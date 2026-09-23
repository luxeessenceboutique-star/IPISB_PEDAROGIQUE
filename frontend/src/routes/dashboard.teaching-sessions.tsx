import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { Presentation, Loader2, ChevronRight } from "lucide-react";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";
import { ListSkeleton } from "@/components/Skeletons";

/* ── Teaching session history + feedback results (Phase 4). Read-only —
   starting/ending a session happens from the course reader page. This is
   the "what actually happened, session by session" view (spec §17/§22),
   plus the aggregated feedback dashboard (spec §16: aggregate only, never
   individual student answers). ─────────────────────────────────────── */
export const Route = createFileRoute("/dashboard/teaching-sessions")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: TeachingSessionsPage,
});

type ContentPosition = { module_id: string; lesson_id: string | null; slide_id: string | null } | null;
type SessionRow = {
  id: string;
  status: "active" | "completed" | "cancelled" | "scheduled";
  started_at: string;
  ended_at: string | null;
  duration_seconds: number | null;
  start_position: ContentPosition;
  end_position: ContentPosition;
  course_title: string;
  class_name: string;
  professor_name: string;
  start_module_title: string | null;
  end_module_title: string | null;
  feedback_invited: number;
  feedback_responses: number;
};
type FeedbackResults = {
  invited: number;
  responses: number;
  response_rate: number;
  per_question: { question_id: string; text_fr: string; average: number | null; count: number }[];
  overall_average: number | null;
  learning_check: { question_id: string; question: string; explanation: string | null; correct_count: number; answered_count: number; correct_rate: number | null }[];
  learning_check_score: number | null;
};
type Comparison = { id: string; name: string; session_count: number; average: number | null };
type AnalyticsSummary = {
  total_sessions: number;
  completed_sessions: number;
  total_invited: number;
  total_responses: number;
  response_rate: number;
  overall_average: number | null;
  by_professor: Comparison[];
  by_course: Comparison[];
};

function formatDuration(totalSeconds: number | null, lang: string): string {
  if (totalSeconds == null) return "—";
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  if (h > 0) return `${h}h${String(m).padStart(2, "0")}`;
  return lang === "fr" ? `${m}min` : `${m}m`;
}

const STATUS_LABEL: Record<string, { fr: string; en: string; chip: string }> = {
  active: { fr: "En cours", en: "Active", chip: "chip-c-blue" },
  completed: { fr: "Terminée", en: "Completed", chip: "chip-c-green" },
  cancelled: { fr: "Annulée", en: "Cancelled", chip: "chip-c-red" },
  scheduled: { fr: "Planifiée", en: "Scheduled", chip: "chip-c-amber" },
};

