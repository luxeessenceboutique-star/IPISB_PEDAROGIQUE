import { createFileRoute, redirect, useNavigate, useParams } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api, ApiError } from "@/lib/api";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { ArrowLeft, Download, Loader2, Plus, Trash2, Save, CheckCircle2, RotateCcw } from "lucide-react";
import { PageHead } from "@/components/dashboard/ui";
import { RichTextField } from "@/components/continuous-assessments/RichTextField";

export const Route = createFileRoute("/dashboard/continuous-assessments_/$assessmentId_/editor")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: ContinuousAssessmentEditorPage,
});

type Section = { id: string; consigne: string; bareme: number; corrige: string };
type Assessment = {
  id: string; title: string; filiere: string | null; niveau: string | null;
  formateur: string | null; date_evaluation: string | null; duree_epreuve: string | null;
  total_points: number; sections: Section[]; status: "draft" | "published";
};

const labelStyle = { fontFamily: '"Manrope", system-ui, sans-serif', fontSize: 11, fontWeight: 600, color: "oklch(48% 0.02 180)", letterSpacing: ".08em", textTransform: "uppercase" as const };

function newSectionId(sections: Section[]) {
  const n = sections.reduce((max, s) => {
    const m = /^s(\d+)$/.exec(s.id);
    return m ? Math.max(max, parseInt(m[1], 10)) : max;
  }, 0);
  return `s${n + 1}`;
}

