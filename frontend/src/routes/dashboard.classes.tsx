import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Plus, Trash2, Loader2, Users, X, BookOpen, Settings, GraduationCap, User, CalendarDays, Pencil, ArrowLeftRight } from "lucide-react";
import { PageHead } from "@/components/dashboard/ui";

type ClassesSearch = { specialty?: string; manage?: string };

export const Route = createFileRoute("/dashboard/classes")({
  validateSearch: (search: Record<string, unknown>): ClassesSearch => ({
    specialty: typeof search.specialty === "string" ? search.specialty : undefined,
    manage: typeof search.manage === "string" ? search.manage : undefined,
  }),
  beforeLoad: async () => {
    const { data: sess } = await supabase.auth.getSession();
    if (!sess.session) throw redirect({ to: "/auth" });
    const { data } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", sess.session.user.id)
      .in("role", ["admin", "professor", "cashier"]);
    if (!data?.length) throw redirect({ to: "/dashboard" });
  },
  component: ClassesPage,
});

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  text:    "oklch(34% 0.03 180)",
  muted:   "oklch(48% 0.02 180)",
  primary: "oklch(48% 0.085 175)",
  line:    "oklch(88% 0.015 170)",
  paper:   "oklch(99% 0.005 160)",
  pale:    "oklch(94% 0.025 165)",
  cream:   "oklch(97% 0.012 90)",
  success: "oklch(55% 0.14 145)",
  danger:  "oklch(55% 0.18 25)",
};
const sans = '"Manrope", system-ui, sans-serif';

type ClassItem = {
  id: string;
  name: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  student_count: number;
  professor_name: string;
  specialty_id: string | null;
  specialty_name: string | null;
  year_number: number | null;
  formation_id: string | null;
  formation_name: string | null;
  formation_code: string | null;
  trainer_id: string | null;
  trainer_name: string | null;
  start_date: string | null;
  duration_months: number | null;
};

type SpecialtyType = "formation_initiale" | "formation_continue";
type Specialty = { id: string; name: string; type: SpecialtyType };

type Formation = {
  id: string;
  name: string;
  code: string | null;
  default_duration_months: number | null;
  description: string | null;
};

type Trainer = { id: string; full_name: string | null; email: string | null };

// « sept. 2024 → juin 2025 · 9 mois » à partir d'une date de début + durée en mois
function fmtMonthYear(d: Date) {
  return d.toLocaleDateString("fr-FR", { month: "short", year: "numeric" });
}
function periodLabel(start: string | null, months: number | null): string | null {
  if (!start) return null;
  const d = new Date(start + "T00:00:00");
  if (isNaN(d.getTime())) return null;
  const startTxt = fmtMonthYear(d);
  if (!months) return startTxt;
  const end = new Date(d);
  end.setMonth(end.getMonth() + months);
  return `${startTxt} → ${fmtMonthYear(end)} · ${months} mois`;
}

type StudentItem = {
  id: string;
  email: string | null;
  full_name: string | null;
  added_at: string | null;
};

type RosterStudent = {
  id: string;
  email: string | null;
  full_name: string | null;
  roles: string[];
};

// ── Create class modal ────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "10px 14px",
  background: PAL.cream, border: `1px solid ${PAL.line}`,
  borderRadius: 10, fontFamily: sans, fontSize: 14,
  color: PAL.ink, outline: "none", boxSizing: "border-box",
};
const fieldLabelStyle: React.CSSProperties = {
  display: "block", fontFamily: sans, fontSize: 11, fontWeight: 600,
  color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase", marginBottom: 6,
};

