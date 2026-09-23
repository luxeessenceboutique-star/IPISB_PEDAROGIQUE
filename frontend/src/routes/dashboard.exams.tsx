import { createFileRoute, redirect, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api, ApiError } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import { GraduationCap, Plus, Loader2, Timer, AlertTriangle, ChevronRight, Eye, EyeOff, Pencil } from "lucide-react";
import { ListSkeleton } from "@/components/Skeletons";
import { PageHead, SectionLabel, EmptyHint } from "@/components/dashboard/ui";
import { QuestionView } from "@/components/exams/QuestionView";
import { useDeepLinkFocus } from "@/lib/deep-link";

export const Route = createFileRoute("/dashboard/exams")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: ExamsPage,
});

type Exam = { id: string; course_id: string; title: string; description: string | null; duration_minutes: number; start_time: string | null; end_time: string | null; is_published: boolean; created_at: string; type?: "examen" | "quiz"; course_title?: string; question_count?: number; my_response?: ExamResponse | null };
type Question = { id: string; exam_id?: string; question: string; options: string[]; correct_index?: number; order_num: number; image_url?: string | null; image_caption?: string | null };
type ExamResponse = { id: string; answers: Record<string, number>; score: number | null; total: number | null; submitted_at: string };

function ExamsPage() {
  const { t, lang } = useI18n();
  const { user, roles } = useAuth();
  const isAdmin   = roles.includes("admin");
  const isProf    = roles.includes("professor");
  const canCreate = isAdmin || isProf;

  const [exams,      setExams]      = useState<Exam[]>([]);
  const [loading,    setLoading]    = useState(true);
  const { focusId, attachFocus } = useDeepLinkFocus();

  const [takingExam, setTakingExam] = useState<{ exam: Exam; questions: Question[] } | null>(null);
  const [answers,    setAnswers]    = useState<Record<string, number>>({});
  const [timeLeft,   setTimeLeft]   = useState(0);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [tabWarnings, setTabWarnings] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [resultsExam, setResultsExam] = useState<{ exam: Exam; questions: Question[]; response: ExamResponse } | null>(null);

  async function load() {
    if (!user) return;
    setLoading(true);
    try {
      if (canCreate) {
        const courseQ = isAdmin ? supabase.from("courses").select("id, title") : supabase.from("courses").select("id, title").eq("professor_id", user!.id);
        const { data: courses } = await courseQ;
        const courseMap: Record<string, string> = Object.fromEntries((courses ?? []).map((c: any) => [c.id, c.title]));
        const courseIds = Object.keys(courseMap);
        if (!courseIds.length) { setExams([]); return; }
        const { data: raw } = await supabase.from("exams").select("*").in("course_id", courseIds).order("created_at", { ascending: false });
        const examList = raw ?? [];
        if (!examList.length) { setExams([]); return; }
        const examIds = examList.map((e: any) => e.id);
        const { data: qRows } = await supabase.from("exam_questions").select("exam_id").in("exam_id", examIds);
        const qCount: Record<string, number> = {};
        for (const q of qRows ?? []) qCount[(q as any).exam_id] = (qCount[(q as any).exam_id] ?? 0) + 1;
        setExams(examList.map((e: any) => ({ ...e, course_title: courseMap[e.course_id] ?? "—", question_count: qCount[e.id] ?? 0 })));
      } else {
        const { data: enrollments } = await supabase.from("course_enrollments").select("course_id").eq("student_id", user!.id);
        const enrolledIds = (enrollments ?? []).map((e: any) => e.course_id);
        if (!enrolledIds.length) { setExams([]); return; }
        const { data: courses } = await supabase.from("courses").select("id, title").in("id", enrolledIds);
        const courseMap: Record<string, string> = Object.fromEntries((courses ?? []).map((c: any) => [c.id, c.title]));
        const { data: raw } = await supabase.from("exams").select("*").in("course_id", enrolledIds).eq("is_published", true).order("created_at", { ascending: false });
        const examList = raw ?? [];
        if (!examList.length) { setExams([]); return; }
        const examIds = examList.map((e: any) => e.id);
        const [qRows, respRows] = await Promise.all([
          supabase.from("exam_questions").select("exam_id").in("exam_id", examIds),
          supabase.from("exam_responses").select("*").eq("student_id", user!.id).in("exam_id", examIds),
        ]);
        const qCount: Record<string, number> = {};
        for (const q of qRows.data ?? []) qCount[(q as any).exam_id] = (qCount[(q as any).exam_id] ?? 0) + 1;
        const respMap: Record<string, any> = Object.fromEntries((respRows.data ?? []).map((r: any) => [r.exam_id, r]));
        setExams(examList.map((e: any) => ({ ...e, course_title: courseMap[e.course_id] ?? "—", question_count: qCount[e.id] ?? 0, my_response: respMap[e.id] ?? null })));
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (user) load(); }, [user]);

  useEffect(() => {
    if (!takingExam) return;
    function handleVisibility() {
      if (document.hidden) setTabWarnings(w => { toast.warning(t("exams.warning_tab"), { duration: 4000 }); return w + 1; });
    }
    document.addEventListener("visibilitychange", handleVisibility);
    return () => document.removeEventListener("visibilitychange", handleVisibility);
  }, [takingExam]);

  useEffect(() => {
    if (!takingExam) { if (timerRef.current) clearInterval(timerRef.current); return; }
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) { clearInterval(timerRef.current!); autoSubmitExam(); return 0; }
        return t - 1;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [takingExam]);

  if (!user) return null;

  async function openExam(exam: Exam) {
    try {
      // §17/§22 — server-authoritative start: records started_at once so the
      // deadline (and the countdown shown below) survives a page refresh
      // instead of resetting to a fresh duration_minutes every time.
      const start: { started_at: string; deadline_at: string | null; submitted: boolean } = await api.post(`/api/exams/${exam.id}/start`, {});
      if (start.submitted) { toast.error(lang === "fr" ? "Cet examen a déjà été soumis." : "This exam has already been submitted."); load(); return; }
      const questions: Question[] = await api.get(`/api/exams/${exam.id}/questions`);
      if (!questions?.length) { toast.error(lang === "fr" ? "Cet examen n'a pas encore de questions." : "This exam has no questions yet."); return; }
      const secondsLeft = start.deadline_at
        ? Math.max(0, Math.round((new Date(start.deadline_at).getTime() - Date.now()) / 1000))
        : exam.duration_minutes * 60;
      setAnswers({}); setTabWarnings(0); setTimeLeft(secondsLeft);
      setTakingExam({ exam, questions });
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Error"); }
  }

  async function autoSubmitExam() { if (!takingExam) return; await doSubmit(takingExam, answers); }

  async function doSubmit(state: { exam: Exam; questions: Question[] }, currentAnswers: Record<string, number>) {
    setSubmitting(true); setConfirmSubmit(false);
    try {
      // Backend is authoritative: grades from exam_questions.correct_index
      // server-side and rejects late/duplicate submissions — the client
      // never computes or sees the score before this call returns.
      const { score, total }: { score: number; total: number } = await api.post(`/api/exams/${state.exam.id}/submit`, { answers: currentAnswers });
      setTakingExam(null);
      if (timerRef.current) clearInterval(timerRef.current);
      toast.success(lang === "fr" ? `Examen soumis ! Score : ${score}/${total}` : `Exam submitted! Score: ${score}/${total}`);
      load();
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Error"); }
    finally { setSubmitting(false); }
  }

  async function openResults(exam: Exam) {
    try {
      const data: { response: ExamResponse; questions: Question[] } = await api.get(`/api/exams/${exam.id}/result`);
      setResultsExam({ exam, questions: data.questions, response: data.response });
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Error"); }
  }

  async function togglePublish(exam: Exam) {
    if (!exam.is_published && (exam.question_count ?? 0) === 0) { toast.error(t("exams.add_questions_first")); return; }
    try {
      await api.put(`/api/exams/${exam.id}/publish`);
      toast.success(exam.is_published ? t("exams.unpublished") : t("exams.published"));
      load();
    } catch (e) { toast.error(e instanceof ApiError ? e.message : "Error"); }
  }

  const fmtTime = (secs: number) => `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;

  if (takingExam) {
    const { exam, questions } = takingExam;
    const answered = Object.keys(answers).length;
    const pct = (answered / questions.length) * 100;
    const urgent = timeLeft < 120;
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-between rounded-2xl border border-border bg-card p-4 shadow-card">
          <div>
            <h2 className="font-display font-bold">{exam.title}</h2>
            <p className="text-xs text-muted-foreground">{answered}/{questions.length} {lang === "fr" ? "répondues" : "answered"}</p>
          </div>
          <div className={`flex items-center gap-2 rounded-xl px-4 py-2 font-mono text-lg font-bold ${urgent ? "bg-red-50 text-red-600" : "bg-gradient-brand text-white"}`}>
            <Timer className="h-4 w-4" />{fmtTime(timeLeft)}
          </div>
        </div>
        {tabWarnings > 0 && (
          <div className="flex items-center gap-2 rounded-xl bg-yellow-50 px-4 py-3 text-sm text-yellow-700">
            <AlertTriangle className="h-4 w-4 shrink-0" />{t("exams.warning_tab")} ({tabWarnings}x)
          </div>
        )}
        <Progress value={pct} className="h-1.5" />
        <div className="space-y-4">
          {questions.map((q, qi) => (
            <Card key={q.id} className="border-0 p-5 shadow-card">
              <QuestionView q={q} index={qi} selectedOption={answers[q.id]} onSelect={oi => setAnswers(a => ({ ...a, [q.id]: oi }))} />
            </Card>
          ))}
        </div>
        <div className="flex justify-end gap-3">
          <Button className="border-0 bg-gradient-brand text-white" onClick={() => setConfirmSubmit(true)} disabled={submitting}>
            <ChevronRight className="h-4 w-4" />{t("exams.submit")}
          </Button>
        </div>
        <Dialog open={confirmSubmit} onOpenChange={setConfirmSubmit}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle className="font-display">{t("exams.confirm_submit")}</DialogTitle>
              <DialogDescription>{t("exams.confirm_submit_desc")}</DialogDescription>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">{answered}/{questions.length} {lang === "fr" ? "questions répondues." : "questions answered."}</p>
            <DialogFooter>
              <Button variant="outline" onClick={() => setConfirmSubmit(false)}>{lang === "fr" ? "Annuler" : "Cancel"}</Button>
              <Button className="border-0 bg-gradient-brand text-white" disabled={submitting} onClick={() => doSubmit(takingExam, answers)}>
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : t("exams.submit")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }

  const upcoming = canCreate ? exams : exams.filter(e => !e.my_response);
  const done     = canCreate ? []    : exams.filter(e => !!e.my_response);

  const examCard = (exam: Exam) => (
    <article key={exam.id} ref={exam.id === focusId ? attachFocus : undefined} className="dash-card lift-c card-pop flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between gap-2">
        <span className="chip-c chip-c-green">{exam.course_title}</span>
        {canCreate
          ? <span className={`chip-c ${exam.is_published ? "chip-c-green" : ""}`}>{exam.is_published ? t("exams.status.published") : t("exams.status.draft")}</span>
          : <span className="chip-c chip-c-amber">{lang === "fr" ? "À venir" : lang === "ar" ? "قادم" : "Upcoming"}</span>}
      </div>
      <h3 className="h-serif" style={{ fontSize: 20, lineHeight: 1.2 }}>{exam.title}</h3>
      {exam.description && <p className="line-clamp-2" style={{ fontSize: 12.5, color: "var(--pal-muted)" }}>{exam.description}</p>}
      <div className="flex flex-wrap items-center gap-4" style={{ fontSize: 12.5, color: "var(--pal-muted)" }}>
        <span className="flex items-center gap-1.5"><Timer size={14} strokeWidth={1.7} />{exam.duration_minutes} {t("exams.mins")}</span>
        <span>{exam.question_count} {t("exams.questions_count")}</span>
      </div>
      <div className="mt-1 flex flex-wrap gap-2">
        {!canCreate && <button type="button" className="btn-c btn-c-green btn-c-sm" onClick={() => openExam(exam)}>{t("exams.take")}</button>}
        {canCreate && (
          <>
            <Link to="/dashboard/exams/$examId/editor" params={{ examId: exam.id }} className="btn-c btn-c-ghost btn-c-sm">
              <Pencil size={13} strokeWidth={1.7} />{lang === "fr" ? "Modifier" : lang === "ar" ? "تعديل" : "Edit"}
            </Link>
            <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => togglePublish(exam)}>
              {exam.is_published ? <><EyeOff size={13} strokeWidth={1.7} />{t("exams.unpublish")}</> : <><Eye size={13} strokeWidth={1.7} />{t("exams.publish")}</>}
            </button>
          </>
        )}
      </div>
    </article>
  );

  return (
    <div>
      <PageHead
        eyebrow={lang === "fr" ? "Évaluations QCM" : lang === "ar" ? "اختبارات QCM" : "MCQ assessments"}
        title={t("dash.exams")}
        sub={t("exams.subtitle")}
        actions={canCreate ? (
          <Link to="/dashboard/exams/new" className="btn-c btn-c-primary">
            <Plus size={15} strokeWidth={1.7} />{t("exams.create")}
          </Link>
        ) : undefined}
      />

      {loading ? (
        <ListSkeleton rows={4} />
      ) : exams.length === 0 ? (
        <div className="dash-card">
          <EmptyHint icon={<GraduationCap size={28} strokeWidth={1.7} />} text={t("exams.empty")} />
        </div>
      ) : (
        <div className="space-y-7">
          {upcoming.length > 0 && (
            <div>
              <SectionLabel>{lang === "fr" ? "À venir" : lang === "ar" ? "قادمة" : "Upcoming"}</SectionLabel>
              <div className="grid gap-4" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(min(380px, 100%), 1fr))" }}>
                {upcoming.map(examCard)}
              </div>
            </div>
          )}

          {done.length > 0 && (
            <div>
              <SectionLabel>{lang === "fr" ? "Résultats" : lang === "ar" ? "النتائج" : "Results"}</SectionLabel>
              <div className="dash-card overflow-hidden">
                {done.map(exam => (
                  <div key={exam.id} ref={exam.id === focusId ? attachFocus : undefined} className="row-c">
                    <span className="flex shrink-0" style={{ color: "var(--pal-primary)" }}>
                      <GraduationCap size={20} strokeWidth={1.7} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div style={{ fontWeight: 700, fontSize: 14, color: "var(--pal-ink)" }}>{exam.title}</div>
                      <div className="mt-0.5" style={{ fontSize: 12, color: "var(--pal-muted)" }}>
                        {exam.course_title} · {exam.question_count} {t("exams.questions_count")} · {exam.duration_minutes} {t("exams.mins")}
                      </div>
                    </div>
                    <span
                      className="whitespace-nowrap"
                      style={{ fontFamily: "'Cormorant Garamond', Georgia, serif", fontSize: 26, fontWeight: 500, color: "var(--pal-primary-deep)" }}
                    >
                      {exam.my_response?.score}/{exam.my_response?.total}
                    </span>
                    <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => openResults(exam)}>
                      {t("exams.view_results")}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Results */}
      <Dialog open={!!resultsExam} onOpenChange={o => !o && setResultsExam(null)}>
        <DialogContent className="max-h-[90vh] sm:max-w-2xl overflow-y-auto">
          <DialogHeader><DialogTitle className="font-display">{t("exams.results")} — {resultsExam?.exam.title}</DialogTitle></DialogHeader>
          {resultsExam && (
            <div className="space-y-4">
              <div className="flex items-center gap-4 rounded-2xl bg-gradient-brand p-5 text-white">
                <div className="text-center">
                  <div className="font-display text-4xl font-bold">{resultsExam.response.score}<span className="text-xl font-normal opacity-80">/{resultsExam.response.total}</span></div>
                  <div className="mt-1 text-sm opacity-80">{t("exams.score")}</div>
                </div>
                <div className="flex-1">
                  <Progress value={((resultsExam.response.score ?? 0) / (resultsExam.response.total ?? 1)) * 100} className="h-3 bg-white/20" />
                  <p className="mt-2 text-sm opacity-80">{Math.round(((resultsExam.response.score ?? 0) / (resultsExam.response.total ?? 1)) * 100)}% {t("exams.correct")}</p>
                </div>
              </div>
              {resultsExam.questions.map((q, qi) => {
                const chosen  = (resultsExam.response.answers as Record<string, number>)[q.id];
                const correct = q.correct_index ?? -1;
                const isRight = chosen === correct;
                return (
                  <div key={q.id} className={`rounded-xl border p-4 ${isRight ? "border-green-200 bg-green-50" : "border-red-200 bg-red-50"}`}>
                    <QuestionView q={q} index={qi} selectedOption={chosen} disabled revealCorrect correctIndex={correct} />
                  </div>
                );
              })}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