function ContinuousAssessmentEditorPage() {
  const { assessmentId } = useParams({ from: "/dashboard/continuous-assessments_/$assessmentId_/editor" });
  const navigate = useNavigate();

  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [dirty, setDirty] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const data: Assessment = await api.get(`/api/continuous-assessments/${assessmentId}`);
      setAssessment(data);
      setDirty(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Erreur de chargement.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [assessmentId]);

  function patch(fields: Partial<Assessment>) {
    setAssessment(a => (a ? { ...a, ...fields } : a));
    setDirty(true);
  }

  function patchSection(id: string, fields: Partial<Section>) {
    setAssessment(a => a ? { ...a, sections: a.sections.map(s => s.id === id ? { ...s, ...fields } : s) } : a);
    setDirty(true);
  }

  function addSection() {
    setAssessment(a => a ? { ...a, sections: [...a.sections, { id: newSectionId(a.sections), consigne: "", bareme: 0, corrige: "" }] } : a);
    setDirty(true);
  }

  function removeSection(id: string) {
    if (!window.confirm("Supprimer cet exercice ?")) return;
    setAssessment(a => a ? { ...a, sections: a.sections.filter(s => s.id !== id) } : a);
    setDirty(true);
  }

  async function aiRewrite(html: string, instruction: string): Promise<string> {
    try {
      const res: { html: string } = await api.post("/api/continuous-assessments/ai-edit", { html, instruction });
      return res.html;
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Échec de la réécriture IA.");
      throw e;
    }
  }

  async function save() {
    if (!assessment) return;
    setSaving(true);
    try {
      await api.patch(`/api/continuous-assessments/${assessment.id}`, {
        title: assessment.title,
        filiere: assessment.filiere,
        niveau: assessment.niveau,
        formateur: assessment.formateur,
        date_evaluation: assessment.date_evaluation,
        duree_epreuve: assessment.duree_epreuve,
        total_points: assessment.total_points,
        sections: assessment.sections,
      });
      toast.success("Enregistré.");
      setDirty(false);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Échec de l'enregistrement.");
    } finally {
      setSaving(false);
    }
  }

  async function togglePublish() {
    if (!assessment) return;
    const next = assessment.status === "published" ? "draft" : "published";
    try {
      await api.patch(`/api/continuous-assessments/${assessment.id}`, { status: next });
      patch({ status: next });
      setDirty(false);
      toast.success(next === "published" ? "Épreuve finalisée." : "Repassée en brouillon.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Échec.");
    }
  }

  async function exportDocx() {
    if (!assessment) return;
    if (dirty) { toast.error("Enregistrez vos modifications avant d'exporter."); return; }
    setExporting(true);
    try {
      await api.download(`/api/continuous-assessments/${assessment.id}/export.docx`, `Controle_continu_${assessment.title}.docx`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Échec de l'export.");
    } finally {
      setExporting(false);
    }
  }

  if (loading) {
    return <div className="dash-card p-6"><div className="shimmer" style={{ height: 18, width: 220, borderRadius: 999 }} /></div>;
  }
  if (!assessment) return null;

  const bareme_sum = assessment.sections.reduce((s, x) => s + (x.bareme || 0), 0);
  const bareme_ok = Math.abs(bareme_sum - assessment.total_points) < 0.01;

  return (
    <div className="mx-auto max-w-3xl pb-16">
      <PageHead
        eyebrow="Contrôle continu"
        title={assessment.title}
        sub={`${assessment.sections.length} exercice${assessment.sections.length !== 1 ? "s" : ""} · ${bareme_sum}/${assessment.total_points} pts${assessment.status === "published" ? " · Finalisé" : " · Brouillon"}`}
        actions={
          <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => navigate({ to: "/dashboard/continuous-assessments" })}>
            <ArrowLeft size={14} strokeWidth={1.7} />Retour
          </button>
        }
      />

      <div className="dash-card space-y-4 p-5 mb-5">
        <div>
          <label style={labelStyle}>Titre</label>
          <Input className="mt-1.5" value={assessment.title} onChange={e => patch({ title: e.target.value })} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label style={labelStyle}>Filière</label>
            <Input className="mt-1.5" value={assessment.filiere ?? ""} onChange={e => patch({ filiere: e.target.value })} />
          </div>
          <div>
            <label style={labelStyle}>Niveau</label>
            <Input className="mt-1.5" value={assessment.niveau ?? ""} onChange={e => patch({ niveau: e.target.value })} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label style={labelStyle}>Date de l'évaluation</label>
            <Input className="mt-1.5" type="date" value={assessment.date_evaluation ?? ""} onChange={e => patch({ date_evaluation: e.target.value })} />
          </div>
          <div>
            <label style={labelStyle}>Durée de l'épreuve</label>
            <Input className="mt-1.5" value={assessment.duree_epreuve ?? ""} onChange={e => patch({ duree_epreuve: e.target.value })} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label style={labelStyle}>Formateur</label>
            <Input className="mt-1.5" value={assessment.formateur ?? ""} onChange={e => patch({ formateur: e.target.value })} />
          </div>
          <div>
            <label style={labelStyle}>Barème total</label>
            <Input className="mt-1.5" type="number" min="1" step="0.5" value={assessment.total_points} onChange={e => patch({ total_points: parseFloat(e.target.value) || 0 })} />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold font-display">Exercices</span>
        <span className={`text-xs ${bareme_ok ? "text-muted-foreground" : "text-destructive font-medium"}`}>
          Total barème : {bareme_sum} / {assessment.total_points} pts{!bareme_ok && " — à ajuster"}
        </span>
      </div>

      <div className="space-y-4">
        {assessment.sections.map((s, i) => (
          <div key={s.id} className="dash-card p-4">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-sm font-semibold font-display">Exercice {i + 1}</span>
              <Input type="number" min="0" step="0.5" value={s.bareme} onChange={e => patchSection(s.id, { bareme: parseFloat(e.target.value) || 0 })}
                className="h-7 w-20 text-sm ml-2" />
              <span className="text-xs text-muted-foreground">pts</span>
              <button type="button" onClick={() => removeSection(s.id)} className="ml-auto btn-c btn-c-ghost btn-c-sm" style={{ color: "var(--pal-danger)" }} title="Supprimer l'exercice">
                <Trash2 size={13} strokeWidth={1.7} />
              </button>
            </div>
            <div className="space-y-3">
              <RichTextField
                label="Consigne (énoncé étudiant)"
                value={s.consigne}
                onChange={html => patchSection(s.id, { consigne: html })}
                onAiRewrite={instruction => aiRewrite(s.consigne, instruction)}
                placeholder="Énoncé de l'exercice…"
              />
              <RichTextField
                label="Corrigé type"
                value={s.corrige}
                onChange={html => patchSection(s.id, { corrige: html })}
                onAiRewrite={instruction => aiRewrite(s.corrige, instruction)}
                placeholder="Réponse modèle attendue…"
              />
            </div>
          </div>
        ))}

        <button type="button" onClick={addSection} className="btn-c btn-c-soft w-full justify-center">
          <Plus size={15} strokeWidth={1.8} />Ajouter un exercice
        </button>
      </div>

      <div className="sticky bottom-0 mt-6 flex items-center justify-between gap-2 rounded-xl border border-border bg-background/95 p-3 backdrop-blur">
        <button type="button" onClick={togglePublish} className="btn-c btn-c-ghost btn-c-sm">
          {assessment.status === "published" ? <RotateCcw size={14} strokeWidth={1.7} /> : <CheckCircle2 size={14} strokeWidth={1.7} />}
          {assessment.status === "published" ? "Repasser en brouillon" : "Finaliser"}
        </button>
        <div className="flex items-center gap-2">
          <button type="button" onClick={exportDocx} disabled={exporting} className="btn-c btn-c-ghost">
            {exporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} strokeWidth={1.8} />}
            Exporter en Word
          </button>
          <button type="button" onClick={save} disabled={saving || !dirty} className="btn-c btn-c-primary">
            {saving ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} strokeWidth={1.8} />}
            {saving ? "Enregistrement…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}
