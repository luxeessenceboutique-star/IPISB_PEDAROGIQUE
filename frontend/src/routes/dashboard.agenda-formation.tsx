import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Building2, Layers, User, Clock3, Plus, X, Pencil, Trash2, GraduationCap, MapPin, Users as UsersIcon } from "lucide-react";
import { PageHead, EmptyHint, SectionLabel } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/agenda-formation")({
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
  component: AgendaFormationPage,
});

const PAL = {
  ink: "oklch(22% 0.025 175)", muted: "oklch(48% 0.02 180)", line: "oklch(88% 0.015 170)", paper: "oklch(99% 0.005 160)",
};
const sans = '"Manrope", system-ui, sans-serif';
const DAYS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"];
const fieldStyle = { marginTop: 6, marginBottom: 14, width: "100%", padding: "9px 12px", border: `1px solid ${PAL.line}`, borderRadius: 8, fontFamily: sans, fontSize: 13, color: PAL.ink, background: PAL.paper, outline: "none", boxSizing: "border-box" as const };
const labelStyle = { fontFamily: sans, fontSize: 10.5, fontWeight: 600, color: PAL.muted, letterSpacing: ".08em", textTransform: "uppercase" as const };

type Slot = { day_of_week: number; start_time: string; end_time: string; subject: string | null; class_name: string | null; filiere: string | null; professor_name: string | null };
type RoomUsage = {
  room: string; room_id: string | null; capacity: number | null; building: string | null; floor: string | null;
  equipment: string | null; notes: string | null; filieres: string[]; slot_count: number; slots: Slot[];
};
type Specialty = { id: string; name: string; type: string };

function timeShort(t: string) {
  return t.slice(0, 5);
}

type RoomForm = { name: string; capacity: string; building: string; floor: string; equipment: string; notes: string };
function emptyForm(r?: RoomUsage): RoomForm {
  return {
    name: r?.room ?? "", capacity: r?.capacity != null ? String(r.capacity) : "",
    building: r?.building ?? "", floor: r?.floor ?? "", equipment: r?.equipment ?? "", notes: r?.notes ?? "",
  };
}

