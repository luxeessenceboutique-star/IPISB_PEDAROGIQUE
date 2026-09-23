import { test, expect, openE2ECourse, E2E_MODULE_2_TITLE } from "../fixtures/auth";

/* FLOW 3 — Student course journey: login -> dashboard -> open the
   enrolled E2E course -> open module 1 -> read content -> navigate to
   the next chapter -> content changes. Also confirms student permissions
   are respected: the progress bar (a student-only UI element) is shown. */
test.describe("Student course flow", () => {
  test("student opens the course, reads a lesson, and navigates chapters", async ({ studentPage: page }) => {
    await openE2ECourse(page);

    // Student-only UI: the progress bar. Proves this render path is the
    // student view, not a professor/admin preview of the same page.
    await expect(page.getByText(/Progression|Progress/)).toBeVisible();
    await expect(page.getByText("E2E Slide One")).toBeVisible();

    // Chapter navigation: module 1 -> module 2, content actually changes.
    // (data-testid, not role+name — the slide viewer's own Prev/Next
    // buttons render the identical "Suivant"/"Précédent" text on this
    // same page when the chapter has slides.)
    await page.getByTestId("chapter-next").click();
    // Same collision as the professor spec — title renders in both the
    // sidebar and the reading-pane heading; scope to the heading.
    await expect(page.getByRole("heading", { name: E2E_MODULE_2_TITLE })).toBeVisible();
    await expect(page.getByText("E2E Text Lesson")).toBeVisible();

    // And back.
    await page.getByTestId("chapter-prev").click();
    await expect(page.getByText("E2E Slide One")).toBeVisible();
  });
});
