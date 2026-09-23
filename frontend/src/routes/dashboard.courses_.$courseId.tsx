import { createFileRoute, redirect, Link, useParams } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { marked } from "marked";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, BookOpen, Check, ChevronLeft, Loader2, Play, Square } from "lucide-react";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";
import { SlideDeckViewer, type ViewerSlide } from "@/components/dashboard/SlideDeckViewer";

export const Route = createFileRoute("/dashboard/courses_/$courseId")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: CourseReaderPage,
});

/* ── Types (kept local — this page only needs a read-only slice) ───── */
type CourseInfo = {
  id: string; title: string; code: string | null; semester: string | null;
  assigned_classes?: { id: string; name: string }[];
};
type LessonImage = { id: string; caption: string | null; url: string };
type Lesson = { id: string; content: string | null; images: LessonImage[]; slides?: ViewerSlide[] | null };
type ModuleT = {
  id: string; order_num: number; title: string; objectives: string | null;
  hours_theory: number; hours_practice: number; status: "draft" | "published"; lessons: Lesson[];
};

/* ── Teaching session — a classroom occurrence of teaching this course,
   distinct from the course itself and from student progress (see
   sql/supabase_teaching_sessions_migration.sql). Position is
   {module_id, lesson_id, slide_id}, slide_id null for markdown lessons. */
type ContentPosition = { module_id: string; lesson_id: string | null; slide_id: string | null } | null;
type TeachingSession = {
  id: string; course_id: string; class_id: string; professor_id: string;
  status: "active" | "completed" | "cancelled" | "scheduled";
  started_at: string; ended_at: string | null; duration_seconds: number | null;
  start_position: ContentPosition; current_position: ContentPosition; end_position: ContentPosition;
};

function formatDuration(totalSeconds: number, lang: string): string {
  const h = Math.floor(totalSeconds / 3600);
  const m = Math.floor((totalSeconds % 3600) / 60);
  const s = totalSeconds % 60;
  if (h > 0) return `${h}h${String(m).padStart(2, "0")}`;
  return lang === "fr" ? `${m}min${String(s).padStart(2, "0")}` : `${m}m${String(s).padStart(2, "0")}s`;
}

/* ── Markdown → HTML, with [[image:ID]] tokens spliced in and the
   ```diagram DSL rendered as cards instead of raw text — same content
   the PDF renderer produces, just for a browser instead of a page. ── */
const IMAGE_TOKEN_RE = /\[\[image:([a-f0-9-]+)\]\]/g;
const DIAGRAM_BLOCK_RE = /<pre><code class="language-diagram">([\s\S]*?)<\/code><\/pre>/g;

function escapeHtml(s: string) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderDiagram(rawEscaped: string): string {
  const text = rawEscaped.replace(/&gt;/g, ">").replace(/&lt;/g, "<").replace(/&amp;/g, "&");
  let title = "";
  const categories: { name: string; items: string[] }[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) continue;
    if (/^title:/i.test(line)) title = line.split(":").slice(1).join(":").trim();
    else if (/^cat[eé]gorie:/i.test(line)) categories.push({ name: line.split(":").slice(1).join(":").trim(), items: [] });
    else if (line.startsWith("-") && categories.length) categories[categories.length - 1].items.push(line.slice(1).trim());
  }
  if (!categories.length) return `<pre>${rawEscaped}</pre>`;
  const cards = categories.map(c => `
    <div class="reader-diagram-card">
      <strong>${escapeHtml(c.name)}</strong>
      <ul>${c.items.map(i => `<li>${escapeHtml(i)}</li>`).join("")}</ul>
    </div>`).join("");
  return `<div class="reader-diagram">${title ? `<p class="reader-diagram-title">${escapeHtml(title)}</p>` : ""}<div class="reader-diagram-grid">${cards}</div></div>`;
}

