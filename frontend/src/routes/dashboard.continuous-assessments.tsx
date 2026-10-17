import { createFileRoute, redirect, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { api, ApiError } from "@/lib/api";
import { toast } from "sonner";
import { FileText, Plus, Loader2, Trash2, Download, Pencil } from "lucide-react";
import { PageHead, SectionLabel, EmptyHint } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/continuous-assessments")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: ContinuousAssessmentsPage,
});

type Assessment = {
  id: string;
  title: string;
  filiere: string | null;
  niveau: string | null;
  status: "draft" | "published";
  section_count: number;
  total_points: number;
  created_at: string;
};

function statusLabel(s: Assessment["status"]) {
  return s === "published" ? "Finalisé" : "Brouillon";
}

function ContinuousAssessmentsPage() {
  const { roles } = useAuth();
  const navigate = useNavigate();
  const canCreate = roles.includes("admin") || roles.includes("professor");

  const [items, setItems] = useState<Assessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      const data: Assessment[] = await api.get("/api/continuous-assessments");
      setItems(data);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (!canCreate) {
    return (
      <div className="dash-card p-6">
        <EmptyHint icon={<FileText size={28} strokeWidth={1.7} />} text="Réservé aux formateurs et administrateurs." />
      </div>
    );
  }

  async function remove(a: Assessment) {
    if (!window.confirm(`Supprimer « ${a.title} » ?`)) return;
    setBusyId(a.id);
    try {
      await api.delete(`/api/continuous-assessments/${a.id}`);
      toast.success("Contrôle continu supprimé.");
      load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Échec de la suppression.");
    } finally {
      setBusyId(null);
    }
  }

  async function exportDocx(a: Assessment) {
    setBusyId(a.id);
    try {
      await api.download(`/api/continuous-assessments/${a.id}/export.docx`, `Controle_continu_${a.title}.docx`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Échec de l'export.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHead
        eyebrow="Pédagogique"
        title="Contrôle continu — Épreuves écrites"
        sub="Générées par IA à partir de plusieurs cours, sur le modèle officiel de l'établissement. Export Word (Questions + Corrigé type)."
        actions={
          <button type="button" className="btn-c btn-c-primary" onClick={() => navigate({ to: "/dashboard/continuous-assessments/new" })}>
            <Plus size={15} strokeWidth={1.8} />Nouvelle épreuve
          </button>
        }
      />

      <SectionLabel>{items.length} épreuve{items.length !== 1 ? "s" : ""}</SectionLabel>

      {loading ? (
        <div className="dash-card p-6">
          <div className="shimmer" style={{ height: 18, width: 200, borderRadius: 999 }} />
        </div>
      ) : items.length === 0 ? (
        <div className="dash-card p-6">
          <EmptyHint icon={<FileText size={28} strokeWidth={1.7} />} text="Aucune épreuve de contrôle continu pour le moment." />
        </div>
      ) : (
        <div className="dash-card overflow-hidden">
          {items.map(a => (
            <div key={a.id} className="row-c flex-wrap">
              <span className="flex shrink-0" style={{ color: "var(--pal-primary)" }}>
                <FileText size={18} strokeWidth={1.7} />
              </span>
              <div className="min-w-0 flex-1" style={{ minWidth: 180 }}>
                <Link to="/dashboard/continuous-assessments/$assessmentId/editor" params={{ assessmentId: a.id }} className="font-semibold text-sm hover:underline">
                  {a.title}
                </Link>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {[a.filiere, a.niveau].filter(Boolean).join(" · ") || "—"} · {a.section_count} exercice{a.section_count !== 1 ? "s" : ""} · {a.total_points} pts
                </div>
              </div>
              <span className={`chip-c ${a.status === "published" ? "chip-c-green" : "chip-c-amber"}`}>{statusLabel(a.status)}</span>
              <button type="button" onClick={() => exportDocx(a)} disabled={busyId === a.id} className="btn-c btn-c-ghost btn-c-sm" title="Exporter en Word">
                {busyId === a.id ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} strokeWidth={1.7} />}
              </button>
              <Link to="/dashboard/continuous-assessments/$assessmentId/editor" params={{ assessmentId: a.id }} className="btn-c btn-c-ghost btn-c-sm" title="Modifier">
                <Pencil size={14} strokeWidth={1.7} />
              </Link>
              <button type="button" onClick={() => remove(a)} disabled={busyId === a.id} className="btn-c btn-c-ghost btn-c-sm" style={{ color: "var(--pal-danger)" }} title="Supprimer">
                <Trash2 size={14} strokeWidth={1.7} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
