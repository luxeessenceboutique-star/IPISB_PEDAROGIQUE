import { test, expect, openE2ECourse } from "../fixtures/auth";

/* FLOW 5 — Course presentation/slide viewer. Reuses the existing
   SlideDeckViewer (no second viewer was built) — this exercises its
   actual next/previous controls and confirms the rendered slide changes. */
test.describe("Course presentation flow", () => {
  test("professor navigates slides forward and back", async ({ professorPage: page }) => {
    await openE2ECourse(page); // opens the module with a 2-slide deck

    await expect(page.getByText("E2E Slide One")).toBeVisible();
    await expect(page.getByText("E2E Slide Two")).not.toBeVisible();

    await page.getByTestId("slide-next").click();
    await expect(page.getByText("E2E Slide Two")).toBeVisible();
    await expect(page.getByText("E2E Slide One")).not.toBeVisible();

    // "Next" is disabled on the last slide of a 2-slide deck.
    await expect(page.getByTestId("slide-next")).toBeDisabled();

    await page.getByTestId("slide-prev").click();
    await expect(page.getByText("E2E Slide One")).toBeVisible();
    await expect(page.getByTestId("slide-prev")).toBeDisabled();
  });
});
