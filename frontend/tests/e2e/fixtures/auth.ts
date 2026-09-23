import { test as base, expect, type Page } from "@playwright/test";

/* ── Shared E2E identity + fixture constants — must match
   backend/seed_e2e.py exactly. Overridable via .env.e2e for a different
   environment; defaults match what the seed script creates out of the
   box, so `python backend/seed_e2e.py && npm run test:e2e` works with
   zero configuration. ─────────────────────────────────────────────── */
export const PROFESSOR_EMAIL = process.env.E2E_PROFESSOR_EMAIL ?? "e2e.professor@ipisb.ma";
export const PROFESSOR_PASSWORD = process.env.E2E_PROFESSOR_PASSWORD ?? "E2E_Prof_2026!";
export const STUDENT_EMAIL = process.env.E2E_STUDENT_EMAIL ?? "e2e.student@ipisb.ma";
export const STUDENT_PASSWORD = process.env.E2E_STUDENT_PASSWORD ?? "E2E_Student_2026!";
// Owns nothing — exists only to prove the exam-authoring ownership check
// actually rejects a professor who isn't the course's owner (or admin).
export const PROFESSOR2_EMAIL = process.env.E2E_PROFESSOR2_EMAIL ?? "e2e.professor2@ipisb.ma";
export const PROFESSOR2_PASSWORD = process.env.E2E_PROFESSOR2_PASSWORD ?? "E2E_Prof2_2026!";

export const E2E_CLASS_NAME = "E2E Test Class";
export const E2E_COURSE_TITLE = "E2E Test Course";
export const E2E_MODULE_TITLE = "E2E Module 1";
export const E2E_MODULE_2_TITLE = "E2E Module 2";

export async function loginAs(page: Page, email: string, password: string) {
  await page.goto("/auth");
  await page.getByTestId("auth-email").fill(email);
  await page.getByTestId("auth-password").fill(password);
  await page.getByTestId("auth-submit").click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
}

type Fixtures = {
  professorPage: Page;
  professor2Page: Page;
  studentPage: Page;
};

/** Each test gets its own logged-in browser context — real login through
    the real UI, no storageState shortcuts, so every test genuinely proves
    the auth flow works, not just that a token happens to be valid. */
export const test = base.extend<Fixtures>({
  professorPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await loginAs(page, PROFESSOR_EMAIL, PROFESSOR_PASSWORD);
    await use(page);
    await context.close();
  },
  professor2Page: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await loginAs(page, PROFESSOR2_EMAIL, PROFESSOR2_PASSWORD);
    await use(page);
    await context.close();
  },
  studentPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();
    await loginAs(page, STUDENT_EMAIL, STUDENT_PASSWORD);
    await use(page);
    await context.close();
  },
});

/** Bearer token for `page`'s currently logged-in session — lets a test call
    the backend API directly (e.g. to prove a 403 an unauthorized professor
    gets back, independent of whatever the frontend UI would or wouldn't
    let them click). */
export async function accessToken(page: Page): Promise<string> {
  const token = await page.evaluate(async () => {
    const raw = Object.keys(localStorage).find(k => k.endsWith("-auth-token"));
    if (!raw) return null;
    try { return JSON.parse(localStorage.getItem(raw) ?? "null")?.access_token ?? null; } catch { return null; }
  });
  if (!token) throw new Error("Could not read Supabase access token from localStorage");
  return token;
}

export { expect };

/** Opens the E2E Test Course from the courses list via real UI clicks
    (sidebar -> course card -> "read course" link) — never a direct
    goto(`/dashboard/courses/${id}`), so navigation itself is exercised. */
export async function openE2ECourse(page: Page) {
  await page.getByRole("link", { name: /^(Cours|Courses)$/ }).click();
  await expect(page).toHaveURL(/\/dashboard\/courses/);

  const card = page.locator("article", { hasText: E2E_COURSE_TITLE });
  await expect(card).toBeVisible({ timeout: 15_000 });
  await card.getByTitle(/Lire le cours|Read the course/).click();

  await expect(page).toHaveURL(/\/dashboard\/courses\/[^/]+$/);
  await page.getByRole("button", { name: E2E_MODULE_TITLE }).click();
}
