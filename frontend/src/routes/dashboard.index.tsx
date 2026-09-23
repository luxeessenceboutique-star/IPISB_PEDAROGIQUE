import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { BookOpen, FileText, GraduationCap, CalendarDays, Bell, ChevronDown, ChevronRight, ArrowRight, Users, Activity, Home, Building2, TrendingUp } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { CountUp } from "@/components/CountUp";
import { StatCardsSkeleton, ListSkeleton } from "@/components/Skeletons";
import { PageHead, SectionLabel } from "@/components/dashboard/ui";
import { AgendaFormationPage } from "./dashboard.agenda-formation";
import { ProductionPage } from "./dashboard.kpis-production";
import { PerformancePage } from "./dashboard.performance";

export const Route = createFileRoute("/dashboard/")({
  component: DashboardHome,
});

type Stats = {
  courses: number;
  assignments: number;
  exams: number;
  events: number;
  unread: number;
  pending_grade: number;
};

type AssignmentAnalytic = {
  id: string;
  title: string;
  enrolled: number;
  submitted: number;
  avg_grade: number | null;
};

type ExamAnalytic = {
  id: string;
  title: string;
  enrolled: number;
  submitted: number;
  avg_score: number | null;
};

type CourseAnalytic = {
  course_id: string;
  course_title: string;
  enrolled_count: number;
  assignments: AssignmentAnalytic[];
  exams: ExamAnalytic[];
};

type AuditEntry = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
};

type AdminOverview = {
  total_students: number;
  students_by_class: { class_id: string; class_name: string; count: number }[];
  documents_total: number;
  documents_today: number;
  recent_activity: AuditEntry[];
};

async function fetchStats(userId: string, roles: string[]): Promise<Stats> {
  const now = new Date().toISOString();
  const isAdmin = roles.includes("admin");
  const isProf  = roles.includes("professor");

  const { count: unread = 0 } = await supabase
    .from("notifications").select("*", { count: "exact", head: true })
    .eq("user_id", userId).eq("read", false);

  if (isAdmin) {
    const [c, a, e, ev] = await Promise.all([
      supabase.from("courses").select("*", { count: "exact", head: true }),
      supabase.from("assignments").select("*", { count: "exact", head: true }),
      supabase.from("exams").select("*", { count: "exact", head: true }),
      supabase.from("calendar_events").select("*", { count: "exact", head: true }),
    ]);
    return { courses: c.count ?? 0, assignments: a.count ?? 0, exams: e.count ?? 0, events: ev.count ?? 0, unread: unread ?? 0, pending_grade: 0 };
  }

  if (isProf) {
    const { data: profCourses } = await supabase.from("courses").select("id").eq("professor_id", userId);
    const courseIds = profCourses?.map((c: any) => c.id) ?? [];
    if (!courseIds.length) return { courses: 0, assignments: 0, exams: 0, events: 0, unread: unread ?? 0, pending_grade: 0 };

    const [a, e, assignRows] = await Promise.all([
      supabase.from("assignments").select("*", { count: "exact", head: true }).in("course_id", courseIds),
      supabase.from("exams").select("*", { count: "exact", head: true }).in("course_id", courseIds),
      supabase.from("assignments").select("id").in("course_id", courseIds),
    ]);
    const assignIds = assignRows.data?.map((x: any) => x.id) ?? [];
    let pending_grade = 0;
    if (assignIds.length) {
      const { count } = await supabase.from("submissions").select("*", { count: "exact", head: true })
        .in("assignment_id", assignIds).is("grade", null);
      pending_grade = count ?? 0;
    }
    return { courses: courseIds.length, assignments: a.count ?? 0, exams: e.count ?? 0, events: 0, unread: unread ?? 0, pending_grade };
  }

  // Student
  const { data: enrollments } = await supabase.from("course_enrollments").select("course_id").eq("student_id", userId);
  const enrolledIds = enrollments?.map((e: any) => e.course_id) ?? [];
  if (!enrolledIds.length) return { courses: 0, assignments: 0, exams: 0, events: 0, unread: unread ?? 0, pending_grade: 0 };

  const [a, e, ev] = await Promise.all([
    supabase.from("assignments").select("*", { count: "exact", head: true }).in("course_id", enrolledIds).gt("due_date", now),
    supabase.from("exams").select("*", { count: "exact", head: true }).in("course_id", enrolledIds).eq("is_published", true),
    supabase.from("calendar_events").select("*", { count: "exact", head: true }).gt("start_time", now),
  ]);
  return { courses: enrolledIds.length, assignments: a.count ?? 0, exams: e.count ?? 0, events: ev.count ?? 0, unread: unread ?? 0, pending_grade: 0 };
}

