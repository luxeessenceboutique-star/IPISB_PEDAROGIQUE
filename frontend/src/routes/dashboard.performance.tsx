import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { TrendingUp, GraduationCap, ClipboardList, Users, MessageSquare } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";
import { CountUp } from "@/components/CountUp";

export const Route = createFileRoute("/dashboard/performance")({
  beforeLoad: async () => {
    const { data: sess } = await supabase.auth.getSession();
    if (!sess.session) throw redirect({ to: "/auth" });
    const { data } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", sess.session.user.id)
      .in("role", ["admin", "professor"]);
    if (!data?.length) throw redirect({ to: "/dashboard" });
  },
  component: PerformancePage,
});

const C = {
  ink: "oklch(22% 0.025 175)", muted: "oklch(48% 0.02 180)", line: "oklch(88% 0.015 170)", paper: "oklch(99% 0.005 160)",
  primary: "oklch(48% 0.085 175)", mid: "oklch(62% 0.085 170)",
};
const sans = '"Manrope", system-ui, sans-serif';
const TT: React.CSSProperties = { fontFamily: sans, fontSize: 12.5, borderRadius: 12, border: `1px solid ${C.line}`, background: C.paper, boxShadow: "0 8px 32px oklch(0% 0 0/.12)", padding: "8px 12px" };

type CourseAnalytics = {
  course_id: string; course_title: string; enrolled_count: number;
  assignments: { id: string; title: string; enrolled: number; submitted: number; avg_grade: number | null }[];
  exams: { id: string; title: string; enrolled: number; submitted: number; avg_score: number | null }[];
};
type Comparison = { id: string; name: string; session_count: number; average: number | null };
type SessionsSummary = {
  total_sessions: number; completed_sessions: number; total_invited: number; total_responses: number;
  response_rate: number; overall_average: number | null;
  by_professor: Comparison[]; by_course: Comparison[];
};

function mean(vals: (number | null)[]): number | null {
  const nums = vals.filter((v): v is number => v != null);
  return nums.length ? Math.round((nums.reduce((a, b) => a + b, 0) / nums.length) * 10) / 10 : null;
}

function KpiTile({ icon, label, value, suffix }: { icon: React.ReactNode; label: string; value: number | null; suffix?: string }) {
  return (
    <div className="dash-card" style={{ padding: "18px 20px", display: "flex", alignItems: "center", gap: 14 }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--pal-pale)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--pal-primary)", flexShrink: 0 }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, color: C.ink, fontFamily: sans, lineHeight: 1.1 }}>
          {value != null ? <CountUp value={`${value}${suffix ?? ""}`} /> : "—"}
        </div>
        <div style={{ fontSize: 11.5, color: C.muted, marginTop: 2 }}>{label}</div>
      </div>
    </div>
  );
}

function ChartCard({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className="dash-card" style={{ padding: "20px 22px" }}>
      <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase", color: C.muted, fontFamily: sans }}>{title}</div>
      {sub && <div style={{ fontSize: 11.5, color: C.muted, marginTop: 3, marginBottom: 4 }}>{sub}</div>}
      <div style={{ width: "100%", height: 280, marginTop: 10 }}>{children}</div>
    </div>
  );
}