function renderLessonHtml(content: string, images: LessonImage[]): string {
  const byId = new Map(images.map(img => [img.id, img]));
  const parts = content.split(IMAGE_TOKEN_RE);
  let html = "";
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      const img = byId.get(parts[i]);
      if (img) {
        html += `<figure class="reader-image"><img src="${img.url}" alt="${escapeHtml(img.caption || "")}" />${img.caption ? `<figcaption>${escapeHtml(img.caption)}</figcaption>` : ""}</figure>`;
      }
      continue;
    }
    if (!parts[i].trim()) continue;
    let chunk = marked.parse(parts[i], { async: false }) as string;
    chunk = chunk.replace(DIAGRAM_BLOCK_RE, (_m, inner) => renderDiagram(inner));
    html += chunk;
  }
  return html;
}

function CourseReaderPage() {
  const { courseId } = useParams({ from: "/dashboard/courses_/$courseId" });
  const { lang } = useI18n();
  const { user, roles } = useAuth();
  // Progress/resume is a student concept — hide it for professors/admins
  // previewing their own course, since it'd just be meaningless 0/N noise.
  const isStudentView = !roles.includes("admin") && !roles.includes("professor");

  const [course, setCourse] = useState<CourseInfo | null>(null);
  const [modules, setModules] = useState<ModuleT[]>([]);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [completedIds, setCompletedIds] = useState<Set<string>>(new Set());

  // Teaching session — professor/admin only (spec: Classroom Teaching Session, Phase 1)
  const [session, setSession] = useState<TeachingSession | null>(null);
  const [selectedClassId, setSelectedClassId] = useState("");
  const [sessionBusy, setSessionBusy] = useState(false);
  const [activeSlideId, setActiveSlideId] = useState<string | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      setForbidden(false);
      try {
        const [courses, mods, progress] = await Promise.all([
          api.get("/api/courses") as Promise<CourseInfo[]>,
          api.get(`/api/courses/${courseId}/modules`) as Promise<ModuleT[]>,
          api.get(`/api/courses/${courseId}/progress`) as Promise<{
            completed_module_ids: string[]; last_module_id: string | null; percent: number;
          }>,
        ]);
        if (cancelled) return;
        setCourse(courses.find(c => c.id === courseId) ?? null);
        setModules(mods);
        setCompletedIds(new Set(progress.completed_module_ids));
        // Priority: an explicit ?chapter= (from "Preview as student") wins,
        // then resume where the student last left off, then just the first chapter.
        const requested = new URLSearchParams(window.location.search).get("chapter");
        const resumeId = progress.last_module_id;
        const initial = [requested, resumeId].find(id => id && mods.some(m => m.id === id)) ?? mods[0]?.id ?? null;
        setActiveId(initial);
      } catch (e: any) {
        if (cancelled) return;
        if (e.status === 403) setForbidden(true);
        else toast.error(e.message || "Erreur de chargement");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [user, courseId]);

  // Marks the chapter the student just opened as "visited" — this is what
  // both drives the completion checkmarks and lets them resume here next time.
  // Fire-and-forget: a failure here shouldn't block reading.
  useEffect(() => {
    if (!activeId || loading) return;
    api.post(`/api/courses/${courseId}/modules/${activeId}/progress`, {})
      .then(() => {
        setCompletedIds(prev => {
          if (prev.has(activeId)) return prev;
          const next = new Set(prev); next.add(activeId);
          return next;
        });
      })
      .catch(() => {}); // e.g. professor previewing their own course — server just no-ops
  }, [activeId, loading, courseId]);

  // A module switch means whatever slide was showing no longer applies —
  // the position PATCH below should reflect the new module, not a stale slide.
  useEffect(() => { setActiveSlideId(null); }, [activeId]);

  // Session recovery (spec §21): on load, check whether this professor
  // already has an ACTIVE session for one of this course's assigned
  // classes — a refresh/reconnect must never silently drop it.
  useEffect(() => {
    if (isStudentView || loading || !course?.assigned_classes?.length) return;
    let cancelled = false;
    (async () => {
      const found = await Promise.all(
        course.assigned_classes!.map(c =>
          api.get(`/api/teaching-sessions/active?course_id=${courseId}&class_id=${c.id}`).catch(() => null)
        )
      );
      const active = (found.find(Boolean) as TeachingSession | undefined) ?? null;
      if (!cancelled && active) {
        setSession(active);
        setSelectedClassId(active.class_id);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isStudentView, loading, course?.id]);

  // Live timer while a session is active.
  useEffect(() => {
    if (!session || session.status !== "active") return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [session]);

  const activeIndex = modules.findIndex(m => m.id === activeId);
  const active = activeIndex >= 0 ? modules[activeIndex] : null;
  const progressPercent = modules.length ? Math.round((completedIds.size / modules.length) * 100) : 0;
  // A chapter authored in the visual editor carries its own slides — that's
  // what students see. Chapters never touched in the editor still fall back
  // to the plain generated markdown, so nothing regresses for older content.
  const activeSlides = active?.lessons?.[0]?.slides;
  const hasSlides = !!activeSlides && activeSlides.length > 0;
  const activeHtml = useMemo(() => {
    if (hasSlides) return "";
    const content = active?.lessons?.[0]?.content;
    if (!content) return "";
    return renderLessonHtml(content, active!.lessons[0].images || []);
  }, [active, hasSlides]);

  // {module_id, lesson_id, slide_id} for wherever the reader is right now —
  // what a teaching session records as start/current/end position (spec §4).
  const currentPos: ContentPosition = active
    ? { module_id: active.id, lesson_id: active.lessons[0]?.id ?? null, slide_id: hasSlides ? activeSlideId : null }
    : null;

  // Push the position to the active session as the professor navigates —
  // overwrites in place server-side, never one row per slide (spec §7).
  useEffect(() => {
    if (!session || session.status !== "active" || !currentPos) return;
    api.patch(`/api/teaching-sessions/${session.id}/position`, { position: currentPos }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session?.id, currentPos?.module_id, currentPos?.lesson_id, currentPos?.slide_id]);

  async function handleStartSession() {
    if (!selectedClassId || !course) return;
    setSessionBusy(true);
    try {
      const s = await api.post("/api/teaching-sessions", {
        course_id: course.id,
        class_id: selectedClassId,
        start_position: currentPos,
      }) as TeachingSession;
      setSession(s);
      toast.success(lang === "fr" ? "Séance démarrée" : "Session started");
    } catch (e: any) {
      toast.error(e.message || (lang === "fr" ? "Erreur" : "Error"));
    } finally {
      setSessionBusy(false);
    }
  }

  async function handleEndSession() {
    if (!session) return;
    setSessionBusy(true);
    try {
      const s = await api.post(`/api/teaching-sessions/${session.id}/end`, { end_position: currentPos }) as TeachingSession;
      setSession(null);
      const dur = formatDuration(s.duration_seconds ?? 0, lang);
      toast.success(lang === "fr" ? `Séance terminée — durée ${dur}` : `Session ended — ${dur}`);
    } catch (e: any) {
      toast.error(e.message || (lang === "fr" ? "Erreur" : "Error"));
    } finally {
      setSessionBusy(false);
    }
  }

  if (!user) return null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Link to="/dashboard/courses" className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-3.5 w-3.5" />{lang === "fr" ? "Retour aux cours" : "Back to courses"}
        </Link>
      </div>

      <PageHead
        eyebrow={course?.code || ""}
        title={course?.title || (loading ? "…" : (lang === "fr" ? "Cours introuvable" : "Course not found"))}
        sub={course?.semester || ""}
      />

      {isStudentView && !loading && !forbidden && modules.length > 0 && (
        <div className="dash-card px-4 py-3 flex items-center gap-3">
          <span className="text-xs font-semibold text-muted-foreground shrink-0">
            {lang === "fr" ? "Progression" : "Progress"} · {completedIds.size}/{modules.length}
          </span>
          <div className="flex-1 h-1.5 rounded-full bg-muted overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${progressPercent}%`, background: "var(--pal-primary, #2F6F5E)" }}
            />
          </div>
          <span className="text-xs tabular-nums text-muted-foreground shrink-0">{progressPercent}%</span>
        </div>
      )}

      {!isStudentView && !loading && !forbidden && modules.length > 0 && (
        <div className="dash-card px-4 py-3" data-testid="teaching-session-panel" data-session-status={session ? "active" : "idle"}>
          {session ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="chip-c chip-c-green inline-flex items-center gap-1.5 shrink-0">
                <span className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ background: "currentColor" }} />
                {lang === "fr" ? "Séance en cours" : "Session active"}
              </span>
              <span className="text-xs text-muted-foreground shrink-0">
                {lang === "fr" ? "Démarrée à" : "Started"}{" "}
                {new Date(session.started_at).toLocaleTimeString(lang === "fr" ? "fr-FR" : "en-US", { hour: "2-digit", minute: "2-digit" })}
              </span>
              <span className="text-xs font-mono font-semibold tabular-nums shrink-0">
                {formatDuration(Math.max(0, Math.floor((now - new Date(session.started_at).getTime()) / 1000)), lang)}
              </span>
              {active && (
                <span className="text-xs text-muted-foreground truncate min-w-0">
                  {(lang === "fr" ? "Position : " : "Position: ") + active.title}
                </span>
              )}
              <button
                className="btn-c btn-c-danger btn-c-sm ml-auto shrink-0"
                disabled={sessionBusy}
                onClick={handleEndSession}
                data-testid="end-session-btn"
              >
                <Square size={13} strokeWidth={2} />{lang === "fr" ? "Terminer la séance" : "End session"}
              </button>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-semibold text-muted-foreground shrink-0">
                {lang === "fr" ? "Démarrer une séance en classe" : "Start a classroom session"}
              </span>
              {(course?.assigned_classes?.length ?? 0) > 0 ? (
                <>
                  <select
                    className="text-xs rounded-lg border border-border px-2 py-1.5 bg-transparent"
                    value={selectedClassId}
                    onChange={e => setSelectedClassId(e.target.value)}
                    aria-label={lang === "fr" ? "Choisir une classe" : "Choose a class"}
                    data-testid="session-class-select"
                  >
                    <option value="">{lang === "fr" ? "Choisir une classe…" : "Choose a class…"}</option>
                    {course!.assigned_classes!.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  <button
                    className="btn-c btn-c-primary btn-c-sm"
                    disabled={!selectedClassId || sessionBusy}
                    onClick={handleStartSession}
                    data-testid="start-session-btn"
                  >
                    <Play size={13} strokeWidth={2} />{lang === "fr" ? "Démarrer la séance" : "Start session"}
                  </button>
                </>
              ) : (
                <span className="text-xs text-muted-foreground">
                  {lang === "fr" ? "Aucune classe assignée à ce cours." : "No class assigned to this course."}
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
      ) : forbidden ? (
        <div className="dash-card">
          <EmptyHint icon={<BookOpen size={28} strokeWidth={1.7} />} text={lang === "fr" ? "Vous n'avez pas accès à ce cours." : "You don't have access to this course."} />
        </div>
      ) : modules.length === 0 ? (
        <div className="dash-card">
          <EmptyHint
            icon={<BookOpen size={28} strokeWidth={1.7} />}
            text={lang === "fr" ? "Aucun chapitre publié pour ce cours pour le moment." : "No published chapter for this course yet."}
          />
        </div>
      ) : (
        <div className="grid gap-4" style={{ gridTemplateColumns: "260px minmax(0,1fr)" }}>
          {/* Chapter list */}
          <nav className="dash-card p-2 space-y-1 self-start">
            {modules.map((m, i) => (
              <button
                key={m.id}
                onClick={() => setActiveId(m.id)}
                className="w-full text-left rounded-lg px-3 py-2 text-sm transition-colors flex items-center gap-2"
                style={{
                  background: m.id === activeId ? "var(--pal-pale, oklch(94% 0.025 165))" : "transparent",
                  color: m.id === activeId ? "var(--pal-ink, oklch(22% 0.025 175))" : "var(--pal-muted, oklch(48% 0.02 180))",
                  fontWeight: m.id === activeId ? 700 : 500,
                }}
              >
                <span className="tabular-nums opacity-60">{String(i + 1).padStart(2, "0")}</span>
                <span className="flex-1 min-w-0 truncate">{m.title}</span>
                {isStudentView && completedIds.has(m.id) && (
                  <Check size={13} strokeWidth={2.5} className="shrink-0" style={{ color: "var(--pal-primary, #2F6F5E)" }} />
                )}
              </button>
            ))}
          </nav>

          {/* Reading pane */}
          <div className="dash-card p-6 min-w-0">
            {active && (
              <>
                <p className="text-xs font-mono font-semibold text-muted-foreground uppercase tracking-wider mb-1">
                  {lang === "fr" ? "Chapitre" : "Chapter"} {String(activeIndex + 1).padStart(2, "0")}
                </p>
                <h2 className="h-serif mb-1" style={{ fontSize: 26 }}>{active.title}</h2>
                {active.objectives && <p className="text-sm text-muted-foreground italic mb-5">{active.objectives}</p>}
                {hasSlides ? (
                  <SlideDeckViewer slides={activeSlides!} onIndexChange={(_, slide) => setActiveSlideId(slide.id)} />
                ) : activeHtml ? (
                  <div className="reader-content" dangerouslySetInnerHTML={{ __html: activeHtml }} />
                ) : (
                  <p className="text-sm text-muted-foreground">{lang === "fr" ? "Contenu indisponible." : "Content unavailable."}</p>
                )}

                <div className="flex items-center justify-between mt-8 pt-5 border-t border-border">
                  <button
                    className="btn-c btn-c-ghost btn-c-sm"
                    disabled={activeIndex <= 0}
                    onClick={() => setActiveId(modules[activeIndex - 1].id)}
                    data-testid="chapter-prev"
                  >
                    <ChevronLeft size={14} strokeWidth={1.7} />{lang === "fr" ? "Précédent" : "Previous"}
                  </button>
                  <button
                    className="btn-c btn-c-primary btn-c-sm"
                    disabled={activeIndex >= modules.length - 1}
                    onClick={() => setActiveId(modules[activeIndex + 1].id)}
                    data-testid="chapter-next"
                  >
                    {lang === "fr" ? "Suivant" : "Next"}<ArrowRight size={14} strokeWidth={1.7} />
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <style>{`
        .reader-content { font-size: 14.5px; line-height: 1.7; color: var(--pal-ink, oklch(22% 0.025 175)); }
        .reader-content h2, .reader-content h3 { font-family: "Cormorant Garamond", serif; margin: 1.3em 0 0.4em; color: var(--pal-ink, oklch(22% 0.025 175)); }
        .reader-content h2 { font-size: 22px; } .reader-content h3 { font-size: 18px; }
        .reader-content p { margin: 0 0 1em; }
        .reader-content ul, .reader-content ol { margin: 0 0 1em; padding-left: 1.3em; }
        .reader-content li { margin-bottom: 0.35em; }
        .reader-content strong { font-weight: 700; }
        .reader-content table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 13.5px; }
        .reader-content th, .reader-content td { border: 1px solid var(--pal-line-soft, oklch(88% 0.015 170)); padding: 6px 10px; text-align: left; }
        .reader-content th { background: var(--pal-cream, oklch(97% 0.012 90)); font-weight: 700; }
        .reader-image { margin: 1.2em 0; }
        .reader-image img { max-width: 100%; border-radius: 10px; border: 1px solid var(--pal-line-soft, oklch(88% 0.015 170)); }
        .reader-image figcaption { font-size: 12px; color: var(--pal-muted, oklch(48% 0.02 180)); margin-top: 6px; font-style: italic; }
        .reader-diagram { margin: 1.2em 0; }
        .reader-diagram-title { font-size: 12px; font-weight: 700; color: var(--pal-primary, oklch(48% 0.085 175)); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px; }
        .reader-diagram-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; }
        .reader-diagram-card { border: 1px solid var(--pal-line-soft, oklch(88% 0.015 170)); background: var(--pal-cream, oklch(97% 0.012 90)); border-radius: 10px; padding: 12px; font-size: 13px; }
        .reader-diagram-card ul { margin: 6px 0 0; padding-left: 1.1em; }
      `}</style>
    </div>
  );
}
