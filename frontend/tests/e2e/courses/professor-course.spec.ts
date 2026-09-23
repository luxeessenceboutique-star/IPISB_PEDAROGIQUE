import { test, expect, openE2ECourse, E2E_MODULE_TITLE } from "../fixtures/auth";

/* FLOW 2 — Professor course journey: login (via fixture) -> dashboard ->
   courses -> open the E2E course -> open its module -> see real lesson
   content render (the 2-slide deck seeded by seed_e2e.py). */
test.describe("Professor course flow", () => {
  test("professor opens a course, its module, and sees the lesson content", async ({ professorPage: page }) => {
    await openE2ECourse(page);

    // openE2ECourse already clicked the module button; the chapter/lesson
    // pane should now show the seeded slide content. The module title
    // appears twice on screen (sidebar button + reading-pane heading) —
    // scope to the heading specifically to avoid a strict-mode collision.
    await expect(page.getByRole("heading", { name: E2E_MODULE_TITLE })).toBeVisible();
    await expect(page.getByText("E2E Slide One")).toBeVisible();
  });
});