function RoomDetailModal({ room, onClose, onSaved, onDeleted }: { room: RoomUsage; onClose: () => void; onSaved: () => void; onDeleted: () => void }) {
  const [form, setForm] = useState<RoomForm>(emptyForm(room));
  const [busy, setBusy] = useState(false);
  const byDay = DAYS.map((_, i) => room.slots.filter(s => s.day_of_week === i).sort((a, b) => a.start_time.localeCompare(b.start_time)));

  async function save() {
    if (!form.name.trim()) { toast.error("Le nom de la salle est requis."); return; }
    setBusy(true);
    try {
      const payload = {
        name: form.name.trim(),
        capacity: form.capacity ? parseInt(form.capacity, 10) : null,
        building: form.building.trim() || null,
        floor: form.floor.trim() || null,
        equipment: form.equipment.trim() || null,
        notes: form.notes.trim() || null,
      };
      if (room.room_id) await api.patch(`/api/rooms/${room.room_id}`, payload);
      else await api.post("/api/rooms", payload);
      toast.success("Fiche salle enregistrée.");
      onSaved();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'enregistrement.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!room.room_id) return;
    if (!window.confirm(`Supprimer la fiche de la salle « ${room.room} » ? (l'historique des créneaux planifiés n'est pas affecté)`)) return;
    setBusy(true);
    try {
      await api.delete(`/api/rooms/${room.room_id}`);
      toast.success("Salle supprimée.");
      onDeleted();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la suppression.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)", padding: 20 }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 16, width: "100%", maxWidth: 680, maxHeight: "88vh", display: "flex", flexDirection: "column", boxShadow: "0 24px 60px rgba(0,0,0,.18)" }}>
        <div style={{ padding: "18px 24px", borderBottom: `1px solid ${PAL.line}`, display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
          <div style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 22, fontWeight: 500, color: PAL.ink }}>{room.room}</div>
          <button onClick={onClose} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted }}><X size={18} strokeWidth={1.7} /></button>
        </div>

        <div style={{ overflowY: "auto", padding: "18px 24px" }}>
          <SectionLabel>Fiche salle</SectionLabel>
          {!room.room_id && (
            <div style={{ fontSize: 12, color: PAL.muted, fontStyle: "italic" as const, marginBottom: 10 }}>
              Salle vue dans l'emploi du temps mais pas encore enregistrée — complétez et enregistrez pour la gérer.
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>Nom de la salle *</label>
              <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} style={fieldStyle} className="u-input" />
            </div>
            <div>
              <label style={labelStyle}>Capacité (places)</label>
              <input type="number" min="0" value={form.capacity} onChange={e => setForm({ ...form, capacity: e.target.value })} style={fieldStyle} className="u-input" />
            </div>
            <div>
              <label style={labelStyle}>Bâtiment</label>
              <input type="text" value={form.building} onChange={e => setForm({ ...form, building: e.target.value })} style={fieldStyle} className="u-input" />
            </div>
            <div>
              <label style={labelStyle}>Étage</label>
              <input type="text" value={form.floor} onChange={e => setForm({ ...form, floor: e.target.value })} style={fieldStyle} className="u-input" />
            </div>
          </div>
          <label style={labelStyle}>Équipement</label>
          <input type="text" placeholder="Vidéoprojecteur, tableau interactif…" value={form.equipment} onChange={e => setForm({ ...form, equipment: e.target.value })} style={fieldStyle} className="u-input" />
          <label style={labelStyle}>Notes</label>
          <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })} rows={2} style={{ ...fieldStyle, resize: "vertical" as const }} className="u-input" />

          <div style={{ display: "flex", gap: 8, marginBottom: 4 }}>
            <button type="button" onClick={save} disabled={busy} className="btn-c btn-c-sm btn-c-primary">
              <Pencil size={13} strokeWidth={1.7} />{busy ? "…" : "Enregistrer"}
            </button>
            {room.room_id && (
              <button type="button" onClick={remove} disabled={busy} className="btn-c btn-c-sm" style={{ color: "var(--pal-danger)" }}>
                <Trash2 size={13} strokeWidth={1.7} />Supprimer la fiche
              </button>
            )}
          </div>

          {room.filieres.length > 0 && (
            <>
              <SectionLabel>Types de formation utilisant cette salle</SectionLabel>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 16 }}>
                {room.filieres.map(f => (
                  <span key={f} className="chip-c chip-c-blue" style={{ fontSize: 11 }}>
                    <GraduationCap size={11} strokeWidth={1.8} />{f}
                  </span>
                ))}
              </div>
            </>
          )}

          <SectionLabel>Occupation hebdomadaire ({room.slot_count} créneau{room.slot_count > 1 ? "x" : ""})</SectionLabel>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 0, border: `1px solid ${PAL.line}`, borderRadius: 10, overflow: "hidden" }}>
            {DAYS.map((day, i) => (
              <div key={day} style={{ padding: "12px 10px", borderInlineEnd: i < 4 ? `1px solid ${PAL.line}` : undefined }}>
                <div style={{ fontSize: 10.5, fontWeight: 700, color: PAL.muted, textTransform: "uppercase" as const, letterSpacing: ".05em", marginBottom: 8 }}>{day}</div>
                {byDay[i].length === 0 ? (
                  <div style={{ fontSize: 11.5, color: PAL.muted, fontStyle: "italic" as const }}>—</div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {byDay[i].map((s, j) => (
                      <div key={j} style={{ background: "var(--pal-cream)", borderRadius: 8, padding: "6px 8px" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 10.5, color: PAL.muted, fontWeight: 600 }}>
                          <Clock3 size={10} strokeWidth={1.8} />{timeShort(s.start_time)}–{timeShort(s.end_time)}
                        </div>
                        <div style={{ fontSize: 12, fontWeight: 600, color: PAL.ink, marginTop: 2 }}>{s.subject || "—"}</div>
                        <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: PAL.muted, marginTop: 2 }}>
                          <Layers size={10} strokeWidth={1.8} />{s.class_name || "—"}
                        </div>
                        {s.professor_name && (
                          <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: PAL.muted, marginTop: 1 }}>
                            <User size={10} strokeWidth={1.8} />{s.professor_name}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function NewRoomModal({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const [form, setForm] = useState<RoomForm>(emptyForm());
  const [busy, setBusy] = useState(false);

  async function create() {
    if (!form.name.trim()) { toast.error("Le nom de la salle est requis."); return; }
    setBusy(true);
    try {
      await api.post("/api/rooms", {
        name: form.name.trim(),
        capacity: form.capacity ? parseInt(form.capacity, 10) : null,
        building: form.building.trim() || null,
        floor: form.floor.trim() || null,
        equipment: form.equipment.trim() || null,
        notes: form.notes.trim() || null,
      });
      toast.success("Salle créée.");
      onCreated();
      onClose();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la création.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)", padding: 20 }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 16, width: "100%", maxWidth: 460, boxShadow: "0 24px 60px rgba(0,0,0,.18)" }}>
        <div style={{ padding: "18px 24px", borderBottom: `1px solid ${PAL.line}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 22, fontWeight: 500, color: PAL.ink }}>Nouvelle salle</div>
          <button onClick={onClose} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted }}><X size={18} strokeWidth={1.7} /></button>
        </div>
        <div style={{ padding: "18px 24px" }}>
          <label style={labelStyle}>Nom de la salle *</label>
          <input type="text" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} style={fieldStyle} className="u-input" autoFocus />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label style={labelStyle}>Capacité</label>
              <input type="number" min="0" value={form.capacity} onChange={e => setForm({ ...form, capacity: e.target.value })} style={fieldStyle} className="u-input" />
            </div>
            <div>
              <label style={labelStyle}>Bâtiment</label>
              <input type="text" value={form.building} onChange={e => setForm({ ...form, building: e.target.value })} style={fieldStyle} className="u-input" />
            </div>
          </div>
          <label style={labelStyle}>Équipement</label>
          <input type="text" value={form.equipment} onChange={e => setForm({ ...form, equipment: e.target.value })} style={{ ...fieldStyle, marginBottom: 20 }} className="u-input" />
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <button onClick={onClose} style={{ fontFamily: sans, fontSize: 13, color: PAL.muted, background: "transparent", border: `1px solid ${PAL.line}`, borderRadius: 8, padding: "9px 16px", cursor: "pointer" }}>Annuler</button>
            <button onClick={create} disabled={busy} className="btn-c btn-c-primary">{busy ? "…" : "Créer"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function RoomCard({ r, onOpen }: { r: RoomUsage; onOpen: () => void }) {
  return (
    <div className="dash-card u-hover-lift" style={{ padding: "16px 20px", cursor: "pointer" }} onClick={onOpen}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Building2 size={15} strokeWidth={1.8} style={{ color: "var(--pal-primary)" }} />
          <span style={{ fontWeight: 700, fontSize: 14.5, color: PAL.ink }}>{r.room}</span>
        </div>
        <span className="chip-c" style={{ fontSize: 11 }}>{r.slot_count} créneau{r.slot_count > 1 ? "x" : ""}/sem.</span>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12, color: PAL.muted, marginBottom: r.filieres.length ? 8 : 4 }}>
        {r.capacity != null && <span style={{ display: "flex", alignItems: "center", gap: 4 }}><UsersIcon size={12} strokeWidth={1.8} />{r.capacity} places</span>}
        {(r.building || r.floor) && <span style={{ display: "flex", alignItems: "center", gap: 4 }}><MapPin size={12} strokeWidth={1.8} />{[r.building, r.floor].filter(Boolean).join(" · ")}</span>}
        {!r.room_id && <span style={{ fontStyle: "italic" as const }}>Fiche non enregistrée</span>}
      </div>
      {r.filieres.length > 0 && (
        <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 8 }}>
          {r.filieres.map(f => <span key={f} className="chip-c chip-c-blue" style={{ fontSize: 10.5 }}>{f}</span>)}
        </div>
      )}
      <span style={{ fontFamily: sans, fontSize: 12, fontWeight: 600, color: "var(--pal-primary)" }}>Voir plus de détails →</span>
    </div>
  );
}

export function AgendaFormationPage() {
  const [rooms, setRooms] = useState<RoomUsage[]>([]);
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<RoomUsage | null>(null);
  const [showNew, setShowNew] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [roomData, specData] = await Promise.all([
        api.get("/api/timetables/rooms/usage") as Promise<RoomUsage[]>,
        api.get("/api/specialties") as Promise<Specialty[]>,
      ]);
      // Tolère une réponse d'un backend pas encore redéployé (avant l'ajout
      // de `filieres`/`capacity`/…) — évite un crash sur un champ manquant.
      setRooms((roomData ?? []).map(r => ({ ...r, filieres: r.filieres ?? [], slots: r.slots ?? [] })));
      setSpecialties(specData ?? []);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors du chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  // Reflète la sélection à jour après un enregistrement/suppression de fiche.
  useEffect(() => {
    if (!selected) return;
    const fresh = rooms.find(r => r.room === selected.room);
    if (fresh) setSelected(fresh);
  }, [rooms]); // eslint-disable-line react-hooks/exhaustive-deps

  const programCount = useMemo(() => {
    const counts = new Map<string, number>();
    for (const r of rooms) for (const f of r.filieres) counts.set(f, (counts.get(f) ?? 0) + 1);
    return counts;
  }, [rooms]);

  return (
    <div style={{ fontFamily: sans }}>
      {selected && (
        <RoomDetailModal
          room={selected}
          onClose={() => setSelected(null)}
          onSaved={() => { load(); }}
          onDeleted={() => { setSelected(null); load(); }}
        />
      )}
      {showNew && <NewRoomModal onClose={() => setShowNew(false)} onCreated={load} />}

      <PageHead
        eyebrow="Aperçu"
        title="Agenda formation"
        sub="Programmes de formation et occupation réelle des salles, d'après le dernier emploi du temps validé de chaque classe."
        actions={
          <button type="button" onClick={() => setShowNew(true)} className="btn-c btn-c-primary btn-c-sm">
            <Plus size={14} strokeWidth={1.7} />Nouvelle salle
          </button>
        }
      />

      <SectionLabel>Programmes de formation</SectionLabel>
      {specialties.length === 0 ? (
        <div className="dash-card" style={{ marginBottom: 22 }}><EmptyHint icon={<GraduationCap size={22} strokeWidth={1.7} />} text="Aucune filière renseignée." /></div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))", gap: 12, marginBottom: 26 }}>
          {specialties.map(s => (
            <div key={s.id} className="dash-card" style={{ padding: "14px 18px", display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{ width: 34, height: 34, borderRadius: 9, background: "var(--pal-pale)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--pal-primary)", flexShrink: 0 }}>
                <GraduationCap size={16} strokeWidth={1.8} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontFamily: sans, fontSize: 13, fontWeight: 700, color: PAL.ink }}>{s.name}</div>
                <div style={{ fontFamily: sans, fontSize: 11, color: PAL.muted, marginTop: 1 }}>
                  {s.type === "formation_continue" ? "Formation continue" : "Formation initiale"} · {programCount.get(s.name) ?? 0} salle{(programCount.get(s.name) ?? 0) > 1 ? "s" : ""}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <SectionLabel>Salles</SectionLabel>
      {loading ? (
        <div className="dash-card" style={{ padding: 22 }}><div className="shimmer" style={{ height: 16, width: 160, borderRadius: 999 }} /></div>
      ) : rooms.length === 0 ? (
        <div className="dash-card">
          <EmptyHint icon={<Building2 size={26} strokeWidth={1.7} />} text="Aucune salle — créez-en une ou validez un emploi du temps qui en indique." />
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
          {rooms.map(r => <RoomCard key={r.room} r={r} onOpen={() => setSelected(r)} />)}
        </div>
      )}
    </div>
  );
}
