import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Layers, BookOpen, CalendarCheck, FileStack } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip } from "recharts";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";
import { CountUp } from "@/components/CountUp";

export const Route = createFileRoute("/dashboard/kpis-production")({
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
  component: ProductionPage,
});

const C = {
  ink: "oklch(22% 0.025 175)", muted: "oklch(48% 0.02 180)", line: "oklch(88% 0.015 170)", paper: "oklch(99% 0.005 160)",
  primary: "oklch(48% 0.085 175)", mid: "oklch(62% 0.085 170)",
};
const sans = '"Manrope", system-ui, sans-serif';
const TT: React.CSSProperties = { fontFamily: sans, fontSize: 12.5, borderRadius: 12, border: `1px solid ${C.line}`, background: C.paper, boxShadow: "0 8px 32px oklch(0% 0 0/.12)", padding: "8px 12px" };
const MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

type Course = { id: string; title: string; created_at: string; professor_name: string; module_count: number };
type SessionRow = { id: string; status: string; started_at: string };

function monthLabel(ym: string) {
  const [y, m] = ym.split("-");
  return `${MONTHS_SHORT[parseInt(m, 10) - 1]} ${y.slice(2)}`;
}
function monthKey(iso: string) {
  return iso.slice(0, 7);
}
function lastNMonths(n: number): string[] {
  const out: string[] = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    out.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`);
  }
  return out;
}

function KpiTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="dash-card" style={{ padding: "18px 20px", display: "flex", alignItems: "center", gap: 14 }}>
      <div style={{ width: 40, height: 40, borderRadius: 10, background: "var(--pal-pale)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--pal-primary)", flexShrink: 0 }}>
        {icon}
      </div>
      <div>
        <div style={{ fontSize: 22, fontWeight: 700, color: C.ink, fontFamily: sans, lineHeight: 1.1 }}><CountUp value={value} /></div>
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
      <div style={{ width: "100%", height: 260, marginTop: 10 }}>{children}</div>
    </div>
  );
}

export function ProductionPage() {
  const [courses, setCourses] = useState<Course[]>([]);
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const [c, s] = await Promise.all([
          api.get("/api/courses") as Promise<Course[]>,
          api.get("/api/teaching-sessions") as Promise<SessionRow[]>,
        ]);
        if (!cancelled) { setCourses(c); setSessions(s); }
      } catch (err: any) {
        if (!cancelled) toast.error(err?.message ?? "Erreur lors du chargement.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const totalModules = useMemo(() => courses.reduce((sum, c) => sum + (c.module_count || 0), 0), [courses]);
  const completedSessions = useMemo(() => sessions.filter(s => s.status === "completed"), [sessions]);

  const months = useMemo(() => lastNMonths(6), []);
  const coursesByMonth = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of courses) counts.set(monthKey(c.created_at), (counts.get(monthKey(c.created_at)) ?? 0) + 1);
    return months.map(m => ({ name: monthLabel(m), cours: counts.get(m) ?? 0 }));
  }, [courses, months]);
  const sessionsByMonth = useMemo(() => {
    const counts = new Map<string, number>();
    for (const s of completedSessions) counts.set(monthKey(s.started_at), (counts.get(monthKey(s.started_at)) ?? 0) + 1);
    return months.map(m => ({ name: monthLabel(m), seances: counts.get(m) ?? 0 }));
  }, [completedSessions, months]);

  return (
    <div style={{ fontFamily: sans }}>
      <PageHead
        eyebrow="Aperçu · KPIs"
        title="Production"
        sub="Volume de contenu créé et de formation dispensée, tous formateurs confondus."
      />

      {loading ? (
        <div className="dash-card" style={{ padding: 26 }}><div className="shimmer" style={{ height: 18, width: 220, borderRadius: 999 }} /></div>
      ) : courses.length === 0 && sessions.length === 0 ? (
        <div className="dash-card"><EmptyHint icon={<Layers size={26} strokeWidth={1.7} />} text="Aucune donnée de production pour l'instant." /></div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 20 }}>
            <KpiTile icon={<BookOpen size={19} strokeWidth={1.7} />} label="Cours créés" value={courses.length} />
            <KpiTile icon={<FileStack size={19} strokeWidth={1.7} />} label="Modules de contenu" value={totalModules} />
            <KpiTile icon={<CalendarCheck size={19} strokeWidth={1.7} />} label="Séances dispensées" value={completedSessions.length} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <ChartCard title="Cours créés" sub="Par mois, 6 derniers mois">
              <ResponsiveContainer>
                <BarChart data={coursesByMonth} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} width={30} allowDecimals={false} />
                  <Tooltip contentStyle={TT} formatter={(v: number) => [v, "Cours créés"]} />
                  <Bar dataKey="cours" fill={C.primary} radius={[5, 5, 0, 0]} animationDuration={900} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Séances dispensées" sub="Par mois, 6 derniers mois">
              <ResponsiveContainer>
                <BarChart data={sessionsByMonth} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={C.line} vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fontFamily: sans, fill: C.muted }} axisLine={false} tickLine={false} width={30} allowDecimals={false} />
                  <Tooltip contentStyle={TT} formatter={(v: number) => [v, "Séances"]} />
                  <Bar dataKey="seances" fill={C.mid} radius={[5, 5, 0, 0]} animationDuration={900} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </>
      )}
    </div>
  );
}
