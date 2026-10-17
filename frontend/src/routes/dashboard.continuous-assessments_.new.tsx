import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { ArrowLeft, Loader2, Sparkles } from "lucide-react";
import { PageHead } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/continuous-assessments_/new")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: NewContinuousAssessmentPage,
});

type Course = { id: string; title: string };

function NewContinuousAssessmentPage() {
  const navigate = useNavigate();

  const [courses, setCourses] = useState<Course[]>([]);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const [title, setTitle] = useState("");
  const [filiere, setFiliere] = useState("");
  const [niveau, setNiveau] = useState("");
  const [formateur, setFormateur] = useState("");
  const [dateEvaluation, setDateEvaluation] = useState("");
  const [dureeEpreuve, setDureeEpreuve] = useState("");
  const [totalPoints, setTotalPoints] = useState("20");
  const [instructions, setInstructions] = useState("");
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    (async () => {
      setLoadingCourses(true);
      try {
        const data: Array<{ id: string; title: string }> = await api.get("/api/courses");
        setCourses(data.map(c => ({ id: c.id, title: c.title })));
      } catch (e) {
        toast.error(e instanceof ApiError ? e.message : "Erreur de chargement des cours.");
      } finally {
        setLoadingCourses(false);
      }
    })();
  }, []);

  const selectedTitles = useMemo(
    () => courses.filter(c => selected.has(c.id)).map(c => c.title).join(", "),
    [courses, selected],
  );

  function toggleCourse(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function generate() {
    if (selected.size === 0) { toast.error("Sélectionnez au moins un cours."); return; }
    if (!title.trim()) { toast.error("Le titre est obligatoire."); return; }
    const points = parseFloat(totalPoints) || 20;

    setGenerating(true);
    try {
      const assessment = await api.post("/api/continuous-assessments/generate", {
        title: title.trim(),
        course_ids: Array.from(selected),
        filiere: filiere.trim() || null,
        niveau: niveau.trim() || null,
        formateur: formateur.trim() || null,
        date_evaluation: dateEvaluation || null,
        duree_epreuve: dureeEpreuve.trim() || null,
        total_points: points,
        instructions: instructions.trim() || null,
      });
      toast.success("Contrôle continu généré — vous pouvez maintenant le relire et l'éditer.");
      navigate({ to: "/dashboard/continuous-assessments/$assessmentId/editor", params: { assessmentId: assessment.id } });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Échec de la génération.");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHead
        eyebrow="Contrôle continu"
        title="Générer une épreuve"
        sub="L'IA rédige les exercices (consigne + barème + corrigé) à partir du contenu réellement publié des cours sélectionnés."
        actions={
          <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => navigate({ to: "/dashboard/continuous-assessments" })}>
            <ArrowLeft size={14} strokeWidth={1.7} />Retour
          </button>
        }
      />

      <div className="space-y-5">
        <div className="dash-card p-5">
          <label className="text-sm font-medium">Cours * <span className="text-xs text-muted-foreground font-normal">(sélection multiple)</span></label>
          {loadingCourses ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Chargement…</div>
          ) : courses.length === 0 ? (
            <p className="py-4 text-sm text-muted-foreground">Aucun cours trouvé.</p>
          ) : (
            <div className="mt-2 max-h-72 space-y-1 overflow-y-auto rounded-xl border border-border p-2">
              {courses.map(c => (
                <label key={c.id} className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm hover:bg-muted/50">
                  <input type="checkbox" checked={selected.has(c.id)} onChange={() => toggleCourse(c.id)} className="h-4 w-4 accent-[var(--pal-primary)]" />
                  {c.title}
                </label>
              ))}
            </div>
          )}
          {selected.size > 0 && (
            <p className="mt-2 text-xs text-muted-foreground">Basé sur : {selectedTitles}</p>
          )}
        </div>

        <div className="dash-card space-y-4 p-5">
          <div>
            <label className="text-sm font-medium">Titre *</label>
            <Input className="mt-1.5" value={title} onChange={e => setTitle(e.target.value)} placeholder="ex. Contrôle continu — Microbio-parasito-entomologie" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Filière</label>
              <Input className="mt-1.5" value={filiere} onChange={e => setFiliere(e.target.value)} placeholder="ex. Infirmier Auxiliaire" />
            </div>
            <div>
              <label className="text-sm font-medium">Niveau</label>
              <Input className="mt-1.5" value={niveau} onChange={e => setNiveau(e.target.value)} placeholder="ex. 1ère année" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Date de l'évaluation</label>
              <Input className="mt-1.5" type="date" value={dateEvaluation} onChange={e => setDateEvaluation(e.target.value)} />
            </div>
            <div>
              <label className="text-sm font-medium">Durée de l'épreuve</label>
              <Input className="mt-1.5" value={dureeEpreuve} onChange={e => setDureeEpreuve(e.target.value)} placeholder="ex. 1h" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Formateur</label>
              <Input className="mt-1.5" value={formateur} onChange={e => setFormateur(e.target.value)} placeholder="Nom du formateur" />
            </div>
            <div>
              <label className="text-sm font-medium">Barème total</label>
              <Input className="mt-1.5" type="number" min="1" step="0.5" value={totalPoints} onChange={e => setTotalPoints(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Consignes pour l'IA <span className="text-xs text-muted-foreground font-normal">(facultatif)</span></label>
            <Textarea className="mt-1.5" rows={3} value={instructions} onChange={e => setInstructions(e.target.value)}
              placeholder="ex. Mettre l'accent sur les définitions et les études de cas, éviter les questions purement théoriques." />
          </div>
        </div>

        <div className="flex justify-end">
          <Button className="border-0 bg-gradient-brand text-white" onClick={generate} disabled={generating}>
            {generating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
            {generating ? "Génération en cours…" : "Générer avec l'IA"}
          </Button>
        </div>
      </div>
    </div>
  );
}