function DashboardHome() {
  const { t, lang } = useI18n();
  const { user, roles } = useAuth();
  const isAdmin = roles.includes("admin");
  const isProf  = roles.includes("professor");
  const role    = isAdmin ? "admin" : isProf ? "professor" : "student";

  const canCreate = isAdmin || isProf;

  const showAgendaFormation = isAdmin;
  const showKpis = isAdmin || isProf;
  const extraTabsVisible = showAgendaFormation || showKpis;

  type OverviewTab = "apercu" | "agenda-formation" | "kpis";
  const [tab, setTab] = useState<OverviewTab>("apercu");
  const [kpiSub, setKpiSub] = useState<"production" | "performance">("production");

  const [stats,   setStats]   = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  const [analytics,        setAnalytics]        = useState<CourseAnalytic[]>([]);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);
  const [expanded,         setExpanded]         = useState<Record<string, boolean>>({});

  const [overview,        setOverview]        = useState<AdminOverview | null>(null);
  const [overviewLoading, setOverviewLoading] = useState(false);

  useEffect(() => {
    if (!user) return;
    fetchStats(user.id, roles)
      .then(setStats)
      .finally(() => setLoading(false));
  }, [user, roles]);

  // Admin real-time overview — effectifs, documents générés, activité récente.
  // Poll every 30s; a future iteration can swap this for a Supabase Realtime
  // subscription on the same tables (classes/documents/audit_log) for instant updates.
  useEffect(() => {
    if (!user || !isAdmin) return;
    setOverviewLoading(true);
    const load = () => api.get("/api/dashboard/admin-overview")
      .then((data: AdminOverview) => setOverview(data))
      .catch(() => setOverview(null))
      .finally(() => setOverviewLoading(false));
    load();
    const timer = setInterval(load, 30_000);
    return () => clearInterval(timer);
  }, [user, isAdmin]);

  useEffect(() => {
    if (!user || !canCreate) return;
    setAnalyticsLoading(true);
    api.get("/api/dashboard/analytics")
      .then((data: CourseAnalytic[]) => setAnalytics(data))
      .catch(() => setAnalytics([]))
      .finally(() => setAnalyticsLoading(false));
  }, [user, canCreate]);

  const cards = stats ? [
    { label: t("dash.courses"),     value: stats.courses,     to: "/dashboard/courses"     },
    { label: t("dash.assignments"), value: isProf && stats.pending_grade > 0 ? stats.pending_grade : stats.assignments, suffix: isProf && stats.pending_grade > 0 ? (lang === "fr" ? " à corriger" : " to grade") : "", to: "/dashboard/assignments" },
    { label: t("dash.exams"),       value: stats.exams,       to: "/dashboard/exams"       },
    { label: t("dash.agenda"),      value: stats.events,      to: "/dashboard/agenda"      },
  ] : [];

  const firstName = user?.user_metadata?.full_name?.split(" ")[0];
  const today = new Date().toLocaleDateString(
    lang === "ar" ? "ar-MA" : lang === "fr" ? "fr-FR" : "en-US",
    { weekday: "long", day: "numeric", month: "long", year: "numeric" },
  );

  return (
    <div className="space-y-6">
      <PageHead
        eyebrow={today}
        title={
          <span>
            {lang === "fr" ? "Bonjour" : lang === "ar" ? "مرحباً" : "Hello"}
            {firstName ? (
              <>
                , <em style={{ fontStyle: "italic", color: "var(--pal-primary)" }}>{firstName}</em>
              </>
            ) : null}
            .
          </span>
        }
        sub={lang === "fr"
          ? `Voici un aperçu de votre espace ${t(`dash.role.${role}`).toLowerCase()}.`
          : lang === "ar"
          ? `هذه نظرة عامة على فضائك.`
          : `Here's an overview of your ${t(`dash.role.${role}`).toLowerCase()} space.`}
        actions={
          <Link to="/dashboard/agenda" className="btn-c btn-c-primary">
            {lang === "fr" ? "Voir l'agenda" : lang === "ar" ? "عرض الجدول" : "View calendar"}
            <ArrowRight size={15} strokeWidth={1.7} />
          </Link>
        }
      />

      {extraTabsVisible && (
        <div style={{ display: "flex", gap: 6, marginBottom: 4, borderBottom: "1px solid var(--pal-line)", flexWrap: "wrap" }}>
          {([
            { key: "apercu" as const, label: lang === "fr" ? "Aperçu" : lang === "ar" ? "نظرة عامة" : "Overview", icon: Home, show: true },
            { key: "agenda-formation" as const, label: t("dash.agendaFormation"), icon: Building2, show: showAgendaFormation },
            { key: "kpis" as const, label: t("dash.kpis"), icon: TrendingUp, show: showKpis },
          ]).filter(x => x.show).map(x => {
            const active = tab === x.key;
            const Icon = x.icon;
            return (
              <button
                key={x.key}
                type="button"
                onClick={() => setTab(x.key)}
                style={{
                  display: "flex", alignItems: "center", gap: 7,
                  padding: "10px 16px", marginBottom: -1,
                  border: "none", borderBottom: active ? "2px solid var(--pal-primary)" : "2px solid transparent",
                  background: "transparent", cursor: "pointer",
                  fontFamily: '"Manrope", system-ui, sans-serif', fontSize: 13.5, fontWeight: active ? 700 : 600,
                  color: active ? "var(--pal-ink)" : "var(--pal-muted)",
                }}
              >
                <Icon size={15} strokeWidth={1.7} />
                {x.label}
              </button>
            );
          })}
        </div>
      )}

      {tab === "agenda-formation" && showAgendaFormation && <AgendaFormationPage />}

      {tab === "kpis" && showKpis && (
        <div>
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <button
              type="button"
              onClick={() => setKpiSub("production")}
              className={`chip-c ${kpiSub === "production" ? "chip-c-green" : ""}`}
              style={{ cursor: "pointer", border: "none" }}
            >
              {t("dash.kpis.production")}
            </button>
            <button
              type="button"
              onClick={() => setKpiSub("performance")}
              className={`chip-c ${kpiSub === "performance" ? "chip-c-green" : ""}`}
              style={{ cursor: "pointer", border: "none" }}
            >
              {t("dash.kpis.performance")}
            </button>
          </div>
          {kpiSub === "production" ? <ProductionPage /> : <PerformancePage />}
        </div>
      )}

      {tab === "apercu" && (
      <>
      {loading ? (
        <StatCardsSkeleton />
      ) : (
        <div className="dash-card card-pop grid grid-cols-2 lg:grid-cols-4 py-5">
          {cards.map((s, i) => (
            <Link
              key={s.label}
              to={s.to as "/dashboard"}
              className={`flex flex-col gap-2 px-6 py-1 text-start no-underline transition-opacity hover:opacity-75 ${i % 2 === 1 ? "border-s" : i > 0 ? "lg:border-s" : ""}`}
              style={{ borderColor: "var(--pal-line-soft)" }}
            >
              <span className="stat-num">
                <CountUp value={typeof s.value === "number" ? s.value : 0} duration={900} />
                {"suffix" in s && s.suffix ? <span style={{ fontSize: 16 }}>{s.suffix}</span> : null}
              </span>
              <span className="eyebrow" style={{ letterSpacing: ".14em" }}>{s.label}</span>
            </Link>
          ))}
        </div>
      )}

      {stats && stats.unread > 0 && (
        <Link to="/dashboard/notifications" className="block no-underline">
          <div className="dash-card lift-c flex items-center gap-3 px-5 py-4">
            <div
              className="flex h-9 w-9 items-center justify-center rounded-full"
              style={{ background: "var(--pal-pale)", color: "var(--pal-primary-deep)" }}
            >
              <Bell className="h-4 w-4" strokeWidth={1.7} />
            </div>
            <div>
              <p className="text-sm font-bold" style={{ color: "var(--pal-ink)" }}>
                {stats.unread}{" "}
                {lang === "fr" ? stats.unread === 1 ? "nouvelle notification" : "nouvelles notifications" : stats.unread === 1 ? "new notification" : "new notifications"}
              </p>
              <p className="text-xs" style={{ color: "var(--pal-muted)" }}>
                {lang === "fr" ? "Cliquez pour les consulter" : "Click to view them"}
              </p>
            </div>
            <span
              className="ms-auto flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-extrabold"
              style={{ background: "var(--pal-danger)", color: "var(--pal-paper)" }}
            >
              {stats.unread}
            </span>
          </div>
        </Link>
      )}

      <div>
        <SectionLabel>{lang === "fr" ? "Accès rapide" : lang === "ar" ? "وصول سريع" : "Quick access"}</SectionLabel>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[
            { to: "/dashboard/courses",      title: lang === "fr" ? "Accéder aux cours" : "Go to Courses",      desc: lang === "fr" ? isProf ? "Gérez vos cours et les inscriptions." : "Inscrivez-vous à vos cours." : isProf ? "Manage your courses and enrollments." : "Enroll in your courses.",        icon: BookOpen },
            { to: "/dashboard/exams",        title: lang === "fr" ? "Examens QCM" : "MCQ Exams",               desc: lang === "fr" ? isProf ? "Créez et publiez des examens QCM." : "Passez vos examens disponibles." : isProf ? "Create and publish MCQ exams." : "Take your available exams.",         icon: GraduationCap },
            { to: "/dashboard/agenda",       title: lang === "fr" ? "Agenda" : "Calendar",                      desc: lang === "fr" ? "Visualisez tous les événements du calendrier." : "View all calendar events.",                                                                                      icon: CalendarDays },
          ].map((item, i) => (
            <Link key={item.to} to={item.to as "/dashboard"} className="no-underline">
              <div className="dash-card lift-c card-pop flex items-start gap-4 p-5" style={{ animationDelay: `${i * 50}ms` }}>
                <div
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                  style={{ background: "var(--pal-pale)", color: "var(--pal-primary-deep)" }}
                >
                  <item.icon className="h-5 w-5" strokeWidth={1.7} />
                </div>
                <div>
                  <h3 className="h-serif" style={{ fontSize: 19, lineHeight: 1.2 }}>{item.title}</h3>
                  <p className="mt-1 text-sm" style={{ color: "var(--pal-muted)" }}>{item.desc}</p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* ── Admin — L2 Gestion Administrative real-time overview ────────── */}
      {isAdmin && (
        <div>
          <SectionLabel>Vue d'ensemble administrative</SectionLabel>

          {overviewLoading && !overview ? (
            <ListSkeleton rows={2} />
          ) : overview ? (
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="dash-card p-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full" style={{ background: "var(--pal-pale)", color: "var(--pal-primary-deep)" }}>
                    <Users className="h-4 w-4" strokeWidth={1.7} />
                  </div>
                  <span className="eyebrow">Effectifs</span>
                </div>
                <div className="stat-num mt-3">
                  <CountUp value={overview.total_students} duration={700} />
                </div>
                <div className="mt-3 flex flex-col gap-1.5">
                  {overview.students_by_class.slice(0, 5).map(c => (
                    <div key={c.class_id} className="flex items-center justify-between text-xs" style={{ color: "var(--pal-muted)" }}>
                      <span>{c.class_name}</span>
                      <span style={{ fontWeight: 700, color: "var(--pal-ink)" }}>{c.count}</span>
                    </div>
                  ))}
                  {overview.students_by_class.length === 0 && (
                    <span className="text-xs" style={{ color: "var(--pal-muted)" }}>Aucune classe.</span>
                  )}
                </div>
              </div>

              <div className="dash-card p-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full" style={{ background: "var(--pal-pale)", color: "var(--pal-primary-deep)" }}>
                    <FileText className="h-4 w-4" strokeWidth={1.7} />
                  </div>
                  <span className="eyebrow">Documents générés</span>
                </div>
                <div className="stat-num mt-3">
                  <CountUp value={overview.documents_total} duration={700} />
                </div>
                <div className="mt-3 text-xs" style={{ color: "var(--pal-muted)" }}>
                  {overview.documents_today} aujourd'hui
                </div>
              </div>

              <div className="dash-card p-5">
                <div className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-full" style={{ background: "var(--pal-pale)", color: "var(--pal-primary-deep)" }}>
                    <Activity className="h-4 w-4" strokeWidth={1.7} />
                  </div>
                  <span className="eyebrow">Activité récente</span>
                </div>
                <div className="mt-3 flex flex-col gap-1.5 max-h-[104px] overflow-y-auto">
                  {overview.recent_activity.slice(0, 5).map(a => (
                    <div key={a.id} className="text-xs" style={{ color: "var(--pal-muted)" }}>
                      <span style={{ fontWeight: 700, color: "var(--pal-ink)" }}>{a.action}</span>
                      {" · "}
                      {new Date(a.created_at).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                    </div>
                  ))}
                  {overview.recent_activity.length === 0 && (
                    <span className="text-xs" style={{ color: "var(--pal-muted)" }}>Aucune activité récente.</span>
                  )}
                </div>
              </div>
            </div>
          ) : null}
        </div>
      )}

      {/* ── Professor / Admin Analytics ─────────────────────────────────── */}
      {canCreate && (
        <div className="space-y-4">
          <SectionLabel>
            {lang === "fr" ? "Analytiques des cours" : "Course Analytics"}
          </SectionLabel>

          {analyticsLoading ? (
            <ListSkeleton rows={3} />
          ) : analytics.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {lang === "fr" ? "Aucun cours trouvé." : "No courses found."}
            </p>
          ) : (
            <div className="space-y-3">
              {analytics.map((course) => {
                const isOpen = !!expanded[course.course_id];
                return (
                  <div
                    key={course.course_id}
                    className="dash-card overflow-hidden"
                  >
                    {/* Course header — click to expand */}
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded((prev) => ({ ...prev, [course.course_id]: !prev[course.course_id] }))
                      }
                      className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-muted/40 transition-colors"
                    >
                      <div className="flex items-center gap-3">
                        {isOpen
                          ? <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                          : <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0" />
                        }
                        <span className="font-display font-semibold">{course.course_title}</span>
                        <span className="text-sm text-muted-foreground">
                          {course.enrolled_count}{" "}
                          {lang === "fr" ? "étudiant(s) inscrit(s)" : "enrolled student(s)"}
                        </span>
                      </div>
                    </button>

                    {isOpen && (
                      <div className="px-5 pb-5 space-y-5 border-t border-border pt-4">
                        {/* Assignments table */}
                        {course.assignments.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                              {lang === "fr" ? "Contrôle continu" : "Continuous assessment"}
                            </p>
                            <div className="overflow-x-auto rounded-xl border border-border">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="border-b border-border bg-muted/50">
                                    <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                                      {lang === "fr" ? "Titre" : "Title"}
                                    </th>
                                    <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                                      {lang === "fr" ? "Soumissions" : "Submissions"}
                                    </th>
                                    <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                                      {lang === "fr" ? "Note moyenne" : "Avg Grade"}
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {course.assignments.map((a, idx) => (
                                    <tr
                                      key={a.id}
                                      className={idx % 2 === 0 ? "bg-card" : "bg-muted/20"}
                                    >
                                      <td className="px-4 py-2 font-medium">{a.title}</td>
                                      <td className="px-4 py-2 text-center text-muted-foreground">
                                        {a.submitted}/{a.enrolled}
                                      </td>
                                      <td className="px-4 py-2 text-center font-mono text-sm">
                                        {a.avg_grade !== null ? `${a.avg_grade}/20` : "—"}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {/* Exams table */}
                        {course.exams.length > 0 && (
                          <div>
                            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                              {lang === "fr" ? "Examens" : "Exams"}
                            </p>
                            <div className="overflow-x-auto rounded-xl border border-border">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="border-b border-border bg-muted/50">
                                    <th className="px-4 py-2 text-left font-medium text-muted-foreground">
                                      {lang === "fr" ? "Titre" : "Title"}
                                    </th>
                                    <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                                      {lang === "fr" ? "Soumissions" : "Submissions"}
                                    </th>
                                    <th className="px-4 py-2 text-center font-medium text-muted-foreground">
                                      {lang === "fr" ? "Score moyen" : "Avg Score"}
                                    </th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {course.exams.map((e, idx) => (
                                    <tr
                                      key={e.id}
                                      className={idx % 2 === 0 ? "bg-card" : "bg-muted/20"}
                                    >
                                      <td className="px-4 py-2 font-medium">{e.title}</td>
                                      <td className="px-4 py-2 text-center text-muted-foreground">
                                        {e.submitted}/{e.enrolled}
                                      </td>
                                      <td className="px-4 py-2 text-center font-mono text-sm">
                                        {e.avg_score !== null ? `${e.avg_score}%` : "—"}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        )}

                        {course.assignments.length === 0 && course.exams.length === 0 && (
                          <p className="text-sm text-muted-foreground">
                            {lang === "fr"
                              ? "Aucun contrôle continu ni examen pour ce cours."
                              : "No continuous assessment or exams for this course."}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
      </>
      )}
    </div>
  );
}
