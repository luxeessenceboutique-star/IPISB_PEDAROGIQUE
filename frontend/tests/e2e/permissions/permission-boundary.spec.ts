import { test, expect } from "../fixtures/auth";

/* FLOW 4 — Permission boundary. A student navigating to a professor/
   admin-only page (Teaching Sessions) must be denied — using the
   application's own existing authorization behavior (backend 403 ->
   frontend "forbidden" state), not an invented one. */
test.describe("Permission boundaries", () => {
  test("student cannot access the Teaching Sessions page", async ({ studentPage: page }) => {
    // Deliberately not in the student sidebar — direct navigation, as a
    // student who guessed/bookmarked the URL would do.
    await page.goto("/dashboard/teaching-sessions");

    await expect(page.getByText(/Réservé aux professeurs et administrateurs|Professors and admins only/)).toBeVisible({ timeout: 10_000 });
    // And no real session data leaks into the DOM regardless of the message shown.
    await expect(page.getByRole("button", { name: /Résultats|Results/ })).toHaveCount(0);
  });

  test("student does not see the Teaching Sessions link in the sidebar at all", async ({ studentPage: page }) => {
    await expect(page.getByRole("link", { name: /Séances|Sessions/ })).toHaveCount(0);
  });

  /* Tasks module (`tasks.tasks`, Channel 1) — students hold no V1 role for
     this entity, so `dashboard.tasks.tsx`'s beforeLoad redirects them back
     to /dashboard rather than rendering the page (same guard pattern as
     dashboard.rh.tsx / dashboard.accounting.tsx). */
  test("student is redirected away from the Tasks page on direct navigation", async ({ studentPage: page }) => {
    await page.goto("/dashboard/tasks");
    await expect(page).toHaveURL(/\/dashboard\/?$/, { timeout: 10_000 });
  });

  test("student does not see the Tasks link in the sidebar", async ({ studentPage: page }) => {
    await expect(page.getByRole("link", { name: /Tâches|Tasks/ })).toHaveCount(0);
  });

  test("professor can reach the Tasks page", async ({ professorPage: page }) => {
    await page.goto("/dashboard/tasks");
    await expect(page).toHaveURL(/\/dashboard\/tasks/);
    await expect(page.getByRole("heading", { name: /Gestion des tâches/ })).toBeVisible({ timeout: 10_000 });
  });
});
