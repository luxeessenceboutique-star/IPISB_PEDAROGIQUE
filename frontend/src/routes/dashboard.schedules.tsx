import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, CalendarClock, MapPin, Repeat, ClipboardCheck, X } from "lucide-react";
import { PageHead, SectionLabel, EmptyHint } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/schedules")({
  beforeLoad: async () => {
    const { data: sess } = await supabase.auth.getSession();
    if (!sess.session) throw redirect({ to: "/auth" });
    const { data } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", sess.session.user.id)
      .eq("role", "admin");
    if (!data?.length) throw redirect({ to: "/dashboard" });
  },
  component: SchedulesPage,
});

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  muted:   "oklch(48% 0.02 180)",
  primary: "oklch(48% 0.085 175)",
  line:    "oklch(88% 0.015 170)",
  paper:   "oklch(99% 0.005 160)",
  danger:  "oklch(64% 0.18 25)",
};
const sans = '"Manrope", system-ui, sans-serif';
const WEEKDAYS = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

type ClassItem = { id: string; name: string };
type Prof = { id: string; full_name: string | null; email: string | null };
type CourseItem = { id: string; title: string };
type Schedule = {
  id: string;
  class_id: string | null;
  class_name: string | null;
  professor_id: string | null;
  course_id: string | null;
  room: string;
  title: string | null;
  start_time: string;
  end_time: string;
  recurrence: "once" | "weekly";
};
const ATTENDANCE_STATUS: { value: string; label: string }[] = [
  { value: "present", label: "Présent" },
  { value: "absent", label: "Absent" },
  { value: "retard", label: "Retard" },
  { value: "excuse", label: "Excusé" },
];

