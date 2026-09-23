import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Plus, Trash2, Pencil, Lock, Unlock, Download, CalendarRange } from "lucide-react";
import { PageHead, SectionLabel, EmptyHint } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/timetables")({
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
  component: TimetablesPage,
});

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  muted:   "oklch(48% 0.02 180)",
  primary: "oklch(48% 0.085 175)",
  line:    "oklch(88% 0.015 170)",
  paper:   "oklch(99% 0.005 160)",
  pale:    "oklch(94% 0.025 165)",
  danger:  "oklch(64% 0.18 25)",
};
const sans = '"Manrope", system-ui, sans-serif';
const DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"];

type ClassItem = { id: string; name: string };
type Prof = { id: string; full_name: string | null; email: string | null };
type Slot = {
  id: string;
  day_of_week: number;
  start_time: string;
  end_time: string;
  subject: string | null;
  slot_type: "course" | "exam";
  professor_id: string | null;
  room: string | null;
};
type Timetable = {
  id: string;
  class_id: string;
  academic_year: string;
  week_start: string;
  week_end: string;
  status: "draft" | "validated";
  slots: Slot[];
};

function defaultAcademicYear(): string {
  const now = new Date();
  const y = now.getFullYear();
  return now.getMonth() >= 7 ? `${y}/${y + 1}` : `${y - 1}/${y}`;
}

function nextMonday(): string {
  const d = new Date();
  const day = d.getDay(); // 0=Sun..6=Sat
  const diff = (day === 1) ? 0 : ((8 - day) % 7 || 7);
  d.setDate(d.getDate() + (day === 0 ? 1 : diff === 0 ? 0 : diff));
  if (day !== 1) d.setDate(d.getDate());
  return d.toISOString().slice(0, 10);
}

function addDays(iso: string, n: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
}

