import { test, expect, openE2ECourse, E2E_CLASS_NAME } from "../fixtures/auth";

/* FLOW 6 — Teaching Session: select course + class -> Start Session ->
   session indicator appears -> navigate -> tracked position changes ->
   End Session -> completed state. Real UI throughout — no direct calls
   to POST /teaching-sessions. */
test.describe("Teaching session flow", () => {
  test("professor starts a classroom session, position tracks navigation, and ends it", async ({ professorPage: page }) => {
    await openE2ECourse(page);

    const panel = page.getByTestId("teaching-session-panel");
    await expect(panel).toBeVisible();

    // A prior interrupted run may have left this session ACTIVE — resuming
    // it is the correct, designed behavior (spec §21), not a test bug.
    if ((await panel.getAttribute("data-session-status")) === "idle") {
      await page.getByTestId("session-class-select").selectOption({ label: E2E_CLASS_NAME });
      await page.getByTestId("start-session-btn").click();
    }

    await expect(panel).toHaveAttribute("data-session-status", "active", { timeout: 10_000 });
    await expect(page.getByText(/Séance en cours|Session active/)).toBeVisible();
    await expect(page.getByText(/Démarrée à|Started/)).toBeVisible();

    // Current position is shown and updates as the professor navigates.
    await expect(page.getByText(/Position ?:/)).toContainText("E2E Module 1");
    await page.getByTestId("chapter-next").click();
    await expect(page.getByText(/Position ?:/)).toContainText("E2E Module 2");

    await page.getByTestId("end-session-btn").click();
    await expect(panel).toHaveAttribute("data-session-status", "idle", { timeout: 10_000 });
    await expect(page.getByText(/Séance terminée|Session ended/)).toBeVisible({ timeout: 10_000 });

    // Idle state means the Start form is back, proving a clean COMPLETED
    // transition rather than the panel just disappearing.
    await expect(page.getByTestId("start-session-btn")).toBeVisible();
  });
});