function CreateClassModal({ specialties, editing, onClose, onCreated }: { specialties: Specialty[]; editing?: ClassItem | null; onClose: () => void; onCreated: () => void }) {
  const [name, setName]         = useState(editing?.name ?? "");
  const [desc, setDesc]         = useState(editing?.description ?? "");
  const [specialtyId, setSpecialtyId] = useState(editing?.specialty_id ?? "");
  const [yearNumber, setYearNumber]   = useState(editing?.year_number != null ? String(editing.year_number) : "");
  const [busy, setBusy]         = useState(false);

  const [formations, setFormations] = useState<Formation[]>([]);
  const [trainers, setTrainers]     = useState<Trainer[]>([]);
  const [formationId, setFormationId] = useState(editing?.formation_id ?? "");
  const [trainerId, setTrainerId]     = useState(editing?.trainer_id ?? "");
  const [startDate, setStartDate]     = useState(editing?.start_date ?? "");
  const [duration, setDuration]       = useState(editing?.duration_months != null ? String(editing.duration_months) : "");

  // Création d'une formation à la volée (dépliable sous le sélecteur)
  const [addingFormation, setAddingFormation]       = useState(false);
  const [newFName, setNewFName]                     = useState("");
  const [newFCode, setNewFCode]                     = useState("");
  const [newFDuration, setNewFDuration]             = useState("");
  const [savingFormation, setSavingFormation]       = useState(false);

  const backdropRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    (async () => {
      try {
        const [f, t] = await Promise.all([
          api.get("/api/classes/formations"),
          api.get("/api/classes/trainers"),
        ]);
        setFormations(f ?? []);
        setTrainers(t ?? []);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Erreur de chargement");
      }
    })();
  }, []);

  function pickFormation(id: string) {
    setFormationId(id);
    const f = formations.find(x => x.id === id);
    if (f?.default_duration_months != null && !duration) setDuration(String(f.default_duration_months));
  }

  async function createFormation() {
    const nm = newFName.trim();
    if (!nm) { toast.error("Nom de la formation requis"); return; }
    setSavingFormation(true);
    try {
      const created: Formation = await api.post("/api/classes/formations", {
        name: nm,
        code: newFCode.trim() || null,
        default_duration_months: newFDuration ? parseInt(newFDuration, 10) : null,
      });
      setFormations(prev => [...prev, created].sort((a, b) => a.name.localeCompare(b.name)));
      pickFormation(created.id);
      setAddingFormation(false);
      setNewFName(""); setNewFCode(""); setNewFDuration("");
      toast.success("Formation ajoutée au catalogue");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setSavingFormation(false);
    }
  }

  const endLabel = periodLabel(startDate || null, duration ? parseInt(duration, 10) : null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) { toast.error("Le nom est requis"); return; }
    setBusy(true);
    const payload = {
      name: name.trim(),
      description: desc.trim() || null,
      specialty_id: specialtyId || null,
      year_number: yearNumber ? parseInt(yearNumber, 10) : null,
      formation_id: formationId || null,
      trainer_id: trainerId || null,
      start_date: startDate || null,
      duration_months: duration ? parseInt(duration, 10) : null,
    };
    try {
      if (editing) {
        await api.patch(`/api/classes/${editing.id}`, payload);
        toast.success("Classe mise à jour !");
      } else {
        const res = await api.post("/api/classes", payload);
        // Caissier : création soumise à validation N+1 (backend renvoie {pending:true}).
        if (res?.pending) toast.success("Classe envoyée pour validation N+1 ✅");
        else toast.success("Classe créée !");
      }
      onCreated();
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      ref={backdropRef}
      onClick={e => { if (e.target === backdropRef.current) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        background: "oklch(0% 0 0 / .45)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: sans, padding: 20,
      }}
    >
      <div style={{
        background: PAL.paper, borderRadius: 16, padding: "32px 36px",
        width: "100%", maxWidth: 480, maxHeight: "92vh", overflowY: "auto",
        boxShadow: "0 24px 64px oklch(0% 0 0 / .18)", position: "relative",
      }}>
        <button type="button" onClick={onClose} style={{
          position: "absolute", top: 16, right: 16, background: "none",
          border: 0, cursor: "pointer", fontSize: 18, color: PAL.muted,
        }}>✕</button>

        <h2 style={{ margin: "0 0 6px", fontSize: 20, fontWeight: 700, color: PAL.ink }}>
          {editing ? "Modifier la classe" : "Créer une classe"}
        </h2>
        <p style={{ margin: "0 0 24px", fontSize: 13, color: PAL.muted }}>
          Rattachez la classe à une formation, un formateur et une période.
        </p>

        <form onSubmit={handleSubmit}>
          <ModalField label="Nom de la classe" value={name} onChange={setName} placeholder="Ex : Groupe A – Soins Infirmiers L2" />

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
            <div>
              <label style={fieldLabelStyle}>Spécialité</label>
              <select value={specialtyId} onChange={e => setSpecialtyId(e.target.value)} style={inputStyle}>
                <option value="">— Non définie —</option>
                {specialties.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>
            <div>
              <label style={fieldLabelStyle}>Année</label>
              <select value={yearNumber} onChange={e => setYearNumber(e.target.value)} style={inputStyle}>
                <option value="">— Non définie —</option>
                {[1, 2, 3, 4, 5].map(n => <option key={n} value={n}>Année {n}</option>)}
              </select>
            </div>
          </div>

          {/* Formation */}
          <div style={{ marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <label style={fieldLabelStyle}>Formation</label>
              <button type="button" onClick={() => setAddingFormation(v => !v)}
                style={{ background: "none", border: 0, cursor: "pointer", color: PAL.primary, fontSize: 11, fontWeight: 700, fontFamily: sans, padding: 0, marginBottom: 6 }}>
                {addingFormation ? "Annuler" : "＋ Nouvelle"}
              </button>
            </div>
            <select value={formationId} onChange={e => pickFormation(e.target.value)} style={inputStyle}>
              <option value="">— Aucune —</option>
              {formations.map(f => (
                <option key={f.id} value={f.id}>{f.code ? `${f.code} · ` : ""}{f.name}</option>
              ))}
            </select>
            {addingFormation && (
              <div style={{ marginTop: 10, padding: 12, background: PAL.pale, borderRadius: 10, border: `1px solid ${PAL.line}` }}>
                <input type="text" value={newFName} onChange={e => setNewFName(e.target.value)} placeholder="Nom de la formation" style={{ ...inputStyle, marginBottom: 8 }} />
                <div style={{ display: "flex", gap: 8 }}>
                  <input type="text" value={newFCode} onChange={e => setNewFCode(e.target.value)} placeholder="Code (ex. F001)" style={{ ...inputStyle, flex: 1 }} />
                  <input type="number" min="0" value={newFDuration} onChange={e => setNewFDuration(e.target.value)} placeholder="Durée (mois)" style={{ ...inputStyle, flex: 1 }} />
                </div>
                <button type="button" onClick={createFormation} disabled={savingFormation}
                  style={{ marginTop: 8, width: "100%", padding: "9px 0", borderRadius: 999, background: PAL.primary, border: 0, color: PAL.paper, fontFamily: sans, fontSize: 12.5, fontWeight: 700, cursor: savingFormation ? "not-allowed" : "pointer", opacity: savingFormation ? 0.65 : 1 }}>
                  {savingFormation ? "Ajout…" : "Ajouter au catalogue"}
                </button>
              </div>
            )}
          </div>

          {/* Formateur */}
          <div style={{ marginBottom: 14 }}>
            <label style={fieldLabelStyle}>Formateur</label>
            <select value={trainerId} onChange={e => setTrainerId(e.target.value)} style={inputStyle}>
              <option value="">— Aucun —</option>
              {trainers.map(t => (
                <option key={t.id} value={t.id}>{t.full_name || t.email || "—"}</option>
              ))}
            </select>
            {trainers.length === 0 && (
              <p style={{ fontSize: 11, color: PAL.muted, margin: "6px 0 0" }}>
                Aucun compte formateur. Créez un utilisateur avec le rôle professeur dans « Utilisateurs ».
              </p>
            )}
          </div>

          {/* Période : date de début + durée */}
          <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
            <div style={{ flex: 1 }}>
              <label style={fieldLabelStyle}>Date de début</label>
              <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} style={inputStyle} />
            </div>
            <div style={{ flex: 1 }}>
              <label style={fieldLabelStyle}>Durée (mois)</label>
              <input type="number" min="0" value={duration} onChange={e => setDuration(e.target.value)} placeholder="9" style={inputStyle} />
            </div>
          </div>
          {endLabel && (
            <p style={{ fontSize: 12, color: PAL.muted, margin: "0 0 14px" }}>
              Période : <strong style={{ color: PAL.text }}>{endLabel}</strong>
            </p>
          )}

          {/* Description */}
          <div style={{ marginBottom: 14 }}>
            <label style={fieldLabelStyle}>Description (optionnel)</label>
            <textarea
              value={desc}
              onChange={e => setDesc(e.target.value)}
              placeholder="Notes sur ce groupe…"
              rows={2}
              style={{ ...inputStyle, resize: "vertical" }}
            />
          </div>

          <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
            <button type="button" onClick={onClose} style={{
              flex: 1, padding: "11px 0", borderRadius: 999, fontFamily: sans, fontSize: 13,
              fontWeight: 600, cursor: "pointer",
              background: "transparent", border: `1px solid ${PAL.line}`, color: PAL.muted,
            }}>Annuler</button>
            <button type="submit" disabled={busy} style={{
              flex: 2, padding: "11px 0", borderRadius: 999, fontFamily: sans, fontSize: 13,
              fontWeight: 600, cursor: busy ? "not-allowed" : "pointer",
              background: PAL.ink, border: 0, color: PAL.paper,
              opacity: busy ? 0.65 : 1,
            }}>
              {busy ? "Enregistrement…" : editing ? "Enregistrer" : "Créer la classe"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ModalField({ label, value, onChange, placeholder }: {
  label: string; value: string; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: "block", fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const, marginBottom: 6 }}>
        {label}
      </label>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        style={{
          width: "100%", padding: "10px 14px",
          background: PAL.cream, border: `1px solid ${PAL.line}`,
          borderRadius: 10, fontFamily: sans, fontSize: 14,
          color: PAL.ink, outline: "none", boxSizing: "border-box" as const,
        }}
      />
    </div>
  );
}

// ── Manage specialties modal (admin only) ───────────────────────

const SPECIALTY_TYPE_LABEL: Record<SpecialtyType, string> = {
  formation_initiale: "Formation initiale",
  formation_continue: "Formation continue",
};

function SpecialtiesModal({ specialties, onClose, onChanged }: {
  specialties: Specialty[]; onClose: () => void; onChanged: () => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState<SpecialtyType>("formation_initiale");
  const [busy, setBusy] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);

  async function addSpecialty() {
    if (!name.trim()) { toast.error("Le nom est requis"); return; }
    setBusy(true);
    try {
      await api.post("/api/specialties", { name: name.trim(), type });
      setName("");
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  async function changeType(s: Specialty, nextType: SpecialtyType) {
    try {
      await api.patch(`/api/specialties/${s.id}`, { type: nextType });
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    }
  }

  async function removeSpecialty(s: Specialty) {
    if (!window.confirm(`Supprimer la spécialité « ${s.name} » ?`)) return;
    try {
      await api.delete(`/api/specialties/${s.id}`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    }
  }

  return (
    <div
      ref={backdropRef}
      onClick={e => { if (e.target === backdropRef.current) onClose(); }}
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        background: "oklch(0% 0 0 / .45)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: sans,
      }}
    >
      <div style={{
        background: PAL.paper, borderRadius: 16, padding: "32px 36px",
        width: "100%", maxWidth: 420, boxShadow: "0 24px 64px oklch(0% 0 0 / .18)",
        position: "relative",
      }}>
        <button type="button" onClick={onClose} style={{
          position: "absolute", top: 16, right: 16, background: "none",
          border: 0, cursor: "pointer", fontSize: 18, color: PAL.muted,
        }}>✕</button>

        <h2 style={{ margin: "0 0 20px", fontSize: 20, fontWeight: 700, color: PAL.ink }}>
          Gérer les spécialités
        </h2>

        <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
          <input
            type="text" value={name} onChange={e => setName(e.target.value)}
            placeholder="Nouvelle spécialité…"
            style={{
              flex: 1, padding: "9px 12px", background: PAL.cream, border: `1px solid ${PAL.line}`,
              borderRadius: 8, fontFamily: sans, fontSize: 13, color: PAL.ink, outline: "none",
            }}
          />
          <button type="button" onClick={addSpecialty} disabled={busy} className="btn-c btn-c-sm btn-c-primary">
            <Plus size={13} strokeWidth={1.7} />Ajouter
          </button>
        </div>
        <select
          value={type} onChange={e => setType(e.target.value as SpecialtyType)}
          style={{
            width: "100%", marginBottom: 18, padding: "8px 12px", background: PAL.cream, border: `1px solid ${PAL.line}`,
            borderRadius: 8, fontFamily: sans, fontSize: 12.5, color: PAL.ink, outline: "none",
          }}
        >
          <option value="formation_initiale">{SPECIALTY_TYPE_LABEL.formation_initiale}</option>
          <option value="formation_continue">{SPECIALTY_TYPE_LABEL.formation_continue}</option>
        </select>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {specialties.map(s => (
            <div key={s.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
              padding: "8px 10px", borderRadius: 8, background: PAL.pale, border: `1px solid ${PAL.line}`,
            }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: PAL.ink, flex: 1, minWidth: 0 }}>{s.name}</span>
              <select
                value={s.type} onChange={e => changeType(s, e.target.value as SpecialtyType)}
                style={{
                  padding: "4px 8px", background: PAL.paper, border: `1px solid ${PAL.line}`,
                  borderRadius: 6, fontFamily: sans, fontSize: 11.5, color: PAL.muted, outline: "none",
                }}
              >
                <option value="formation_initiale">{SPECIALTY_TYPE_LABEL.formation_initiale}</option>
                <option value="formation_continue">{SPECIALTY_TYPE_LABEL.formation_continue}</option>
              </select>
              <button type="button" onClick={() => removeSpecialty(s)} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.danger, flexShrink: 0 }}>
                <Trash2 size={13} strokeWidth={1.7} />
              </button>
            </div>
          ))}
          {specialties.length === 0 && (
            <div style={{ textAlign: "center", padding: "16px 0", color: PAL.muted, fontSize: 13 }}>Aucune spécialité.</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Transfer student modal (même filière uniquement) ─────────────
function TransferModal({ student, fromClass, classes, onClose, onDone }: {
  student: StudentItem; fromClass: ClassItem; classes: ClassItem[]; onClose: () => void; onDone: () => void;
}) {
  const [toId, setToId] = useState("");
  const [busy, setBusy] = useState(false);
  const backdropRef = useRef<HTMLDivElement>(null);
  // Cibles = classes de la MÊME filière (formation), hors classe d'origine.
  const targets = classes.filter(c => c.id !== fromClass.id && c.formation_id === fromClass.formation_id);

  async function submit() {
    if (!toId) { toast.error("Choisissez une classe cible"); return; }
    setBusy(true);
    try {
      const res = await api.post(`/api/classes/${fromClass.id}/students/${student.id}/transfer`, { to_class_id: toId });
      if (res?.pending) toast.success("Transfert envoyé pour validation N+1 ✅");
      else toast.success("Élève transféré");
      onDone();
      onClose();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div ref={backdropRef} onClick={e => { if (e.target === backdropRef.current) onClose(); }}
      style={{ position: "fixed", inset: 0, zIndex: 60, background: "oklch(0% 0 0 / .45)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: sans, padding: 20 }}>
      <div style={{ background: PAL.paper, borderRadius: 16, padding: "28px 32px", width: "100%", maxWidth: 440, boxShadow: "0 24px 64px oklch(0% 0 0 / .18)", position: "relative" }}>
        <button type="button" onClick={onClose} style={{ position: "absolute", top: 16, right: 16, background: "none", border: 0, cursor: "pointer", fontSize: 18, color: PAL.muted }}>✕</button>
        <h2 style={{ margin: "0 0 6px", fontSize: 19, fontWeight: 700, color: PAL.ink }}>Transférer l'élève</h2>
        <p style={{ margin: "0 0 20px", fontSize: 13, color: PAL.muted }}>
          <strong style={{ color: PAL.text }}>{student.full_name || student.email}</strong> — depuis « {fromClass.name} ».
          Seules les classes de la <strong>même filière</strong> sont proposées (les prix diffèrent d'une filière à l'autre).
        </p>
        {targets.length === 0 ? (
          <div style={{ padding: "18px 16px", borderRadius: 10, background: PAL.pale, border: `1px solid ${PAL.line}`, fontSize: 13, color: PAL.muted, marginBottom: 18 }}>
            Aucune autre classe de la même filière n'est disponible.
          </div>
        ) : (
          <div style={{ marginBottom: 18 }}>
            <label style={fieldLabelStyle}>Classe cible</label>
            <select value={toId} onChange={e => setToId(e.target.value)} style={inputStyle}>
              <option value="">— Choisir —</option>
              {targets.map(c => (
                <option key={c.id} value={c.id}>{c.name}{c.formation_code ? ` · ${c.formation_code}` : ""}</option>
              ))}
            </select>
          </div>
        )}
        <div style={{ display: "flex", gap: 10 }}>
          <button type="button" onClick={onClose} style={{ flex: 1, padding: "11px 0", borderRadius: 999, fontFamily: sans, fontSize: 13, fontWeight: 600, cursor: "pointer", background: "transparent", border: `1px solid ${PAL.line}`, color: PAL.muted }}>Annuler</button>
          <button type="button" onClick={submit} disabled={busy || targets.length === 0 || !toId} style={{ flex: 2, padding: "11px 0", borderRadius: 999, fontFamily: sans, fontSize: 13, fontWeight: 600, cursor: busy || !toId ? "not-allowed" : "pointer", background: PAL.ink, border: 0, color: PAL.paper, opacity: busy || targets.length === 0 || !toId ? 0.6 : 1 }}>
            {busy ? "Envoi…" : "Transférer"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Classes page ──────────────────────────────────────────────

function ClassesPage() {
  const { roles, loading: authLoading } = useAuth();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const [classes,      setClasses]      = useState<ClassItem[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [showModal,    setShowModal]    = useState(false);
  const [showSpecialtiesModal, setShowSpecialtiesModal] = useState(false);
  const [specialties,  setSpecialties]  = useState<Specialty[]>([]);
  const [editClass,    setEditClass]    = useState<ClassItem | null>(null);
  const [selected,     setSelected]     = useState<ClassItem | null>(null);
  const [students,     setStudents]     = useState<StudentItem[]>([]);
  const [studLoading,  setStudLoading]  = useState(false);
  const [roster,       setRoster]       = useState<RosterStudent[]>([]);
  const [deletingId,   setDeletingId]   = useState<string | null>(null);
  const [removingId,   setRemovingId]   = useState<string | null>(null);
  const [addingId,     setAddingId]     = useState<string | null>(null);
  const [transferFor,  setTransferFor]  = useState<StudentItem | null>(null);

  const isAdmin = roles.includes("admin");
  const isCashier = roles.includes("cashier");
  // Caissier : peut créer une classe, inscrire et transférer (→ validation N+1),
  // mais PAS modifier/supprimer une classe ni retirer un élève.
  const canManageClass = !isCashier;      // éditer / supprimer une classe, retirer un élève
  const canTransfer = isAdmin || isCashier;

  async function loadClasses() {
    setLoading(true);
    try {
      const data: ClassItem[] = await api.get("/api/classes");
      setClasses(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  async function loadStudents(classId: string) {
    setStudLoading(true);
    try {
      const data: StudentItem[] = await api.get(`/api/classes/${classId}/students`);
      setStudents(data);
    } catch {
      setStudents([]);
    } finally {
      setStudLoading(false);
    }
  }

  async function loadRoster() {
    try {
      const data: RosterStudent[] = await api.get("/api/users");
      setRoster(data.filter(u =>
      u.roles.includes("student") &&
      !u.roles.includes("admin") &&
      !u.roles.includes("professor")
    ));
    } catch {
      setRoster([]);
    }
  }

  async function loadSpecialties() {
    try {
      const data: Specialty[] = await api.get("/api/specialties");
      setSpecialties(data);
    } catch {
      setSpecialties([]);
    }
  }

  useEffect(() => {
    if (!authLoading) {
      loadClasses();
      loadRoster();
      loadSpecialties();
    }
  }, [authLoading]);

  // Ouverture directe depuis la barre latérale : /dashboard/classes?manage=specialties
  useEffect(() => {
    if (search.manage === "specialties") setShowSpecialtiesModal(true);
  }, [search.manage]);

  const activeSpecialty = search.specialty ? specialties.find(s => s.id === search.specialty) : undefined;
  const visibleClasses = search.specialty ? classes.filter(c => c.specialty_id === search.specialty) : classes;

  async function selectClass(cls: ClassItem) {
    setSelected(cls);
    await loadStudents(cls.id);
  }

  async function deleteClass(cls: ClassItem) {
    if (!window.confirm(`Supprimer définitivement la classe « ${cls.name} » ?`)) return;
    setDeletingId(cls.id);
    try {
      await api.delete(`/api/classes/${cls.id}`);
      toast.success("Classe supprimée");
      if (selected?.id === cls.id) setSelected(null);
      loadClasses();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setDeletingId(null);
    }
  }

  async function removeStudent(studentId: string) {
    if (!selected) return;
    setRemovingId(studentId);
    try {
      await api.delete(`/api/classes/${selected.id}/students/${studentId}`);
      toast.success("Étudiant retiré");
      await loadStudents(selected.id);
      loadClasses();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setRemovingId(null);
    }
  }

  async function addStudent(studentId: string) {
    if (!selected) return;
    setAddingId(studentId);
    try {
      const res = await api.post(`/api/classes/${selected.id}/students`, { student_id: studentId });
      // Caissier : inscription soumise à validation N+1 (backend renvoie {pending:true}).
      if (res?.pending) toast.success("Inscription envoyée pour validation N+1 ✅");
      else toast.success("Étudiant ajouté");
      await loadStudents(selected.id);
      loadClasses();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Étudiant déjà dans cette classe");
    } finally {
      setAddingId(null);
    }
  }

  const enrolledIds = new Set(students.map(s => s.id));
  const available   = roster.filter(s => !enrolledIds.has(s.id));

  return (
    <>
      {(showModal || editClass) && (
        <CreateClassModal
          specialties={specialties}
          key={editClass?.id ?? "new"}
          editing={editClass}
          onClose={() => { setShowModal(false); setEditClass(null); }}
          onCreated={loadClasses}
        />
      )}
      {showSpecialtiesModal && (
        <SpecialtiesModal
          specialties={specialties}
          onClose={() => setShowSpecialtiesModal(false)}
          onChanged={loadSpecialties}
        />
      )}

      {transferFor && selected && (
        <TransferModal
          student={transferFor}
          fromClass={selected}
          classes={classes}
          onClose={() => setTransferFor(null)}
          onDone={() => { if (selected) loadStudents(selected.id); loadClasses(); }}
        />
      )}

      <PageHead
        eyebrow="Encadrement"
        title="Classes"
        sub={isAdmin ? "Toutes les classes de la plateforme" : "Vos groupes d'étudiants"}
        actions={
          <>
            {isAdmin && (
              <button type="button" onClick={() => setShowSpecialtiesModal(true)} className="btn-c btn-c-ghost">
                <Settings size={15} strokeWidth={1.7} />
                Spécialités
              </button>
            )}
            <button type="button" onClick={() => setShowModal(true)} className="btn-c btn-c-primary">
              <BookOpen size={15} strokeWidth={1.7} />
              Nouvelle classe
            </button>
          </>
        }
      />

      {activeSpecialty && (
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          <span style={{
            display: "flex", alignItems: "center", gap: 6, fontFamily: sans, fontSize: 12.5, fontWeight: 700,
            color: PAL.primary, background: PAL.pale, borderRadius: 999, padding: "5px 12px",
          }}>
            Filtré par filière : {activeSpecialty.name}
            <button type="button" onClick={() => navigate({ search: {} })} style={{ background: "none", border: 0, cursor: "pointer", display: "flex", color: PAL.primary }}>
              <X size={13} strokeWidth={2} />
            </button>
          </span>
        </div>
      )}

      <div style={{ display: "flex", gap: 24, alignItems: "flex-start", flexWrap: "wrap" as const }}>

        {/* ── Left panel: class list ── */}
        <div style={{ flex: "1 1 340px", minWidth: 0 }}>
          {/* Class cards */}
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: 48 }}>
              <Loader2 style={{ width: 22, height: 22, color: PAL.muted, animation: "spin 1s linear infinite" }} />
            </div>
          ) : visibleClasses.length === 0 ? (
            <div style={{
              textAlign: "center", padding: "48px 24px",
              background: PAL.pale, borderRadius: 16,
              fontFamily: sans, color: PAL.muted, fontSize: 14,
            }}>
              <BookOpen style={{ width: 36, height: 36, margin: "0 auto 12px", opacity: 0.35 }} />
              <p style={{ fontWeight: 600, marginBottom: 4, color: PAL.text }}>Aucune classe</p>
              <p>{activeSpecialty ? "Aucune classe pour cette filière pour le moment." : "Créez votre première classe pour regrouper vos étudiants."}</p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {visibleClasses.map(cls => {
                const isSelected = selected?.id === cls.id;
                const isDeleting = deletingId === cls.id;
                return (
                  <div
                    key={cls.id}
                    onClick={() => selectClass(cls)}
                    style={{
                      display: "flex", alignItems: "center", gap: 14,
                      padding: "14px 16px", borderRadius: 12, cursor: "pointer",
                      background: isSelected ? PAL.pale : PAL.paper,
                      border: `1px solid ${isSelected ? PAL.primary : PAL.line}`,
                      transition: "all .15s",
                      fontFamily: sans,
                    }}
                  >
                    {/* Icon */}
                    <div style={{
                      width: 40, height: 40, borderRadius: 10, flexShrink: 0,
                      background: isSelected ? PAL.primary : PAL.pale,
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <Users style={{ width: 18, height: 18, color: isSelected ? PAL.paper : PAL.primary }} />
                    </div>

                    {/* Info */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, fontSize: 14, color: PAL.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
                        {cls.name}
                      </div>
                      {cls.description && (
                        <div style={{ fontSize: 12, color: PAL.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const, marginTop: 2 }}>
                          {cls.description}
                        </div>
                      )}
                      {(cls.specialty_name || cls.year_number) && (
                        <div style={{ marginTop: 4 }}>
                          <span style={{
                            fontSize: 10.5, fontWeight: 700, padding: "2px 8px", borderRadius: 999,
                            background: PAL.pale, color: PAL.primary,
                          }}>
                            {[cls.specialty_name, cls.year_number ? `Année ${cls.year_number}` : null].filter(Boolean).join(" · ")}
                          </span>
                        </div>
                      )}
                      <div style={{ fontSize: 11, color: PAL.muted, marginTop: 4 }}>
                        <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                          <Users style={{ width: 11, height: 11 }} />
                          {cls.student_count} étudiant{cls.student_count !== 1 ? "s" : ""}
                        </span>
                        {isAdmin && (
                          <span style={{ marginInlineStart: 10 }}>· {cls.professor_name}</span>
                        )}
                      </div>
                      {(cls.formation_name || cls.trainer_name || cls.start_date) && (
                        <div style={{ display: "flex", flexWrap: "wrap" as const, gap: "4px 12px", fontSize: 11, color: PAL.muted, marginTop: 5 }}>
                          {cls.formation_name && (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                              <GraduationCap style={{ width: 11, height: 11 }} />
                              {cls.formation_code ? `${cls.formation_code} · ` : ""}{cls.formation_name}
                            </span>
                          )}
                          {cls.trainer_name && (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                              <User style={{ width: 11, height: 11 }} />
                              {cls.trainer_name}
                            </span>
                          )}
                          {periodLabel(cls.start_date, cls.duration_months) && (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                              <CalendarDays style={{ width: 11, height: 11 }} />
                              {periodLabel(cls.start_date, cls.duration_months)}
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Edit */}
                    {canManageClass && (<>
                    <button
                      type="button"
                      onClick={e => { e.stopPropagation(); setEditClass(cls); }}
                      title="Modifier (formation, formateur, période)"
                      style={{
                        display: "inline-flex", alignItems: "center", justifyContent: "center",
                        width: 30, height: 30, borderRadius: 8, border: `1px solid ${PAL.line}`,
                        background: "transparent", cursor: "pointer", color: PAL.muted, flexShrink: 0,
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = PAL.pale; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
                    >
                      <Pencil style={{ width: 13, height: 13 }} />
                    </button>

                    {/* Delete */}
                    <button
                      type="button"
                      onClick={e => { e.stopPropagation(); deleteClass(cls); }}
                      disabled={isDeleting}
                      title="Supprimer cette classe"
                      style={{
                        display: "inline-flex", alignItems: "center", justifyContent: "center",
                        width: 30, height: 30, borderRadius: 8, border: `1px solid ${PAL.line}`,
                        background: "transparent", cursor: isDeleting ? "not-allowed" : "pointer",
                        color: isDeleting ? PAL.muted : PAL.danger,
                        flexShrink: 0,
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = "oklch(97% 0.01 25)"; }}
                      onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = "transparent"; }}
                    >
                      {isDeleting
                        ? <Loader2 style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} />
                        : <Trash2 style={{ width: 13, height: 13 }} />
                      }
                    </button>
                    </>)}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ── Right panel: class detail ── */}
        {selected && (
          <div className="dash-card" style={{
            flex: "1 1 340px", minWidth: 0,
            padding: "20px 22px",
            fontFamily: sans,
          }}>
            {/* Panel header */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 18 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700, color: PAL.ink }}>{selected.name}</div>
                {selected.description && (
                  <div style={{ fontSize: 12, color: PAL.muted, marginTop: 3 }}>{selected.description}</div>
                )}
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted, fontSize: 18, lineHeight: 1, padding: 4 }}
              >
                ✕
              </button>
            </div>

            {/* Add student row */}
            {available.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const, marginBottom: 8 }}>
                  Ajouter un étudiant
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 180, overflowY: "auto" as const }}>
                  {available.map(s => (
                    <div key={s.id} style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      padding: "8px 10px", borderRadius: 8,
                      background: PAL.cream, border: `1px solid ${PAL.line}`,
                      gap: 8,
                    }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: PAL.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
                          {s.full_name || s.email || "—"}
                        </div>
                        <div style={{ fontSize: 11, color: PAL.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
                          {s.email}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => addStudent(s.id)}
                        disabled={addingId === s.id}
                        style={{
                          display: "inline-flex", alignItems: "center", gap: 5,
                          padding: "5px 12px", borderRadius: 999,
                          background: PAL.primary, border: 0, color: PAL.paper,
                          fontSize: 11, fontWeight: 700, cursor: addingId === s.id ? "not-allowed" : "pointer",
                          opacity: addingId === s.id ? 0.6 : 1, flexShrink: 0,
                          fontFamily: sans,
                        }}
                      >
                        {addingId === s.id
                          ? <Loader2 style={{ width: 11, height: 11, animation: "spin 1s linear infinite" }} />
                          : <Plus style={{ width: 11, height: 11 }} />
                        }
                        Ajouter
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Divider */}
            <div style={{ height: 1, background: PAL.line, margin: "4px 0 16px" }} />

            {/* Enrolled students */}
            <div style={{ fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const, marginBottom: 10 }}>
              Étudiants inscrits ({students.length})
            </div>

            {studLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 24 }}>
                <Loader2 style={{ width: 18, height: 18, color: PAL.muted, animation: "spin 1s linear infinite" }} />
              </div>
            ) : students.length === 0 ? (
              <div style={{ textAlign: "center", padding: "24px 0", color: PAL.muted, fontSize: 13 }}>
                Aucun étudiant dans cette classe
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {students.map(s => (
                  <div key={s.id} style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "9px 10px", borderRadius: 8,
                    border: `1px solid ${PAL.line}`, background: PAL.pale,
                  }}>
                    <div style={{
                      width: 30, height: 30, borderRadius: 999, flexShrink: 0,
                      background: PAL.primary, color: PAL.paper,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 11, fontWeight: 700,
                    }}>
                      {(s.full_name || s.email || "?")[0].toUpperCase()}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: PAL.ink, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
                        {s.full_name || "—"}
                      </div>
                      <div style={{ fontSize: 11, color: PAL.muted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" as const }}>
                        {s.email}
                      </div>
                    </div>
                    {canTransfer && (
                      <button
                        type="button"
                        onClick={() => setTransferFor(s)}
                        title="Transférer vers une autre classe (même filière)"
                        style={{
                          display: "inline-flex", alignItems: "center", justifyContent: "center",
                          width: 26, height: 26, borderRadius: 6, border: `1px solid ${PAL.line}`,
                          background: "transparent", cursor: "pointer", color: PAL.primary, flexShrink: 0,
                        }}
                      >
                        <ArrowLeftRight style={{ width: 12, height: 12 }} />
                      </button>
                    )}
                    {canManageClass && (
                      <button
                        type="button"
                        onClick={() => removeStudent(s.id)}
                        disabled={removingId === s.id}
                        title="Retirer de la classe"
                        style={{
                          display: "inline-flex", alignItems: "center", justifyContent: "center",
                          width: 26, height: 26, borderRadius: 6, border: `1px solid ${PAL.line}`,
                          background: "transparent", cursor: removingId === s.id ? "not-allowed" : "pointer",
                          color: removingId === s.id ? PAL.muted : PAL.danger,
                          flexShrink: 0,
                        }}
                      >
                        {removingId === s.id
                          ? <Loader2 style={{ width: 11, height: 11, animation: "spin 1s linear infinite" }} />
                          : <X style={{ width: 11, height: 11 }} />
                        }
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}
