import { createFileRoute, redirect, useParams } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { CheckCircle2, ClipboardList, Loader2, Timer, ChevronRight } from "lucide-react";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";

/* ── Session feedback ("Évaluation de la séance") — feedback about a
   classroom TeachingSession, deliberately not the exam/QCM system (spec
   §10). Every student gets the same 5 questions in a randomized order
   fixed server-side per (session, student); this page just renders
   whatever order the API returns and posts answers back keyed by the
   real question_id, never by display position.

   Two question types share this one questionnaire:
   - "rating"    Q1-2, permanent, 1-5 scale
   - "knowledge" Q3-5, AI-generated QCM from the content actually covered
                 during this specific session — answer stored as the
                 selected option's index.

   Flow: instructions screen (duration + rules, no clock running yet) ->
   "Commencer" calls POST /feedback/start, which records started_at
   server-side (idempotent — a refresh mid-quiz never resets the clock,
   same pattern as exams.py's /start) -> one question at a time,
   forward-only (no going back) -> auto-submits whatever's answered so
   far the instant the countdown hits zero. ─────────────────────────── */
export const Route = createFileRoute("/dashboard/session-feedback/$sessionId")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: SessionFeedbackPage,
});

type RatingQuestion = { id: string; type: "rating"; text_fr: string; text_en: string | null; scale_min: number; scale_max: number };
type KnowledgeQuestion = { id: string; type: "knowledge"; question: string; options: string[] };
type FeedbackQuestion = RatingQuestion | KnowledgeQuestion;

const SCALE_LABELS_FR: Record<number, string> = { 1: "Très mauvais", 2: "Mauvais", 3: "Moyen", 4: "Bon", 5: "Très bon" };
const SCALE_LABELS_EN: Record<number, string> = { 1: "Very poor", 2: "Poor", 3: "Average", 4: "Good", 5: "Very good" };
const OPTION_LETTERS = ["A", "B", "C", "D", "E"];

function fmtTime(secs: number) {
  return `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(Math.max(0, secs) % 60).padStart(2, "0")}`;
}