function fmtFR(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function parseErr(err: any, fallback: string): string {
  try {
    const parsed = JSON.parse(err.message);
    if (parsed?.detail?.message) {
      return `${parsed.detail.message} (${parsed.detail.conflicts?.length ?? 0} conflit(s))`;
    }
    if (typeof parsed?.detail === "string") return parsed.detail;
  } catch {
    if (err?.message) return err.message;
  }
  return fallback;
}

const fieldStyle = {
  padding: "8px 10px", border: `1px solid ${PAL.line}`, borderRadius: 8,
  fontFamily: sans, fontSize: 12.5, color: PAL.ink, background: PAL.paper,
  outline: "none", boxSizing: "border-box" as const, width: "100%",
};

type SlotFormValue = {
  start_time: string; end_time: string; subject: string;
  slot_type: "course" | "exam"; professor_id: string; room: string;
};

function SlotForm({
  initial, profs, onCancel, onSubmit, busy,
}: {
  initial: SlotFormValue;
  profs: Prof[];
  onCancel: () => void;
  onSubmit: (v: SlotFormValue) => void;
  busy: boolean;
}) {
  const [v, setV] = useState<SlotFormValue>(initial);
  return (
    <div className="anim-pop" style={{ border: `1px dashed ${PAL.line}`, borderRadius: 10, padding: 12, marginTop: 6, background: PAL.pale }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <div>
          <label style={{ fontSize: 10.5, color: PAL.muted }}>Début</label>
          <input type="time" value={v.start_time} onChange={e => setV(s => ({ ...s, start_time: e.target.value }))} style={fieldStyle} />
        </div>
        <div>
          <label style={{ fontSize: 10.5, color: PAL.muted }}>Fin</label>
          <input type="time" value={v.end_time} onChange={e => setV(s => ({ ...s, end_time: e.target.value }))} style={fieldStyle} />
        </div>
      </div>
      <div style={{ marginTop: 8 }}>
        <label style={{ fontSize: 10.5, color: PAL.muted }}>Séquence (Matière) — laisser vide pour "-"</label>
        <input type="text" value={v.subject} onChange={e => setV(s => ({ ...s, subject: e.target.value }))} placeholder="Ex : Pathologie et soins infirmiers" style={{ ...fieldStyle, marginTop: 4 }} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
        <div>
          <label style={{ fontSize: 10.5, color: PAL.muted }}>Type</label>
          <select value={v.slot_type} onChange={e => setV(s => ({ ...s, slot_type: e.target.value as "course" | "exam" }))} style={{ ...fieldStyle, marginTop: 4 }}>
            <option value="course">Cours</option>
            <option value="exam">Contrôle continue</option>
          </select>
        </div>
        <div>
          <label style={{ fontSize: 10.5, color: PAL.muted }}>Salle</label>
          <input type="text" value={v.room} onChange={e => setV(s => ({ ...s, room: e.target.value }))} placeholder="Ex : TP" style={{ ...fieldStyle, marginTop: 4 }} />
        </div>
      </div>
      <div style={{ marginTop: 8 }}>
        <label style={{ fontSize: 10.5, color: PAL.muted }}>Formateur(trice)</label>
        <select value={v.professor_id} onChange={e => setV(s => ({ ...s, professor_id: e.target.value }))} style={{ ...fieldStyle, marginTop: 4 }}>
          <option value="">— Aucun —</option>
          {profs.map(p => <option key={p.id} value={p.id}>{p.full_name || p.email}</option>)}
        </select>
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end", marginTop: 10 }}>
        <button onClick={onCancel} className="btn-c btn-c-ghost btn-c-sm" type="button">Annuler</button>
        <button
          onClick={() => onSubmit(v)}
          disabled={busy || !v.start_time || !v.end_time}
          className="btn-c btn-c-primary btn-c-sm"
          type="button"
        >
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>
    </div>
  );
}

const EMPTY_FORM: SlotFormValue = { start_time: "", end_time: "", subject: "", slot_type: "course", professor_id: "", room: "" };

function TimetablesPage() {
  const { user, roles } = useAuth();
  const defaultProf = roles.includes("professor") && !roles.includes("admin") ? (user?.id ?? "") : "";
  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [profs, setProfs] = useState<Prof[]>([]);
  const [classId, setClassId] = useState("");
  const [weekStart, setWeekStart] = useState(nextMonday());
  const [academicYear, setAcademicYear] = useState(defaultAcademicYear());
  const [timetable, setTimetable] = useState<Timetable | null>(null);
  const [loading, setLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [addingDay, setAddingDay] = useState<number | null>(null);
  const [editingSlot, setEditingSlot] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/classes").then((d: ClassItem[]) => {
      setClasses(d ?? []);
      if (d?.length && !classId) setClassId(d[0].id);
    }).catch(() => {});
    api.get("/api/users").then((d: any[]) => setProfs((d ?? []).filter(u => u.roles?.includes("professor")))).catch(() => {});
  }, []);

  async function loadTimetable() {
    if (!classId || !weekStart) return;
    setLoading(true);
    setTimetable(null);
    try {
      const rows: any[] = await api.get(`/api/timetables?class_id=${classId}&week_start=${weekStart}`);
      if (rows?.length) {
        const full = await api.get(`/api/timetables/${rows[0].id}`);
        setTimetable(full);
        setAcademicYear(full.academic_year);
      }
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur lors du chargement."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadTimetable(); }, [classId, weekStart]);

  async function createTimetable() {
    setCreating(true);
    try {
      const created = await api.post("/api/timetables", {
        class_id: classId,
        academic_year: academicYear,
        week_start: weekStart,
        week_end: addDays(weekStart, 4),
      });
      toast.success("Emploi du temps créé.");
      const full = await api.get(`/api/timetables/${created.id}`);
      setTimetable(full);
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur lors de la création."));
    } finally {
      setCreating(false);
    }
  }

  async function addSlot(day: number, v: SlotFormValue) {
    if (!timetable) return;
    setBusy(true);
    try {
      await api.post(`/api/timetables/${timetable.id}/slots`, {
        day_of_week: day,
        start_time: v.start_time,
        end_time: v.end_time,
        subject: v.subject || null,
        slot_type: v.slot_type,
        professor_id: v.professor_id || null,
        room: v.room || null,
      });
      toast.success("Créneau ajouté.");
      setAddingDay(null);
      loadTimetable();
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur lors de l'ajout."));
    } finally {
      setBusy(false);
    }
  }

  async function updateSlot(slotId: string, v: SlotFormValue) {
    if (!timetable) return;
    setBusy(true);
    try {
      await api.put(`/api/timetables/${timetable.id}/slots/${slotId}`, {
        start_time: v.start_time,
        end_time: v.end_time,
        subject: v.subject || null,
        slot_type: v.slot_type,
        professor_id: v.professor_id || null,
        room: v.room || null,
      });
      toast.success("Créneau modifié.");
      setEditingSlot(null);
      loadTimetable();
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur lors de la modification."));
    } finally {
      setBusy(false);
    }
  }

  async function deleteSlot(slotId: string) {
    if (!timetable || !window.confirm("Supprimer ce créneau ?")) return;
    try {
      await api.delete(`/api/timetables/${timetable.id}/slots/${slotId}`);
      toast.success("Créneau supprimé.");
      loadTimetable();
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur lors de la suppression."));
    }
  }

  async function validate() {
    if (!timetable) return;
    setBusy(true);
    try {
      await api.post(`/api/timetables/${timetable.id}/validate`, {});
      toast.success("Emploi du temps validé !");
      loadTimetable();
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur lors de la validation."));
    } finally {
      setBusy(false);
    }
  }

  async function unlock() {
    if (!timetable) return;
    setBusy(true);
    try {
      await api.post(`/api/timetables/${timetable.id}/unlock`, {});
      toast.success("Emploi du temps déverrouillé.");
      loadTimetable();
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur."));
    } finally {
      setBusy(false);
    }
  }

  async function downloadPdf() {
    if (!timetable) return;
    try {
      await api.download(`/api/timetables/${timetable.id}/pdf`, `EDT_${timetable.week_start}.pdf`);
    } catch (err: any) {
      toast.error(parseErr(err, "Erreur lors du téléchargement."));
    }
  }

  const profMap = Object.fromEntries(profs.map(p => [p.id, p.full_name || p.email || "—"]));
  const locked = timetable?.status === "validated";

  return (
    <div style={{ fontFamily: sans }}>
      <PageHead
        eyebrow="Gestion pédagogique"
        title="Emplois du temps"
        sub="Construisez, validez et téléchargez l'emploi du temps officiel de votre classe."
      />

      <div className="dash-card" style={{ padding: 18, marginBottom: 20, display: "flex", gap: 14, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div style={{ minWidth: 200 }}>
          <label style={{ fontSize: 10.5, fontWeight: 600, color: PAL.muted, textTransform: "uppercase", letterSpacing: ".08em" }}>Classe (Filière)</label>
          <select value={classId} onChange={e => setClassId(e.target.value)} style={{ ...fieldStyle, marginTop: 4 }}>
            {classes.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label style={{ fontSize: 10.5, fontWeight: 600, color: PAL.muted, textTransform: "uppercase", letterSpacing: ".08em" }}>Semaine (lundi)</label>
          <input type="date" value={weekStart} onChange={e => setWeekStart(e.target.value)} style={{ ...fieldStyle, marginTop: 4 }} />
        </div>
        <div>
          <label style={{ fontSize: 10.5, fontWeight: 600, color: PAL.muted, textTransform: "uppercase", letterSpacing: ".08em" }}>Année scolaire</label>
          <input type="text" value={academicYear} onChange={e => setAcademicYear(e.target.value)} style={{ ...fieldStyle, marginTop: 4, width: 110 }} />
        </div>

        {timetable && (
          <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
            {!locked ? (
              <button onClick={validate} disabled={busy} className="btn-c btn-c-primary">
                <Lock size={14} strokeWidth={1.7} />Valider
              </button>
            ) : (
              <>
                <button onClick={unlock} disabled={busy} className="btn-c btn-c-ghost">
                  <Unlock size={14} strokeWidth={1.7} />Déverrouiller
                </button>
                <button onClick={downloadPdf} className="btn-c btn-c-primary">
                  <Download size={14} strokeWidth={1.7} />Télécharger le PDF
                </button>
              </>
            )}
          </div>
        )}
      </div>

      <SectionLabel>
        {timetable ? `Semaine du ${fmtFR(timetable.week_start)} au ${fmtFR(timetable.week_end)}` : "Aucun emploi du temps pour cette semaine"}
      </SectionLabel>

      {loading ? (
        <div className="dash-card" style={{ padding: 26 }}>
          <div className="shimmer" style={{ height: 18, width: 180, borderRadius: 999 }} />
        </div>
      ) : !timetable ? (
        <div className="dash-card">
          <EmptyHint
            icon={<CalendarRange size={28} strokeWidth={1.7} />}
            text={
              <span className="flex flex-col items-center gap-3">
                Aucun emploi du temps n'existe pour cette classe et cette semaine.
                <button type="button" onClick={createTimetable} disabled={creating || !classId} className="btn-c btn-c-primary btn-c-sm">
                  {creating ? "Création…" : "Créer l'emploi du temps"}
                </button>
              </span>
            }
          />
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {locked && (
            <div className="chip-c chip-c-green" style={{ display: "inline-flex", width: "fit-content" }}>
              Validé — lecture seule
            </div>
          )}
          {DAY_NAMES.map((dayName, dayIdx) => {
            const daySlots = timetable.slots.filter(s => s.day_of_week === dayIdx).sort((a, b) => a.start_time.localeCompare(b.start_time));
            return (
              <div key={dayIdx} className="dash-card" style={{ padding: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: PAL.ink }}>
                    {dayName} <span style={{ color: PAL.muted, fontWeight: 400, fontSize: 12 }}>{fmtFR(addDays(timetable.week_start, dayIdx))}</span>
                  </div>
                  {!locked && (
                    <button type="button" onClick={() => setAddingDay(dayIdx)} className="btn-c btn-c-ghost btn-c-sm">
                      <Plus size={13} strokeWidth={1.7} />Ajouter un créneau
                    </button>
                  )}
                </div>

                {daySlots.length === 0 && addingDay !== dayIdx && (
                  <div style={{ fontSize: 12.5, color: PAL.muted }}>-</div>
                )}

                {daySlots.map(s => (
                  <div key={s.id}>
                    {editingSlot === s.id ? (
                      <SlotForm
                        initial={{
                          start_time: s.start_time.slice(0, 5), end_time: s.end_time.slice(0, 5),
                          subject: s.subject ?? "", slot_type: s.slot_type,
                          professor_id: s.professor_id ?? "", room: s.room ?? "",
                        }}
                        profs={profs}
                        busy={busy}
                        onCancel={() => setEditingSlot(null)}
                        onSubmit={v => updateSlot(s.id, v)}
                      />
                    ) : (
                      <div className="row-c flex-wrap">
                        <span className="chip-c" style={{ fontFamily: '"JetBrains Mono", ui-monospace, monospace', fontSize: 10.5, flexShrink: 0 }}>
                          {s.start_time.slice(0, 5)}-{s.end_time.slice(0, 5)}
                        </span>
                        <div className="min-w-0 flex-1" style={{ minWidth: 160 }}>
                          {s.slot_type === "exam" ? (
                            <span className="chip-c chip-c-red" style={{ fontWeight: 700 }}>Contrôle continue : {s.subject || "-"}</span>
                          ) : (
                            <span style={{ fontWeight: 600, fontSize: 13, color: PAL.ink }}>{s.subject || "-"}</span>
                          )}
                          <div style={{ fontSize: 11.5, color: PAL.muted, marginTop: 2, display: "flex", gap: 10 }}>
                            {s.professor_id && <span>{profMap[s.professor_id] ?? "—"}</span>}
                            {s.room && <span>Salle {s.room}</span>}
                          </div>
                        </div>
                        {!locked && (
                          <>
                            <button type="button" onClick={() => setEditingSlot(s.id)} className="rounded-lg p-1.5 text-muted-foreground hover:text-primary" title="Modifier">
                              <Pencil size={13} strokeWidth={1.7} />
                            </button>
                            <button type="button" onClick={() => deleteSlot(s.id)} className="rounded-lg p-1.5 text-muted-foreground hover:text-destructive" title="Supprimer">
                              <Trash2 size={13} strokeWidth={1.7} />
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                ))}

                {addingDay === dayIdx && (
                  <SlotForm
                    initial={{ ...EMPTY_FORM, professor_id: defaultProf }}
                    profs={profs}
                    busy={busy}
                    onCancel={() => setAddingDay(null)}
                    onSubmit={v => addSlot(dayIdx, v)}
                  />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