function TeachingSessionsPage() {
  const { user, roles } = useAuth();
  const { lang } = useI18n();
  const isAdmin = roles.includes("admin");

  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);

  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);

  const [resultsFor, setResultsFor] = useState<SessionRow | null>(null);
  const [results, setResults] = useState<FeedbackResults | null>(null);
  const [loadingResults, setLoadingResults] = useState(false);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setForbidden(false);
      try {
        const data = (await api.get("/api/teaching-sessions")) as SessionRow[];
        if (!cancelled) setSessions(data);
      } catch (e: any) {
        if (cancelled) return;
        if (e.status === 403) setForbidden(true);
        else toast.error(e.message || (lang === "fr" ? "Erreur de chargement" : "Failed to load"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Institute-wide rollup (spec §17/§29 Phase 5) — admin only; the backend
  // 403s for anyone else, so this simply no-ops for professors.
  useEffect(() => {
    if (!user || !isAdmin) return;
    let cancelled = false;
    (async () => {
      try {
        const data = (await api.get("/api/teaching-sessions/analytics/summary")) as AnalyticsSummary;
        if (!cancelled) setSummary(data);
      } catch {
        // silent — the per-session list below still works without it
      }
    })();
    return () => { cancelled = true; };
  }, [user, isAdmin]);

  async function openResults(session: SessionRow) {
    setResultsFor(session);
    setResults(null);
    setLoadingResults(true);
    try {
      const data = (await api.get(`/api/teaching-sessions/${session.id}/feedback/results`)) as FeedbackResults;
      setResults(data);
    } catch (e: any) {
      toast.error(e.message || (lang === "fr" ? "Erreur" : "Error"));
      setResultsFor(null);
    } finally {
      setLoadingResults(false);
    }
  }

  if (!user) return null;

  const fmtDate = (d: string) =>
    new Date(d).toLocaleString(lang === "fr" ? "fr-FR" : "en-US", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });

  const contentCovered = (s: SessionRow) => {
    if (!s.start_module_title && !s.end_module_title) return "—";
    if (!s.end_module_title || s.start_module_title === s.end_module_title) return s.start_module_title ?? s.end_module_title ?? "—";
    return `${s.start_module_title} → ${s.end_module_title}`;
  };

  return (
    <div className="space-y-4">
      <PageHead
        eyebrow={lang === "fr" ? "Historique" : "History"}
        title={lang === "fr" ? "Séances de classe" : "Classroom sessions"}
        sub={lang === "fr" ? "Ce qui a réellement été enseigné, séance par séance." : "What was actually taught, session by session."}
      />

      {isAdmin && summary && (
        <div className="dash-card p-5 space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: lang === "fr" ? "Séances" : "Sessions", value: `${summary.completed_sessions}/${summary.total_sessions}` },
              { label: lang === "fr" ? "Réponses" : "Responses", value: `${summary.total_responses}/${summary.total_invited}` },
              { label: lang === "fr" ? "Taux de réponse" : "Response rate", value: `${Math.round(summary.response_rate * 100)}%` },
              { label: lang === "fr" ? "Note globale" : "Overall average", value: summary.overall_average != null ? `${summary.overall_average.toFixed(1)}/5` : "—" },
            ].map(tile => (
              <div key={tile.label} className="rounded-xl p-3" style={{ background: "var(--pal-cream, oklch(97% 0.012 90))" }}>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{tile.label}</p>
                <p className="mt-1 text-lg font-bold tabular-nums" style={{ color: "var(--pal-ink, oklch(22% 0.025 175))" }}>{tile.value}</p>
              </div>
            ))}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {[
              { title: lang === "fr" ? "Par professeur" : "By professor", rows: summary.by_professor },
              { title: lang === "fr" ? "Par cours" : "By course", rows: summary.by_course },
            ].map(group => (
              <div key={group.title}>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">{group.title}</p>
                <div className="space-y-1.5">
                  {group.rows.length === 0 ? (
                    <p className="text-xs text-muted-foreground">—</p>
                  ) : group.rows.map(r => (
                    <div key={r.id} className="flex items-center gap-2">
                      <span className="min-w-0 flex-1 truncate text-xs" style={{ color: "var(--pal-ink, oklch(22% 0.025 175))" }}>{r.name}</span>
                      <span className="shrink-0 text-[11px] text-muted-foreground">{r.session_count} {lang === "fr" ? "séance(s)" : "session(s)"}</span>
                      <span className="w-10 shrink-0 text-right text-xs font-semibold tabular-nums">{r.average != null ? r.average.toFixed(1) : "—"}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <ListSkeleton rows={4} />
      ) : forbidden ? (
        <div className="dash-card">
          <EmptyHint
            icon={<Presentation size={28} strokeWidth={1.7} />}
            text={lang === "fr" ? "Réservé aux professeurs et administrateurs." : "Professors and admins only."}
          />
        </div>
      ) : sessions.length === 0 ? (
        <div className="dash-card">
          <EmptyHint
            icon={<Presentation size={28} strokeWidth={1.7} />}
            text={lang === "fr" ? "Aucune séance pour le moment. Démarrez-en une depuis la page d'un cours." : "No sessions yet. Start one from a course page."}
          />
        </div>
      ) : (
        <div className="dash-card card-pop overflow-hidden">
          {sessions.map(s => {
            const st = STATUS_LABEL[s.status] ?? STATUS_LABEL.scheduled;
            return (
              <div key={s.id} className="row-c">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p style={{ fontSize: 13.5, fontWeight: 800, color: "var(--pal-ink)" }}>{s.course_title}</p>
                    <span className={`chip-c ${st.chip}`}>{lang === "fr" ? st.fr : st.en}</span>
                  </div>
                  <p className="mt-0.5" style={{ fontSize: 12.5, color: "var(--pal-muted)" }}>
                    {isAdmin ? `${s.professor_name} · ` : ""}{s.class_name} · {fmtDate(s.started_at)} · {formatDuration(s.duration_seconds, lang)}
                  </p>
                  <p className="mt-0.5 truncate" style={{ fontSize: 12, color: "var(--pal-muted)" }}>
                    {(lang === "fr" ? "Contenu : " : "Content: ") + contentCovered(s)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {s.feedback_invited > 0 && (
                    <span className="text-xs tabular-nums text-muted-foreground">
                      {s.feedback_responses}/{s.feedback_invited} {lang === "fr" ? "réponses" : "responses"}
                    </span>
                  )}
                  {s.status === "completed" && s.feedback_invited > 0 && (
                    <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => openResults(s)}>
                      {lang === "fr" ? "Résultats" : "Results"}<ChevronRight size={13} strokeWidth={1.7} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={!!resultsFor} onOpenChange={o => !o && setResultsFor(null)}>
        <DialogContent className="max-h-[90vh] sm:max-w-lg overflow-y-auto overflow-x-hidden">
          <DialogHeader>
            <DialogTitle className="font-display">
              {(lang === "fr" ? "Évaluation de la séance" : "Session feedback") + (resultsFor ? ` — ${resultsFor.course_title}` : "")}
            </DialogTitle>
          </DialogHeader>
          {loadingResults ? (
            <div className="flex justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
          ) : results && resultsFor ? (
            // min-w-0: DialogContent is a CSS grid; without this, a grid item
            // defaults to min-width:auto, so a long truncate/nowrap question
            // below can force this whole item (and everything after it —
            // including the score badge) wider than the dialog. overflow-x
            // -hidden then clips the excess instead of showing "…", which is
            // what was cutting off scores and question text on the right.
            <div className="space-y-4 min-w-0">
              <div className="flex items-center gap-4 rounded-2xl bg-gradient-brand p-5 text-white">
                <div className="text-center">
                  <div className="font-display text-4xl font-bold">
                    {results.overall_average != null ? results.overall_average.toFixed(1) : "—"}
                    <span className="text-xl font-normal opacity-80">/5</span>
                  </div>
                  <div className="mt-1 text-sm opacity-80">{lang === "fr" ? "Note globale" : "Overall"}</div>
                </div>
                <div className="flex-1">
                  <Progress value={results.response_rate * 100} className="h-3 bg-white/20" />
                  <p className="mt-2 text-sm opacity-80">
                    {results.responses}/{results.invited} {lang === "fr" ? "réponses" : "responses"} ({Math.round(results.response_rate * 100)}%)
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {lang === "fr" ? "Évaluation de la séance" : "Session feedback"}
                </p>
                {results.per_question.map(q => (
                  <div key={q.question_id}>
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <p className="text-xs truncate min-w-0" style={{ color: "var(--pal-muted)" }}>{q.text_fr}</p>
                      <span className="text-xs font-semibold tabular-nums shrink-0">{q.average != null ? `${q.average.toFixed(1)}/5` : "—"}</span>
                    </div>
                    <Progress value={q.average != null ? (q.average / 5) * 100 : 0} className="h-2" />
                  </div>
                ))}
              </div>

              {/* Deliberately separate from feedback above (spec: "do not mix
                  these concepts") — this is comprehension, not opinion. */}
              {results.learning_check.length > 0 && (
                <div className="space-y-3 pt-2 border-t border-border">
                  <div className="flex items-center justify-between gap-2 pt-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground min-w-0 truncate">
                      {lang === "fr" ? "Contrôle rapide" : "Quick check"}
                    </p>
                    <span className="chip-c chip-c-blue shrink-0">
                      {results.learning_check_score != null ? `${Math.round(results.learning_check_score * 100)}%` : "—"}
                    </span>
                  </div>
                  {results.learning_check.map(q => (
                    <div key={q.question_id}>
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <p className="text-xs truncate min-w-0" style={{ color: "var(--pal-muted)" }}>{q.question}</p>
                        <span className="text-xs font-semibold tabular-nums shrink-0">
                          {q.correct_rate != null ? `${q.correct_count}/${q.answered_count}` : "—"}
                        </span>
                      </div>
                      <Progress value={q.correct_rate != null ? q.correct_rate * 100 : 0} className="h-2" />
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}