function SessionFeedbackPage() {
  const { sessionId } = useParams({ from: "/dashboard/session-feedback/$sessionId" });
  const { user } = useAuth();
  const { lang } = useI18n();

  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [questions, setQuestions] = useState<FeedbackQuestion[]>([]);
  const [courseTitle, setCourseTitle] = useState<string | null>(null);
  const [durationMinutes, setDurationMinutes] = useState(5);
  const [alreadySubmitted, setAlreadySubmitted] = useState(false);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [submitting, setSubmitting] = useState(false);
  const [justSubmitted, setJustSubmitted] = useState(false);

  // null deadline = instructions screen still showing, clock not running.
  const [deadlineAt, setDeadlineAt] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const [currentIndex, setCurrentIndex] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Avoids a race where the 0-second tick and a manual click both fire
  // handleSubmit before the first request even returns.
  const submittedRef = useRef(false);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setNotFound(false);
      try {
        const data = (await api.get(`/api/teaching-sessions/${sessionId}/feedback`)) as {
          questions: FeedbackQuestion[]; already_submitted: boolean; course_title: string | null;
          started_at: string | null; deadline_at: string | null; duration_minutes: number;
        };
        if (cancelled) return;
        setQuestions(data.questions);
        setAlreadySubmitted(data.already_submitted);
        setCourseTitle(data.course_title);
        setDurationMinutes(data.duration_minutes);
        // Refresh mid-quiz: the clock was already running server-side —
        // resume it instead of showing the instructions screen again.
        if (data.started_at && data.deadline_at && !data.already_submitted) {
          setDeadlineAt(data.deadline_at);
          setTimeLeft(Math.max(0, Math.round((new Date(data.deadline_at).getTime() - Date.now()) / 1000)));
        }
      } catch {
        if (!cancelled) setNotFound(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, sessionId]);

  async function startQuiz() {
    setStarting(true);
    try {
      const res: { started_at: string; deadline_at: string } = await api.post(`/api/teaching-sessions/${sessionId}/feedback/start`, {});
      setDeadlineAt(res.deadline_at);
      setTimeLeft(Math.max(0, Math.round((new Date(res.deadline_at).getTime() - Date.now()) / 1000)));
      setCurrentIndex(0);
    } catch (e: any) {
      toast.error(e.message || (lang === "fr" ? "Erreur" : "Error"));
    } finally {
      setStarting(false);
    }
  }

  async function handleSubmit(finalAnswers: Record<string, number>) {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      await api.post(`/api/teaching-sessions/${sessionId}/feedback`, { answers: finalAnswers });
      if (timerRef.current) clearInterval(timerRef.current);
      setJustSubmitted(true);
      toast.success(lang === "fr" ? "Merci pour votre évaluation !" : "Thanks for your feedback!");
    } catch (e: any) {
      submittedRef.current = false; // let the student retry — e.g. a transient network error
      toast.error(e.message || (lang === "fr" ? "Erreur" : "Error"));
    } finally {
      setSubmitting(false);
    }
  }

  // Countdown — only runs once the clock has actually started and hasn't
  // been submitted yet; auto-submits whatever's answered so far at zero.
  useEffect(() => {
    if (!deadlineAt || justSubmitted || alreadySubmitted) { if (timerRef.current) clearInterval(timerRef.current); return; }
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) { clearInterval(timerRef.current!); handleSubmit(answers); return 0; }
        return t - 1;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- answers is read via ref-like closure on purpose, re-subscribing every keystroke would be wasteful
  }, [deadlineAt, justSubmitted, alreadySubmitted]);

  if (!user) return null;

  const labels = lang === "fr" ? SCALE_LABELS_FR : SCALE_LABELS_EN;
  const done = alreadySubmitted || justSubmitted;
  const started = !!deadlineAt;
  const current = questions[currentIndex];
  const isLast = currentIndex === questions.length - 1;
  const currentAnswered = !!current && current.id in answers;
  const urgent = timeLeft < 60;

  function selectAnswer(qid: string, value: number) {
    setAnswers(prev => ({ ...prev, [qid]: value }));
  }

  function advance() {
    if (isLast) { handleSubmit(answers); return; }
    setCurrentIndex(i => Math.min(i + 1, questions.length - 1));
  }

  return (
    <div className="space-y-4" style={{ maxWidth: 640 }}>
      <PageHead
        eyebrow={lang === "fr" ? "Évaluation de la séance" : "Session feedback"}
        title={courseTitle || (lang === "fr" ? "Séance de cours" : "Class session")}
        sub={lang === "fr" ? "Votre avis, puis un mini contrôle sur ce qui vient d'être vu." : "Your feedback, then a quick check on what was just covered."}
      />

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
      ) : notFound ? (
        <div className="dash-card">
          <EmptyHint
            icon={<ClipboardList size={28} strokeWidth={1.7} />}
            text={lang === "fr" ? "Cette évaluation est introuvable ou ne vous concerne pas." : "This feedback form is unavailable to you."}
          />
        </div>
      ) : done ? (
        <div className="dash-card anim-pop flex flex-col items-center gap-3 py-12 text-center">
          <CheckCircle2 size={40} strokeWidth={1.5} style={{ color: "var(--pal-primary, #2F6F5E)" }} />
          <p className="text-sm font-semibold" style={{ color: "var(--pal-ink, oklch(22% 0.025 175))" }}>
            {lang === "fr" ? "Vous avez déjà évalué cette séance." : "You have already submitted feedback for this session."}
          </p>
        </div>
      ) : !started ? (
        <div className="space-y-4" data-testid="feedback-instructions">
          <div className="dash-card p-6 space-y-4">
            <div className="flex items-center justify-around text-center">
              <div>
                <div className="font-display text-2xl font-bold">{durationMinutes}</div>
                <div className="text-xs text-muted-foreground">{lang === "fr" ? "minutes" : "minutes"}</div>
              </div>
              <div>
                <div className="font-display text-2xl font-bold">{questions.length}</div>
                <div className="text-xs text-muted-foreground">{lang === "fr" ? "questions" : "questions"}</div>
              </div>
            </div>
            <div className="border-t border-border pt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                {lang === "fr" ? "À savoir" : "Good to know"}
              </p>
              <ul className="mt-2 space-y-2 text-sm">
                <li className="flex gap-2">
                  <Timer className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--pal-primary, #2F6F5E)" }} />
                  {lang === "fr"
                    ? "Le chronomètre démarre dès que vous cliquez sur « Commencer » et ne s'arrête plus."
                    : "The timer starts the moment you click \"Start\" and won't stop."}
                </li>
                <li className="flex gap-2">
                  <ChevronRight className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--pal-primary, #2F6F5E)" }} />
                  {lang === "fr"
                    ? "Les questions s'affichent une par une — une fois passée à la suivante, impossible de revenir en arrière."
                    : "Questions appear one at a time — once you move to the next one, you can't go back."}
                </li>
                <li className="flex gap-2">
                  <ClipboardList className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--pal-primary, #2F6F5E)" }} />
                  {lang === "fr"
                    ? "Les 2 premières questions sont votre avis sur la séance, les suivantes un mini contrôle sur ce qui vient d'être vu."
                    : "The first 2 questions are your feedback on the session, the rest a quick check on what was just covered."}
                </li>
              </ul>
            </div>
          </div>
          <div className="flex justify-end">
            <button
              type="button"
              className="btn-c btn-c-primary btn-c-sm"
              disabled={starting}
              onClick={startQuiz}
              data-testid="start-feedback-btn"
            >
              {starting ? <Loader2 size={13} className="animate-spin" /> : null}
              {lang === "fr" ? "Commencer" : "Start"}
            </button>
          </div>
        </div>
      ) : !current ? null : (
        <div className="space-y-3">
          <div className="flex items-center justify-between rounded-2xl border border-border bg-card p-3.5 shadow-card">
            <p className="text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider">
              {(lang === "fr" ? "Question" : "Question") + ` ${currentIndex + 1}/${questions.length}`}
            </p>
            <div
              className="flex items-center gap-1.5 rounded-lg px-2.5 py-1 font-mono text-sm font-bold"
              style={{ color: urgent ? "#b91c1c" : "var(--pal-primary, #2F6F5E)", background: urgent ? "#fef2f2" : "var(--pal-pale, oklch(94% 0.025 165))" }}
            >
              <Timer className="h-3.5 w-3.5" />{fmtTime(timeLeft)}
            </div>
          </div>

          <div className="dash-card p-5" data-testid="feedback-question">
            <p className="text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider mb-2">
              {current.type === "knowledge" && (
                <span className="chip-c chip-c-blue normal-case tracking-normal">
                  {lang === "fr" ? "Contrôle rapide" : "Quick check"}
                </span>
              )}
            </p>

            {current.type === "rating" ? (
              <>
                <p className="text-sm font-semibold mb-4" style={{ color: "var(--pal-ink, oklch(22% 0.025 175))" }}>
                  {lang === "en" && current.text_en ? current.text_en : current.text_fr}
                </p>
                <div className="grid grid-cols-5 gap-2">
                  {Array.from({ length: current.scale_max - current.scale_min + 1 }, (_, idx) => current.scale_min + idx).map(v => (
                    <button
                      key={v}
                      type="button"
                      data-testid={`rating-${v}`}
                      onClick={() => selectAnswer(current.id, v)}
                      className="rounded-xl border px-2 py-2.5 text-center transition-all"
                      style={{
                        borderColor: answers[current.id] === v ? "var(--pal-primary, #2F6F5E)" : "var(--pal-line, #d8d8d8)",
                        background: answers[current.id] === v ? "var(--pal-pale, oklch(94% 0.025 165))" : "transparent",
                        fontWeight: answers[current.id] === v ? 700 : 500,
                      }}
                    >
                      <div className="text-sm tabular-nums">{v}</div>
                      <div className="mt-0.5 text-[10px] leading-tight text-muted-foreground">{labels[v] ?? ""}</div>
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <>
                <p className="text-sm font-semibold mb-4" style={{ color: "var(--pal-ink, oklch(22% 0.025 175))" }}>
                  {current.question}
                </p>
                <div className="space-y-2">
                  {current.options.map((opt, oi) => (
                    <button
                      key={oi}
                      type="button"
                      data-testid={`knowledge-option-${oi}`}
                      onClick={() => selectAnswer(current.id, oi)}
                      className="w-full flex items-center gap-2.5 rounded-xl border px-3.5 py-2.5 text-left text-sm transition-all"
                      style={{
                        borderColor: answers[current.id] === oi ? "var(--pal-primary, #2F6F5E)" : "var(--pal-line, #d8d8d8)",
                        background: answers[current.id] === oi ? "var(--pal-pale, oklch(94% 0.025 165))" : "transparent",
                        fontWeight: answers[current.id] === oi ? 700 : 500,
                      }}
                    >
                      <span className="shrink-0 text-xs font-mono text-muted-foreground">{OPTION_LETTERS[oi]}.</span>
                      <span>{opt}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="button"
              className="btn-c btn-c-primary btn-c-sm"
              disabled={!currentAnswered || submitting}
              onClick={advance}
              data-testid={isLast ? "submit-feedback-btn" : "next-feedback-btn"}
            >
              {submitting ? <Loader2 size={13} className="animate-spin" /> : null}
              {isLast
                ? (lang === "fr" ? "Envoyer mon évaluation" : "Submit feedback")
                : (lang === "fr" ? "Suivant" : "Next")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