export function PerformancePage() {
  const { roles } = useAuth();
  const isAdmin = roles.includes("admin");
  const [courses, setCourses] = useState<CourseAnalytics[]>([]);
  const [summary, setSummary] = useState<SessionsSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = (await api.get("/api/dashboard/analytics")) as CourseAnalytics[];
        if (!cancelled) setCourses(data);
      } catch (err: any) {
        if (!cancelled) toast.error(err?.message ?? "Erreur lors du chargement.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!isAdmin) return;
    let cancelled = false;
    (async () => {
      try {
        const data = (await api.get("/api/teaching-sessions/analytics/summary")) as SessionsSummary;
        if (!cancelled) setSummary(data);
      } catch {
        // silencieux — les indicateurs académiques ci-dessus restent valables sans ça
      }
    })();
    return () => { cancelled = true; };
  }, [isAdmin]);

  const perCourseExams = useMemo(() =>
    courses.map(c => ({ name: c.course_title, moyenne: mean(c.exams.map(e => e.avg_score)) }))
      .filter(r => r.moyenne != null), [courses]);
  const perCourseAssignments = useMemo(() =>
    courses.map(c => ({ name: c.course_title, moyenne: mean(c.assignments.map(a => a.avg_grade)) }))
      .filter(r => r.moyenne != null), [courses]);

  const overallExamAvg = useMemo(() => mean(courses.flatMap(c => c.exams.map(e => e.avg_score))), [courses]);
  const overallAssignAvg = useMemo(() => mean(courses.flatMap(c => c.assignments.map(a => a.avg_grade))), [courses]);
  const totalEnrolled = useMemo(() => courses.reduce((sum, c) => sum + c.enrolled_count, 0), [courses]);

  const profChart = useMemo(() => (summary?.by_professor ?? [])
    .filter(p => p.average != null)
    .map(p => ({ name: p.name, moyenne: p.average as number })), [summary]);

  return (
    <div style={{ fontFamily: sans }}>
      <PageHead
        eyebrow="Aperçu"
        title="Graphes de performance"
        sub="Indicateurs de réussite et de suivi, tous groupes confondus."
      />

      {loading ? (
        <div className="dash-card" style={{ padding: 26 }}><div className="shimmer" style={{ height: 18, width: 220, borderRadius: 999 }} /></div>
      ) : courses.length === 0 ? (
        <div className="dash-card"><EmptyHint icon={<TrendingUp size={26} strokeWidth={1.7} />} text="Aucune donnée de performance pour l'instant." /></div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 20 }}>
            <KpiTile icon={<GraduationCap size={19} strokeWidth={1.7} />} label="Moyenne examens (%)" value={overallExamAvg} suffix="%" />
            <KpiTile icon={<ClipboardList size={19} strokeWidth={1.7} />} label="Moyenne contrôle continu" value={overallAssignAvg} />
            <KpiTile icon={<Users size={19} strokeWidth={1.7} />} label="Stagiaires suivis" value={totalEnrolled} />
            {summary && (
              <KpiTile icon={<MessageSquare size={19} strokeWidth={1.7} />} label="Satisfaction séances (%)" value={summary.overall_average != null ? Math.round(summary.overall_average * 20) : null} suffix="%" />
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <ChartCard title="Moyenne aux examens" sub="Par cours, en %">
              {perCourseExams.length === 0 ? (
                <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontSize: 13 }}>Aucun examen noté.</div>
              ) : (
                <ResponsiveContainer>
                  <BarChart data={perCourseExams} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} interval={0} angle={-20} textAnchor="end" height={52} />
                    <YAxis tick={{ fontSize: 11, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} width={36} domain={[0, 100]} />
                    <Tooltip contentStyle={TT} formatter={(v: number) => [`${v}%`, "Moyenne"]} />
                    <Bar dataKey="moyenne" fill={C.primary} radius={[5, 5, 0, 0]} animationDuration={900} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>

            <ChartCard title="Moyenne contrôle continu" sub="Par cours">
              {perCourseAssignments.length === 0 ? (
                <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: C.muted, fontSize: 13 }}>Aucun devoir noté.</div>
              ) : (
                <ResponsiveContainer>
                  <BarChart data={perCourseAssignments} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={C.line} vertical={false} />
                    <XAxis dataKey="name" tick={{ fontSize: 10, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} interval={0} angle={-20} textAnchor="end" height={52} />
                    <YAxis tick={{ fontSize: 11, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} width={36} />
                    <Tooltip contentStyle={TT} formatter={(v: number) => [v, "Moyenne"]} />
                    <Bar dataKey="moyenne" fill={C.mid} radius={[5, 5, 0, 0]} animationDuration={900} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>

          {isAdmin && summary && profChart.length > 0 && (
            <ChartCard title="Satisfaction moyenne par formateur" sub="Retours des stagiaires en fin de séance, sur 5">
              <ResponsiveContainer>
                <BarChart data={profChart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 10, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} interval={0} angle={-20} textAnchor="end" height={52} />
                  <YAxis tick={{ fontSize: 11, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} width={30} domain={[0, 5]} />
                  <Tooltip contentStyle={TT} formatter={(v: number) => [`${v}/5`, "Moyenne"]} />
                  <Bar dataKey="moyenne" fill={C.primary} radius={[5, 5, 0, 0]} animationDuration={900} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          )}
        </>
      )}
    </div>
  );
}