function fmt(dt: string) {
  const d = new Date(dt);
  return `${WEEKDAYS[d.getDay()]} ${d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit" })} · ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

function CreateModal({ classes, profs, courses, onClose, onCreated }: { classes: ClassItem[]; profs: Prof[]; courses: CourseItem[]; onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState({ room: "", class_id: "", professor_id: "", course_id: "", title: "", start_time: "", end_time: "", recurrence: "once" as "once" | "weekly" });
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!form.room.trim()) { toast.error("La salle est requise."); return; }
    if (!form.start_time || !form.end_time) { toast.error("Les horaires sont requis."); return; }
    setBusy(true);
    try {
      await api.post("/api/schedules", {
        room: form.room,
        class_id: form.class_id || null,
        professor_id: form.professor_id || null,
        course_id: form.course_id || null,
        title: form.title || null,
        start_time: new Date(form.start_time).toISOString(),
        end_time: new Date(form.end_time).toISOString(),
        recurrence: form.recurrence,
      });
      toast.success("Créneau créé !");
      onCreated();
      onClose();
    } catch (err: any) {
      // Backend returns 409 with {detail: {message, conflicts}} on room/instructor overlap
      let msg = "Erreur lors de la création.";
      try {
        const parsed = JSON.parse(err.message);
        if (parsed?.detail?.message) msg = `Conflit détecté : ${parsed.detail.message} (${parsed.detail.conflicts?.length ?? 0} créneau(x) en collision)`;
        else if (typeof parsed?.detail === "string") msg = parsed.detail;
      } catch {
        if (err?.message) msg = err.message;
      }
      toast.error(msg);
    } finally {
      setBusy(false);
    }
  }

  const fieldStyle = { marginTop: 8, marginBottom: 16, width: "100%", padding: "11px 14px", border: `1px solid ${PAL.line}`, borderRadius: 10, fontFamily: sans, fontSize: 14, color: PAL.ink, background: PAL.paper, outline: "none", boxSizing: "border-box" as const };
  const labelStyle = { fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const };

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 16, padding: 32, width: 480, maxWidth: "95vw", maxHeight: "92vh", overflowY: "auto", boxShadow: "0 24px 60px rgba(0,0,0,.18)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
          <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 26, fontWeight: 500, color: PAL.ink, margin: "0 0 20px" }}>
            Nouveau créneau
          </h2>
          <button type="button" onClick={onClose} title="Fermer" aria-label="Fermer" style={{ border: "none", background: "transparent", cursor: "pointer", color: PAL.muted, padding: 0, lineHeight: 0 }}><X size={20} /></button>
        </div>

        <label style={labelStyle}>Titre (optionnel)</label>
        <input type="text" value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="Ex : Soins infirmiers — TP" className="u-input" style={fieldStyle} />

        <label style={labelStyle}>Salle *</label>
        <input type="text" value={form.room} onChange={e => setForm(f => ({ ...f, room: e.target.value }))} placeholder="Ex : Salle B12" className="u-input" style={fieldStyle} />

        <label style={labelStyle}>Classe (optionnel)</label>
        <select value={form.class_id} onChange={e => setForm(f => ({ ...f, class_id: e.target.value }))} className="u-input" style={fieldStyle}>
          <option value="">— Aucune —</option>
          {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <label style={labelStyle}>Formateur (optionnel)</label>
        <select value={form.professor_id} onChange={e => setForm(f => ({ ...f, professor_id: e.target.value }))} className="u-input" style={fieldStyle}>
          <option value="">— Aucun —</option>
          {profs.map(p => <option key={p.id} value={p.id}>{p.full_name || p.email}</option>)}
        </select>

        <label style={labelStyle}>Cours (optionnel)</label>
        <select value={form.course_id} onChange={e => setForm(f => ({ ...f, course_id: e.target.value }))} className="u-input" style={fieldStyle}>
          <option value="">— Aucun —</option>
          {courses.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
        </select>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <label style={labelStyle}>Début *</label>
            <input type="datetime-local" value={form.start_time} onChange={e => setForm(f => ({ ...f, start_time: e.target.value }))} className="u-input" style={fieldStyle} />
          </div>
          <div>
            <label style={labelStyle}>Fin *</label>
            <input type="datetime-local" value={form.end_time} onChange={e => setForm(f => ({ ...f, end_time: e.target.value }))} className="u-input" style={fieldStyle} />
          </div>
        </div>

        <label style={labelStyle}>Récurrence</label>
        <select value={form.recurrence} onChange={e => setForm(f => ({ ...f, recurrence: e.target.value as "once" | "weekly" }))} className="u-input" style={{ ...fieldStyle, marginBottom: 24 }}>
          <option value="once">Ponctuel</option>
          <option value="weekly">Hebdomadaire</option>
        </select>

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} className="u-ghost" style={{ fontFamily: sans, fontSize: 13, color: PAL.muted, background: "transparent", border: `1px solid ${PAL.line}`, borderRadius: 8, padding: "10px 18px", cursor: "pointer" }}>Annuler</button>
          <button onClick={submit} disabled={busy} style={{ fontFamily: sans, fontSize: 13, fontWeight: 600, color: PAL.paper, background: PAL.ink, border: 0, borderRadius: 8, padding: "10px 24px", cursor: busy ? "not-allowed" : "pointer", opacity: busy ? .6 : 1 }}>
            {busy ? "Création…" : "Créer le créneau"}
          </button>
        </div>
      </div>
    </div>
  );
}

function AttendanceModal({ schedule, onClose }: { schedule: Schedule; onClose: () => void }) {
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const [seanceId, setSeanceId] = useState<string | null>(null);
  const [roster, setRoster] = useState<{ student_id: string; full_name: string | null; status: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const seance = await api.get(`/api/schedules/${schedule.id}/seances?date=${date}`);
      setSeanceId(seance.id);
      const data = await api.get(`/api/seances/${seance.id}/attendance`);
      setRoster(data.roster ?? []);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors du chargement.");
      setRoster([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [date]);

  function setStatus(studentId: string, status: string) {
    setRoster(r => r.map(s => s.student_id === studentId ? { ...s, status } : s));
  }

  async function save() {
    if (!seanceId) return;
    setBusy(true);
    try {
      await api.post(`/api/seances/${seanceId}/attendance`, {
        entries: roster.map(s => ({ student_id: s.student_id, status: s.status })),
      });
      toast.success("Présence enregistrée.");
      onClose();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'enregistrement.");
    } finally {
      setBusy(false);
    }
  }

  const fieldStyle = { marginTop: 8, marginBottom: 16, padding: "9px 12px", border: `1px solid ${PAL.line}`, borderRadius: 8, fontFamily: sans, fontSize: 13, color: PAL.ink, background: PAL.paper, outline: "none" };
  const labelStyle = { fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const };

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 16, padding: 32, width: 460, maxWidth: "95vw", maxHeight: "88vh", overflowY: "auto", boxShadow: "0 24px 60px rgba(0,0,0,.18)" }}>
        <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 24, fontWeight: 500, color: PAL.ink, margin: "0 0 4px" }}>
          Présence — {schedule.title || schedule.class_name || "Créneau"}
        </h2>
        <p style={{ fontSize: 12.5, color: PAL.muted, margin: "0 0 16px" }}>{schedule.room}</p>

        <label style={labelStyle}>Date de la séance</label>
        <input type="date" value={date} onChange={e => setDate(e.target.value)} className="u-input" style={{ ...fieldStyle, width: 180 }} />

        {loading ? (
          <div className="shimmer" style={{ height: 18, width: 180, borderRadius: 999 }} />
        ) : roster.length === 0 ? (
          <div style={{ textAlign: "center", padding: "20px 0", color: PAL.muted, fontSize: 13 }}>
            Aucun étudiant dans cette classe.
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 20 }}>
            {roster.map(s => (
              <div key={s.student_id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 10px", borderRadius: 8, border: `1px solid ${PAL.line}` }}>
                <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: PAL.ink }}>{s.full_name || "—"}</span>
                <select
                  value={s.status}
                  onChange={e => setStatus(s.student_id, e.target.value)}
                  style={{ padding: "6px 8px", border: `1px solid ${PAL.line}`, borderRadius: 6, fontFamily: sans, fontSize: 12, background: PAL.paper }}
                >
                  {ATTENDANCE_STATUS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            ))}
          </div>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} style={{ fontFamily: sans, fontSize: 13, color: PAL.muted, background: "transparent", border: `1px solid ${PAL.line}`, borderRadius: 8, padding: "10px 18px", cursor: "pointer" }}>Fermer</button>
          <button onClick={save} disabled={busy || roster.length === 0} style={{ fontFamily: sans, fontSize: 13, fontWeight: 600, color: PAL.paper, background: PAL.ink, border: 0, borderRadius: 8, padding: "10px 24px", cursor: busy ? "not-allowed" : "pointer", opacity: busy ? .6 : 1 }}>
            {busy ? "Enregistrement…" : "Enregistrer la présence"}
          </button>
        </div>
      </div>
    </div>
  );
}

function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [profs, setProfs] = useState<Prof[]>([]);
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [attendanceFor, setAttendanceFor] = useState<Schedule | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data: Schedule[] = await api.get("/api/schedules");
      setSchedules(data);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors du chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    api.get("/api/classes/all").then((d: ClassItem[]) => setClasses(d ?? [])).catch(() => {});
    api.get("/api/users").then((d: any[]) => setProfs((d ?? []).filter(u => u.roles?.includes("professor")))).catch(() => {});
    api.get("/api/courses/list").then((d: CourseItem[]) => setCourses(d ?? [])).catch(() => {});
  }, []);

  const profMap = Object.fromEntries(profs.map(p => [p.id, p.full_name || p.email || "—"]));

  async function remove(s: Schedule) {
    if (!window.confirm("Supprimer ce créneau ?")) return;
    try {
      await api.delete(`/api/schedules/${s.id}`);
      toast.success("Créneau supprimé.");
      load();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la suppression.");
    }
  }

  return (
    <div style={{ fontFamily: sans }}>
      {showCreate && (
        <CreateModal classes={classes} profs={profs} courses={courses} onClose={() => setShowCreate(false)} onCreated={load} />
      )}
      {attendanceFor && (
        <AttendanceModal schedule={attendanceFor} onClose={() => setAttendanceFor(null)} />
      )}

      <PageHead
        eyebrow="Gestion administrative"
        title="Emploi du temps"
        sub="Créneaux, salles et formateurs — conflits détectés automatiquement."
        actions={
          <button type="button" onClick={() => setShowCreate(true)} className="btn-c btn-c-primary">
            <Plus size={15} strokeWidth={1.7} />Nouveau créneau
          </button>
        }
      />

      <SectionLabel>{schedules.length} créneau{schedules.length !== 1 ? "x" : ""}</SectionLabel>

      {loading ? (
        <div className="dash-card" style={{ padding: 26 }}>
          <div className="shimmer" style={{ height: 18, width: 180, borderRadius: 999 }} />
          <div className="shimmer" style={{ height: 26, width: "55%", borderRadius: 8, marginTop: 14 }} />
        </div>
      ) : schedules.length === 0 ? (
        <div className="dash-card">
          <EmptyHint
            icon={<CalendarClock size={28} strokeWidth={1.7} />}
            text={
              <span className="flex flex-col items-center gap-3">
                Aucun créneau planifié.
                <button type="button" onClick={() => setShowCreate(true)} className="btn-c btn-c-ghost btn-c-sm">
                  Créer le premier créneau
                </button>
              </span>
            }
          />
        </div>
      ) : (
        <div className="dash-card overflow-hidden">
          {schedules.map(s => (
            <div key={s.id} className="row-c flex-wrap">
              <span className="flex shrink-0" style={{ color: PAL.primary }}>
                <CalendarClock size={20} strokeWidth={1.7} />
              </span>
              <div className="min-w-0 flex-1" style={{ minWidth: 200 }}>
                <div style={{ fontWeight: 700, fontSize: 14, color: PAL.ink }}>
                  {s.title || s.class_name || "Créneau"}
                </div>
                <div className="mt-0.5" style={{ fontSize: 12, color: PAL.muted, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><MapPin size={11} strokeWidth={1.7} />{s.room}</span>
                  {s.professor_id && <span>{profMap[s.professor_id] ?? "—"}</span>}
                  {s.class_name && <span>{s.class_name}</span>}
                  {s.recurrence === "weekly" && (
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}><Repeat size={11} strokeWidth={1.7} />Hebdomadaire</span>
                  )}
                </div>
              </div>
              <span className="chip-c" style={{ fontFamily: '"JetBrains Mono", ui-monospace, monospace', fontSize: 10.5 }}>
                {fmt(s.start_time)}
              </span>
              {s.class_id && (
                <button
                  type="button"
                  onClick={() => setAttendanceFor(s)}
                  className="btn-c btn-c-sm btn-c-ghost"
                  title="Prendre la présence"
                >
                  <ClipboardCheck size={13} strokeWidth={1.7} />Présence
                </button>
              )}
              <button
                type="button"
                onClick={() => remove(s)}
                className="rounded-lg p-1.5 text-muted-foreground hover:text-destructive"
                aria-label="Supprimer"
                title="Supprimer"
              >
                <Trash2 size={14} strokeWidth={1.7} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
