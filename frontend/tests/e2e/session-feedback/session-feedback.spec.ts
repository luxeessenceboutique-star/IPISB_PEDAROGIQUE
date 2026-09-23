import { test, expect, openE2ECourse, E2E_CLASS_NAME } from "../fixtures/auth";

/* FLOW 7 — Session Feedback: professor starts/ends a session (triggers the
   questionnaire) -> student gets a notification -> clicks it (real UI, not
   a direct goto — exercises the notification-click feature) -> sees
   exactly 5 questions -> answers all -> submits -> confirmation ->
   duplicate submission blocked. Uses two authenticated browser contexts
   in one test to model the real two-actor handoff. */
test.describe("Session feedback flow", () => {
  test("student completes the questionnaire after the professor ends a session", async ({ professorPage, studentPage }) => {
    // ── Professor: start -> teach -> end ────────────────────────────
    await openE2ECourse(professorPage);
    const panel = professorPage.getByTestId("teaching-session-panel");
    if ((await panel.getAttribute("data-session-status")) === "idle") {
      await professorPage.getByTestId("session-class-select").selectOption({ label: E2E_CLASS_NAME });
      await professorPage.getByTestId("start-session-btn").click();
      await expect(panel).toHaveAttribute("data-session-status", "active", { timeout: 10_000 });
    }
    await professorPage.getByTestId("end-session-btn").click();
    await expect(panel).toHaveAttribute("data-session-status", "idle", { timeout: 10_000 });

    // ── Student: notification -> questionnaire ──────────────────────
    await studentPage.goto("/dashboard/notifications");
    const notif = studentPage.getByText(/Évaluez votre séance de cours|Rate your class session/).first();
    await expect(notif).toBeVisible({ timeout: 15_000 });
    await notif.click();
    await expect(studentPage).toHaveURL(/\/dashboard\/session-feedback\//);

    // Instructions screen first — the countdown must not start until this
    // is confirmed (spec: server-authoritative /feedback/start, mirrors
    // the exam /start pattern).
    await expect(studentPage.getByTestId("feedback-instructions")).toBeVisible({ timeout: 10_000 });
    await studentPage.getByTestId("start-feedback-btn").click();

    // One question at a time, forward-only. Q1-2 are rating questions
    // (1-5 scale); Q3-5 are AI-generated knowledge-check QCM (pick option
    // A) — answer whichever this question actually is rather than
    // assuming one shape for all 5. "Suivant" on the first four, then the
    // same button reads "submit-feedback-btn" on the fifth.
    for (let i = 0; i < 5; i++) {
      const card = studentPage.getByTestId("feedback-question");
      await expect(card).toBeVisible({ timeout: 10_000 });
      const rating4 = card.getByTestId("rating-4");
      if (await rating4.count()) {
        await rating4.click();
      } else {
        await card.getByTestId("knowledge-option-0").click();
      }
      const isLast = i === 4;
      await studentPage.getByTestId(isLast ? "submit-feedback-btn" : "next-feedback-btn").click();
    }

    await expect(studentPage.getByText(/Merci pour votre évaluation|Thanks for your feedback/)).toBeVisible({ timeout: 10_000 });

    // Reload from scratch — the "already evaluated" state must come back
    // from the server, not just persist as leftover client state, proving
    // the one-response-per-student rule is actually enforced.
    await studentPage.reload();
    await expect(studentPage.getByText(/Vous avez déjà évalué cette séance|already submitted feedback/)).toBeVisible({ timeout: 10_000 });
  });
});
