import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test, expect, accessToken, E2E_COURSE_TITLE, E2E_MODULE_TITLE } from "../fixtures/auth";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const API_URL = process.env.E2E_API_URL ?? "http://localhost:9000";

// 1x1 transparent PNG, generated once for the "add image" step — avoids
// shipping a binary fixture in the repo just to exercise a file input.
const TINY_PNG_B64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=";
const TINY_PNG_PATH = path.resolve(__dirname, "tiny.png");

test.beforeAll(() => {
  fs.writeFileSync(TINY_PNG_PATH, Buffer.from(TINY_PNG_B64, "base64"));
});

/* Serial: authoring (create → edit → publish) must finish before the
   ownership-boundary check (needs the exam to exist) and the student flow
   (needs it published) can run — same "one shared fixture, ordered steps"
   pattern permission-boundary.spec.ts and teaching-session.spec.ts use. */
test.describe.serial("Exam Authoring Studio", () => {
  let examId = "";
  const questionText = `E2E question ${Date.now()}`;

  test("professor creates a draft exam from real course content (not Word/PDF/an external tool)", async ({ professorPage: page }) => {
    await page.goto("/dashboard/exams");
    await page.getByRole("link", { name: /Créer un examen|Create exam/ }).click();
    await expect(page).toHaveURL(/\/dashboard\/exams\/new$/);

    // Step 1 — course + content selection, straight from course_modules/
    // course_lessons (§2/§3), never a title the professor just types in.
    await page.getByRole("combobox").click();
    await page.getByRole("option", { name: E2E_COURSE_TITLE }).click();
    await expect(page.getByText(E2E_MODULE_TITLE)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText("Tout le cours")).toBeVisible();
    await page.getByRole("button", { name: /Continuer|Continue/ }).click();

    // Step 2 — configuration screen; defaults are already valid (types
    // checked, difficulty mix sums to 100) so this proves the draft
    // persists real configuration, not just a title.
    await expect(page.getByText(/Configurez l'examen|Configure the exam/)).toBeVisible();
    await page.getByRole("button", { name: /Créer le brouillon|Create draft/ }).click();

    await expect(page).toHaveURL(/\/dashboard\/exams\/[^/]+\/editor$/, { timeout: 15_000 });
    examId = page.url().match(/\/exams\/([^/]+)\/editor/)![1];
    expect(examId).toBeTruthy();
    await expect(page.getByText("Brouillon")).toBeVisible();
  });

  test("professor edits questions, reorders, adds an image, and it survives a refresh", async ({ professorPage: page }) => {
    await page.goto(`/dashboard/exams/${examId}/editor`);

    // Empty draft → add the first question from inside the editor (never
    // Word/PowerPoint/an external editor — everything below stays on this
    // one IPISB Connect page).
    await page.getByRole("button", { name: /Ajouter une question|Add a question/ }).click();
    await page.locator("textarea").fill(questionText);
    const options = page.getByPlaceholder(/^Option [A-D]$/);
    await options.nth(0).fill("Réponse A");
    await options.nth(1).fill("Réponse B — correcte");
    await options.nth(2).fill("Réponse C");
    await options.nth(3).fill("Réponse D");
    // Mark option B (index 1) as correct.
    await page.getByTitle(/Marquer comme bonne réponse|Mark as correct answer/).nth(1).click();
    // Difficulty + type are independent, editable fields (§9), not baked
    // into the question text.
    await page.getByRole("radio", { name: /Difficile|Hard/ }).check();
    await page.locator("textarea").blur();
    await expect(page.getByText(/Enregistré|Saved/)).toBeVisible({ timeout: 10_000 });

    // Add an image directly in the editor (§10) — no external image host.
    await page.getByRole("button", { name: /Ajouter une image|Add an image/ }).click();
    await page.setInputFiles('input[type="file"]', TINY_PNG_PATH);
    await expect(page.getByRole("button", { name: /Remplacer|Replace/ })).toBeVisible({ timeout: 15_000 });

    // Add a second question, then reorder it above the first (§9 — real
    // question identity survives reordering, not display position). Wait
    // for the second sidebar row before typing — clicking "+ Question"
    // doesn't block on the create request, and the textarea locator would
    // otherwise still resolve to question 1's (still-mounted) textarea.
    await page.getByRole("button", { name: "Question", exact: true }).click();
    await expect(page.locator("div.group")).toHaveCount(2, { timeout: 10_000 });
    await page.locator("textarea").fill("Second question — to be moved up");
    await page.locator("textarea").blur();
    await expect(page.getByText(/Enregistré|Saved/)).toBeVisible({ timeout: 10_000 });

    const secondRow = page.locator("div.group", { hasText: "Second question" });
    await secondRow.hover();
    await secondRow.getByTitle(/Monter|Move up/).click();
    // Sidebar's first entry should now be the moved-up question.
    await expect(page.locator("div.group").first()).toContainText("Second question");

    // Delete it again — exercises delete, and keeps the exam clean for
    // publish. The delete icon lives in the main editor panel (acting on
    // whichever question is selected), not inside the sidebar row itself.
    await page.locator("div.group", { hasText: "Second question" }).click();
    await page.getByTitle(/Supprimer|Delete/).click();
    await page.getByRole("button", { name: /^Supprimer$|^Delete$/ }).click();
    await expect(page.getByText("Second question — to be moved up")).toHaveCount(0);

    // §22 — refresh must not lose anything; it's persisted server-side, not
    // just React state.
    await page.reload();
    await expect(page.locator("textarea")).toHaveValue(questionText);
    await expect(page.getByPlaceholder("Option B")).toHaveValue("Réponse B — correcte");
    await expect(page.getByRole("radio", { name: /Difficile|Hard/ })).toBeChecked();
    await expect(page.getByRole("button", { name: /Remplacer|Replace/ })).toBeVisible();
  });

  test("preview renders with the same component the student sees, then professor publishes", async ({ professorPage: page }) => {
    await page.goto(`/dashboard/exams/${examId}/editor`);
    await page.getByRole("button", { name: /Aperçu|Preview/ }).click();
    const previewDialog = page.getByRole("dialog");
    await expect(previewDialog.getByText(/Aperçu — vue étudiant|Preview — student view/)).toBeVisible();
    await expect(previewDialog.getByText(questionText)).toBeVisible();
    await expect(previewDialog.getByText("Réponse B — correcte")).toBeVisible();
    await page.keyboard.press("Escape");

    await page.getByRole("button", { name: /^Publier$|^Publish$/ }).click();
    await expect(page.getByText(/^Publié$|^Published$/)).toBeVisible({ timeout: 10_000 });
  });

  test("a professor who does not own the course is rejected by the backend, not just hidden by the UI", async ({ professor2Page: page2 }) => {
    const token = await accessToken(page2);
    const headers = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

    const patchRes = await page2.request.patch(`${API_URL}/api/exams/${examId}`, {
      headers,
      data: { title: "Hijacked title" },
    });
    expect(patchRes.status()).toBe(403);

    const addQRes = await page2.request.post(`${API_URL}/api/exams/${examId}/questions`, {
      headers,
      data: { question: "Injected", options: ["A", "B"], correct_index: 0, type: "multiple_choice" },
    });
    expect(addQRes.status()).toBe(403);

    const deleteRes = await page2.request.delete(`${API_URL}/api/exams/${examId}`, { headers });
    expect(deleteRes.status()).toBe(403);
  });

  test("student takes the published exam inside IPISB Connect and gets an authoritative grade", async ({ studentPage: page }) => {
    await page.goto("/dashboard/exams");
    // Locate by course badge — the exam title itself is dynamic ("Examen — E2E Test Course").
    await expect(page.locator("article", { hasText: "E2E Test Course" }).first()).toBeVisible({ timeout: 10_000 });
    await page.locator("article", { hasText: "E2E Test Course" }).first().getByRole("button", { name: /Passer l'examen|Take exam/ }).click();

    await expect(page.getByText(questionText)).toBeVisible({ timeout: 10_000 });
    // Never redirected to Google Forms/Moodle/an external site — still on
    // IPISB Connect, same tab, same origin.
    await expect(page).toHaveURL(/\/dashboard\/exams$/);
    await expect(page.getByText("Réponse B — correcte")).toBeVisible();
    await page.getByText("Réponse B — correcte").click();

    await page.getByRole("button", { name: /Soumettre l'examen|Submit exam/ }).click();
    await page.getByRole("button", { name: /Soumettre l'examen|Submit exam/ }).last().click();

    await expect(page.getByText(/Score : 1\/1|Score: 1\/1/)).toBeVisible({ timeout: 10_000 });
  });
});
