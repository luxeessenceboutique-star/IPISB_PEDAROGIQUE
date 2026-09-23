import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Search, IdCard, Loader2, X } from "lucide-react";
import { PageHead, SectionLabel, EmptyHint, DashAvatar } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/students")({
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
  component: StudentsPage,
});

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  muted:   "oklch(48% 0.02 180)",
  primary: "oklch(48% 0.085 175)",
  line:    "oklch(88% 0.015 170)",
  cream:   "oklch(97% 0.012 90)",
  paper:   "oklch(99% 0.005 160)",
  danger:  "oklch(64% 0.18 25)",
  success: "oklch(55% 0.14 150)",
};
const sans = '"Manrope", system-ui, sans-serif';

type Student = {
  id: string;
  email: string | null;
  full_name: string | null;
  statut: string;
  photo_url: string | null;
  created_at: string;
};

const STATUTS = ["actif", "suspendu", "diplome", "abandon"];
const STATUT_LABEL: Record<string, string> = {
  actif: "Actif", suspendu: "Suspendu", diplome: "Diplômé", abandon: "Abandon",
};

function statutTone(s: string) {
  if (s === "actif") return "chip-c-green";
  if (s === "suspendu" || s === "abandon") return "chip-c-red";
  return "";
}

function EditDrawer({ student, onClose, onSaved }: { student: Student; onClose: () => void; onSaved: () => void }) {
  const [statut, setStatut] = useState(student.statut);
  const [photoUrl, setPhotoUrl] = useState(student.photo_url ?? "");
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      await api.patch(`/api/students/${student.id}`, { statut, photo_url: photoUrl || null });
      toast.success("Fiche mise à jour.");
      onSaved();
      onClose();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la mise à jour.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 16, padding: 32, width: 440, maxWidth: "95vw", boxShadow: "0 24px 60px rgba(0,0,0,.18)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <DashAvatar name={student.full_name ?? student.email ?? "?"} size={40} tone="primary" />
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, color: PAL.ink }}>{student.full_name || "—"}</div>
              <div style={{ fontSize: 12, color: PAL.muted }}>{student.email}</div>
            </div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted }}><X size={18} /></button>
        </div>

        <label style={{ fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const }}>Statut</label>
        <select
          value={statut}
          onChange={e => setStatut(e.target.value)}
          className="u-input"
          style={{ marginTop: 8, marginBottom: 16, width: "100%", padding: "11px 14px", border: `1px solid ${PAL.line}`, borderRadius: 10, fontFamily: sans, fontSize: 14, color: PAL.ink, background: PAL.paper, outline: "none" }}
        >
          {STATUTS.map(s => <option key={s} value={s}>{STATUT_LABEL[s]}</option>)}
        </select>

        <label style={{ fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const }}>Photo (URL)</label>
        <input
          type="text"
          value={photoUrl}
          onChange={e => setPhotoUrl(e.target.value)}
          placeholder="https://…"
          className="u-input"
          style={{ marginTop: 8, marginBottom: 24, width: "100%", padding: "11px 14px", border: `1px solid ${PAL.line}`, borderRadius: 10, fontFamily: sans, fontSize: 14, color: PAL.ink, background: PAL.paper, outline: "none", boxSizing: "border-box" as const }}
        />

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} className="u-ghost" style={{ fontFamily: sans, fontSize: 13, color: PAL.muted, background: "transparent", border: `1px solid ${PAL.line}`, borderRadius: 8, padding: "10px 18px", cursor: "pointer" }}>Annuler</button>
          <button onClick={save} disabled={saving} style={{ fontFamily: sans, fontSize: 13, fontWeight: 600, color: PAL.paper, background: PAL.ink, border: 0, borderRadius: 8, padding: "10px 24px", cursor: saving ? "not-allowed" : "pointer", opacity: saving ? .6 : 1 }}>
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StudentsPage() {
  const navigate = useNavigate();
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");
  const [statut, setStatut] = useState("");
  const [editing, setEditing] = useState<Student | null>(null);

  async function load() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (statut) params.set("statut", statut);
      const qs = params.toString();
      const data: Student[] = await api.get(`/api/students${qs ? `?${qs}` : ""}`);
      setStudents(data);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors du chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = setTimeout(load, 250); // debounce search
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, statut]);

  return (
    <div style={{ fontFamily: sans }}>
      {editing && (
        <EditDrawer student={editing} onClose={() => setEditing(null)} onSaved={load} />
      )}

      <PageHead
        eyebrow="Gestion administrative"
        title="Registre des stagiaires"
        sub="Recherchez, filtrez et mettez à jour le statut des stagiaires."
      />

      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        <div style={{ position: "relative", flex: "1 1 260px" }}>
          <Search size={15} strokeWidth={1.7} style={{ position: "absolute", insetInlineStart: 14, top: "50%", transform: "translateY(-50%)", color: PAL.muted }} />
          <input
            type="text"
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Rechercher par nom ou e-mail…"
            className="u-input"
            style={{ width: "100%", padding: "11px 14px 11px 40px", border: `1px solid ${PAL.line}`, borderRadius: 10, fontFamily: sans, fontSize: 14, color: PAL.ink, background: PAL.paper, outline: "none", boxSizing: "border-box" as const }}
          />
        </div>
        <select
          value={statut}
          onChange={e => setStatut(e.target.value)}
          className="u-input"
          style={{ padding: "11px 14px", border: `1px solid ${PAL.line}`, borderRadius: 10, fontFamily: sans, fontSize: 14, color: statut ? PAL.ink : PAL.muted, background: PAL.paper, outline: "none" }}
        >
          <option value="">Tous les statuts</option>
          {STATUTS.map(s => <option key={s} value={s}>{STATUT_LABEL[s]}</option>)}
        </select>
      </div>

      <SectionLabel>{students.length} stagiaire{students.length !== 1 ? "s" : ""}</SectionLabel>

      {loading ? (
        <div className="dash-card" style={{ padding: 26 }}>
          <div className="shimmer" style={{ height: 18, width: 180, borderRadius: 999 }} />
          <div className="shimmer" style={{ height: 26, width: "55%", borderRadius: 8, marginTop: 14 }} />
        </div>
      ) : students.length === 0 ? (
        <div className="dash-card">
          <EmptyHint icon={<IdCard size={28} strokeWidth={1.7} />} text="Aucun stagiaire trouvé." />
        </div>
      ) : (
        <div className="dash-card overflow-hidden">
          {students.map(s => (
            <div
              key={s.id}
              className="row-c flex-wrap"
              onClick={() => navigate({ to: "/dashboard/students/$studentId", params: { studentId: s.id } })}
              style={{ cursor: "pointer" }}
            >
              {s.photo_url ? (
                <img
                  src={s.photo_url}
                  alt=""
                  style={{ width: 34, height: 34, borderRadius: 999, objectFit: "cover", flexShrink: 0 }}
                  onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <DashAvatar name={s.full_name || s.email || "?"} size={34} tone="mid" />
              )}
              <div className="min-w-0 flex-1" style={{ minWidth: 180 }}>
                <div style={{ fontWeight: 700, fontSize: 14, color: PAL.ink }}>{s.full_name || "—"}</div>
                <div className="mt-0.5" style={{ fontSize: 12, color: PAL.muted }}>{s.email}</div>
              </div>
              <span className={`chip-c ${statutTone(s.statut)}`}>{STATUT_LABEL[s.statut] ?? s.statut}</span>
              <button
                type="button"
                onClick={e => { e.stopPropagation(); setEditing(s); }}
                className="btn-c btn-c-sm btn-c-ghost"
                title="Modifier statut/photo"
              >
                Modifier
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
