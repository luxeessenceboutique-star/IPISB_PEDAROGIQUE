import { test, expect } from "@playwright/test";
import { PROFESSOR_EMAIL, PROFESSOR_PASSWORD } from "../fixtures/auth";

/* FLOW 1 — Login. Real browser: open app -> /auth -> fill credentials ->
   submit -> dashboard renders. */
test.describe("Login", () => {
  test("professor can log in and reach the real dashboard UI", async ({ page }) => {
    await page.goto("/auth");
    await expect(page.getByTestId("auth-email")).toBeVisible();

    await page.getByTestId("auth-email").fill(PROFESSOR_EMAIL);
    await page.getByTestId("auth-password").fill(PROFESSOR_PASSWORD);
    await page.getByTestId("auth-submit").click();

    await expect(page).toHaveURL(/\/dashboard/);
    // Not just the URL — the actual sidebar nav must render, proving the
    // authenticated dashboard shell (roles loaded, layout mounted) loaded.
    await expect(page.getByRole("link", { name: /^(Cours|Courses)$/ })).toBeVisible();
    await expect(page.getByRole("link", { name: /^(Notifications)$/ })).toBeVisible();
  });

  test("wrong password is rejected and the user stays on the login page", async ({ page }) => {
    await page.goto("/auth");
    await page.getByTestId("auth-email").fill(PROFESSOR_EMAIL);
    await page.getByTestId("auth-password").fill("definitely-the-wrong-password");
    await page.getByTestId("auth-submit").click();

    // Supabase's own auth error surfaces via a sonner toast — assert the
    // actual error is shown, not just "nothing happened yet".
    await expect(page.getByText(/invalid|incorrect|erreur/i).first()).toBeVisible({ timeout: 10_000 });
    await expect(page).toHaveURL(/\/auth/);
  });
});
