import { createFileRoute, redirect } from "@tanstack/react-router";
import { Fragment, useCallback, useEffect, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { toast } from "sonner";
import { Award, ChevronDown, ChevronRight, Save, Plus, X, Trash2, SlidersHorizontal, Pencil, Gavel, FileSpreadsheet, FileText } from "lucide-react";
import { PageHead, SectionLabel, EmptyHint } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/grades")({
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
  component: GradesPage,
});

const PAL = {
  ink: "oklch(22% 0.025 175)", muted: "oklch(48% 0.02 180)", line: "oklch(88% 0.015 170)", paper: "oklch(99% 0.005 160)",
};
const sans = '"Manrope", system-ui, sans-serif';
const mono = '"JetBrains Mono", ui-monospace, monospace';

const fieldStyle = { padding: "9px 12px", border: `1px solid ${PAL.line}`, borderRadius: 8, fontFamily: sans, fontSize: 13, color: PAL.ink, background: PAL.paper, outline: "none", boxSizing: "border-box" as const };

type ClassItem = { id: string; name: string; formation_code?: string | null };
type StudentItem = { id: string; full_name: string | null; email: string };
type CourseGrade = { course_id: string; title: string | null; coefficient: number; grade: number | null };
type OverallGrade = { average: number | null; courses: CourseGrade[] };
type CourseItem = { id: string; title: string; assigned_classes: { id: string; name: string }[] };
type ModuleGrade = { grade: number | null; devoir_avg: number | null; exam_avg: number | null; quiz_avg: number | null };
type QuickCategory = "devoir" | "exam";
type QuickAssignment = { id: string; title: string; max_grade: number; quick_grade_category: QuickCategory; grades: Record<string, number | null> };

// MG1 = moyenne générale de la cohorte (MPCC1 × MPEFCFT1 × MPEFCFP1, cf.
// GET /classes/{id}/mg1-summary) — en plus de la moyenne par module déjà
// affichée, c'est le pendant natif des feuilles "P1 G1"/"Modalité de
// passage" de l'ancien classeur Excel.
type ClassSummary = { mpcc1: number | null; mpefcft1: number | null; mpefcfp1: number | null; mg1: number | null };
type StageEntry = { grade: number | null; coefficient: number };

// Décision du jury (admission) par élève — cf. GET/PUT /classes/{id}/decisions.
// status/mention peuvent être une vraie valeur enregistrée (is_override=true)
// ou une simple suggestion dérivée de MG1 (is_override=false) ; "a_examiner"
// n'est qu'un sentinel d'affichage, jamais une valeur stockable en base.
type DecisionStatus = "admis" | "admis_avec_rachat" | "non_admis_redouble" | "redouble_exceptionnel" | "reoriente" | "exclu";
type DecisionEntry = {
  status: DecisionStatus | "a_examiner" | null;
  mention: string | null;
  suggested_status: DecisionStatus | "a_examiner" | null;
  suggested_mention: string | null;
  is_override: boolean;
};
type JuryMember = { name: string; role: string };

const CATEGORY_LABELS: Record<QuickCategory, string> = { devoir: "Contrôle continu", exam: "Examen" };

// Les 6 seules valeurs acceptées par le backend (CHECK constraint de
// class_student_decisions.status) — "a_examiner" n'y figure pas exprès.
const DECISION_STATUS_OPTIONS: { value: DecisionStatus; label: string }[] = [
  { value: "admis", label: "Admis" },
  { value: "admis_avec_rachat", label: "Admis avec rachat" },
  { value: "non_admis_redouble", label: "Non admis — autorisé à redoubler" },
  { value: "redouble_exceptionnel", label: "Autorisé exceptionnellement à redoubler" },
  { value: "reoriente", label: "Réorienté vers une autre filière" },
  { value: "exclu", label: "Exclu" },
];

const DECISION_LABELS: Record<string, string> = {
  admis: "Admis",
  admis_avec_rachat: "Admis avec rachat",
  non_admis_redouble: "Non admis — autorisé à redoubler",
  redouble_exceptionnel: "Autorisé exceptionnellement à redoubler",
  reoriente: "Réorienté vers une autre filière",
  exclu: "Exclu",
  a_examiner: "À examiner",
};

function decisionChipClass(status: string | null): string {
  if (status === "admis") return "chip-c-green";
  if (status === "exclu" || status === "non_admis_redouble") return "chip-c-red";
  if (status === "admis_avec_rachat" || status === "redouble_exceptionnel" || status === "reoriente" || status === "a_examiner") return "chip-c-amber";
  return "chip-c-blue";
}

function gradeColor(v: number | null): string {
  if (v == null) return PAL.muted;
  return v >= 10 ? "var(--pal-good, #2f8f5b)" : "var(--pal-danger, #c0392b)";
}

// Pondération Examens/Contrôle continu/Quiz d'un module — même config que
// dashboard.courses.tsx (GET/PUT /courses/{id}/grade-weights), rendue
// accessible directement depuis la page Notes pour ne pas obliger le
// professeur à changer de page pendant la saisie des notes.
function WeightsModal({ courseId, courseTitle, onClose }: { courseId: string; courseTitle: string; onClose: () => void }) {
  const [weights, setWeights] = useState({ exam_weight: 50, devoir_weight: 30, quiz_weight: 20 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get(`/api/courses/${courseId}/grade-weights`)
      .then(d => setWeights({ exam_weight: d.exam_weight, devoir_weight: d.devoir_weight, quiz_weight: d.quiz_weight }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [courseId]);

  const total = weights.exam_weight + weights.devoir_weight + weights.quiz_weight;

  async function save() {
    if (total !== 100) { toast.error(`Les pourcentages doivent totaliser 100 (actuellement ${total}).`); return; }
    setSaving(true);
    try {
      await api.put(`/api/courses/${courseId}/grade-weights`, weights);
      toast.success("Pondération enregistrée.");
      onClose();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 14, padding: 26, width: 400, maxWidth: "94vw", boxShadow: "0 20px 50px rgba(0,0,0,.15)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 6 }}>
          <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 20, fontWeight: 500, color: PAL.ink, margin: 0 }}>Pondération — {courseTitle}</h2>
          <button onClick={onClose} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted, marginTop: 2 }}><X size={17} strokeWidth={1.7} /></button>
        </div>
        {loading ? (
          <div className="shimmer" style={{ height: 16, width: 200, borderRadius: 999, marginTop: 14 }} />
        ) : (
          <>
            <p style={{ fontSize: 12, color: PAL.muted, marginTop: 8, marginBottom: 14, lineHeight: 1.5 }}>
              Répartition de la note finale entre catégories d'évaluation (doit totaliser 100%). Chaque catégorie sans note aujourd'hui sera automatiquement ignorée dans le calcul.
            </p>
            {[
              { key: "exam_weight" as const, label: "Examens" },
              { key: "devoir_weight" as const, label: "Contrôle continu" },
              { key: "quiz_weight" as const, label: "Quiz" },
            ].map(f => (
              <div key={f.key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <label style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: PAL.ink }}>{f.label}</label>
                <input
                  type="number" min={0} max={100}
                  value={weights[f.key]}
                  onChange={e => setWeights(w => ({ ...w, [f.key]: parseInt(e.target.value, 10) || 0 }))}
                  style={{ ...fieldStyle, width: 80, textAlign: "right" }}
                />
                <span style={{ fontSize: 13, color: PAL.muted }}>%</span>
              </div>
            ))}
            <div style={{ textAlign: "right", fontSize: 12, fontWeight: 600, color: total === 100 ? "var(--pal-good, #2f8f5b)" : "var(--pal-danger, #c0392b)", marginBottom: 4 }}>
              Total : {total}%
            </div>
          </>
        )}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 14 }}>
          <button onClick={onClose} className="btn-c btn-c-ghost">Annuler</button>
          <button onClick={save} disabled={saving || loading} className="btn-c btn-c-primary" style={{ opacity: saving || loading ? 0.6 : 1 }}>
            {saving ? "…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Note de Stage — une seule par élève par classe, non rattachée à un
// module (cf. GET/PUT /classes/{id}/stage-grades). Même squelette que
// WeightsModal, en plus large (liste d'élèves).
function StageModal({ classId, students, onClose }: { classId: string; students: StudentItem[]; onClose: () => void }) {
  const [entries, setEntries] = useState<Record<string, StageEntry>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get(`/api/classes/${classId}/stage-grades`)
      .then((d: Record<string, { grade: number | null; coefficient: number }>) => {
        const next: Record<string, StageEntry> = {};
        students.forEach(s => { next[s.id] = d[s.id] ? { grade: d[s.id].grade, coefficient: d[s.id].coefficient } : { grade: null, coefficient: 3 }; });
        setEntries(next);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [classId]);

  async function save() {
    setSaving(true);
    try {
      await api.put(`/api/classes/${classId}/stage-grades`, { grades: entries });
      toast.success("Notes de stage enregistrées.");
      onClose();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 14, padding: 26, width: 460, maxWidth: "94vw", maxHeight: "85vh", overflowY: "auto", boxShadow: "0 20px 50px rgba(0,0,0,.15)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 6 }}>
          <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 20, fontWeight: 500, color: PAL.ink, margin: 0 }}>Note de Stage</h2>
          <button onClick={onClose} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted, marginTop: 2 }}><X size={17} strokeWidth={1.7} /></button>
        </div>
        {loading ? (
          <div className="shimmer" style={{ height: 16, width: 200, borderRadius: 999, marginTop: 14 }} />
        ) : (
          <>
            <p style={{ fontSize: 12, color: PAL.muted, marginTop: 8, marginBottom: 14, lineHeight: 1.5 }}>
              Une note par élève, comptée dans MPEFCFP1 avec son propre coefficient (défaut 3, comme dans l'ancien classeur).
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {students.map(s => (
                <div key={s.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0" }}>
                  <span style={{ flex: 1, fontSize: 13, color: PAL.ink }}>{s.full_name || s.email}</span>
                  <input
                    type="number" min={0} step="0.25" placeholder="—"
                    value={entries[s.id]?.grade ?? ""}
                    onChange={e => setEntries(m => ({ ...m, [s.id]: { ...(m[s.id] ?? { coefficient: 3 }), grade: e.target.value === "" ? null : parseFloat(e.target.value) } }))}
                    style={{ ...fieldStyle, width: 72, textAlign: "right", padding: "6px 8px" }}
                  />
                  <input
                    type="number" min={0.5} step="0.5" title="Coefficient"
                    value={entries[s.id]?.coefficient ?? 3}
                    onChange={e => setEntries(m => ({ ...m, [s.id]: { ...(m[s.id] ?? { grade: null }), coefficient: parseFloat(e.target.value) || 3 } }))}
                    style={{ ...fieldStyle, width: 56, textAlign: "right", padding: "6px 8px", color: PAL.muted }}
                  />
                </div>
              ))}
            </div>
          </>
        )}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 14 }}>
          <button onClick={onClose} className="btn-c btn-c-ghost">Annuler</button>
          <button onClick={save} disabled={saving || loading} className="btn-c btn-c-primary" style={{ opacity: saving || loading ? 0.6 : 1 }}>
            {saving ? "…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Pondération de la moyenne générale (MG1) — à la différence de
// WeightsModal (pourcentages d'un module, somme=100), ici les 3 poids
// sont des coefficients libres (défaut 3/2/3, comme l'ancien classeur
// Excel qui divise par 8, pas par 100).
function ClassWeightsModal({ classId, onClose }: { classId: string; onClose: () => void }) {
  const [weights, setWeights] = useState({ cc_weight: 3, efcf_th_weight: 2, efcf_pr_weight: 3 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get(`/api/classes/${classId}/grade-weights`)
      .then(d => setWeights({ cc_weight: d.cc_weight, efcf_th_weight: d.efcf_th_weight, efcf_pr_weight: d.efcf_pr_weight }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [classId]);

  const total = weights.cc_weight + weights.efcf_th_weight + weights.efcf_pr_weight;

  async function save() {
    if (weights.cc_weight <= 0 || weights.efcf_th_weight <= 0 || weights.efcf_pr_weight <= 0) {
      toast.error("Les poids doivent être strictement positifs.");
      return;
    }
    setSaving(true);
    try {
      await api.put(`/api/classes/${classId}/grade-weights`, weights);
      toast.success("Pondération enregistrée.");
      onClose();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 14, padding: 26, width: 400, maxWidth: "94vw", boxShadow: "0 20px 50px rgba(0,0,0,.15)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 6 }}>
          <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 20, fontWeight: 500, color: PAL.ink, margin: 0 }}>Pondération — Moyenne générale (MG1)</h2>
          <button onClick={onClose} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted, marginTop: 2 }}><X size={17} strokeWidth={1.7} /></button>
        </div>
        {loading ? (
          <div className="shimmer" style={{ height: 16, width: 200, borderRadius: 999, marginTop: 14 }} />
        ) : (
          <>
            <p style={{ fontSize: 12, color: PAL.muted, marginTop: 8, marginBottom: 14, lineHeight: 1.5 }}>
              MG1 = (MPCC1 × ce coefficient + MPEFCFT1 × ce coefficient + MPEFCFP1 × ce coefficient) ÷ somme des coefficients — pas forcément 100%, comme dans l'ancien classeur.
            </p>
            {[
              { key: "cc_weight" as const, label: "MPCC1 (Contrôle continu)" },
              { key: "efcf_th_weight" as const, label: "MPEFCFT1 (Examen Théorique)" },
              { key: "efcf_pr_weight" as const, label: "MPEFCFP1 (Examen Pratique + Stage)" },
            ].map(f => (
              <div key={f.key} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                <label style={{ flex: 1, fontSize: 13.5, fontWeight: 600, color: PAL.ink }}>{f.label}</label>
                <input
                  type="number" min={0.5} step="0.5"
                  value={weights[f.key]}
                  onChange={e => setWeights(w => ({ ...w, [f.key]: parseFloat(e.target.value) || 0 }))}
                  style={{ ...fieldStyle, width: 80, textAlign: "right" }}
                />
              </div>
            ))}
            <div style={{ textAlign: "right", fontSize: 12, fontWeight: 600, color: PAL.muted, marginBottom: 4 }}>
              Somme : {total}
            </div>
          </>
        )}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 14 }}>
          <button onClick={onClose} className="btn-c btn-c-ghost">Annuler</button>
          <button onClick={save} disabled={saving || loading} className="btn-c btn-c-primary" style={{ opacity: saving || loading ? 0.6 : 1 }}>
            {saving ? "…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Jury de la décision finale (admission) d'une classe — distinct du jury
// d'un Examen (continuous_assessments.jury) : 4 rôles fixes ici (Président
// du jury d'examens / Membre professionnel / Membre formateur 1 / Membre
// formatrice 2), cf. GET/PUT /classes/{id}/jury. Même squelette que les
// autres modals de ce fichier.
function JuryModal({ classId, onClose }: { classId: string; onClose: () => void }) {
  const [members, setMembers] = useState<JuryMember[]>(Array.from({ length: 4 }, () => ({ name: "", role: "" })));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get(`/api/classes/${classId}/jury`)
      .then((d: { members: JuryMember[] }) => {
        const list = d?.members ?? [];
        setMembers(Array.from({ length: 4 }, (_, i) => list[i] ?? { name: "", role: "" }));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [classId]);

  function patch(i: number, fields: Partial<JuryMember>) {
    setMembers(list => list.map((m, j) => (j === i ? { ...m, ...fields } : m)));
  }

  async function save() {
    setSaving(true);
    try {
      await api.put(`/api/classes/${classId}/jury`, { members });
      toast.success("Jury enregistré.");
      onClose();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 14, padding: 26, width: 460, maxWidth: "94vw", maxHeight: "85vh", overflowY: "auto", boxShadow: "0 20px 50px rgba(0,0,0,.15)" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 6 }}>
          <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 20, fontWeight: 500, color: PAL.ink, margin: 0 }}>Jury de la décision</h2>
          <button onClick={onClose} style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted, marginTop: 2 }}><X size={17} strokeWidth={1.7} /></button>
        </div>
        {loading ? (
          <div className="shimmer" style={{ height: 16, width: 200, borderRadius: 999, marginTop: 14 }} />
        ) : (
          <>
            <p style={{ fontSize: 12, color: PAL.muted, marginTop: 8, marginBottom: 14, lineHeight: 1.5 }}>
              4 membres, affichés sur le PV de passage (ex. Président du jury d'examens, Membre professionnel, Membre formateur 1, Membre formatrice 2).
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {members.map((m, i) => (
                <div key={i} style={{ display: "flex", gap: 8 }}>
                  <input type="text" placeholder="Nom" value={m.name} onChange={e => patch(i, { name: e.target.value })} style={{ ...fieldStyle, flex: 1 }} />
                  <input type="text" placeholder="Rôle" value={m.role} onChange={e => patch(i, { role: e.target.value })} style={{ ...fieldStyle, flex: 1 }} />
                </div>
              ))}
            </div>
          </>
        )}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", marginTop: 14 }}>
          <button onClick={onClose} className="btn-c btn-c-ghost">Annuler</button>
          <button onClick={save} disabled={saving || loading} className="btn-c btn-c-primary" style={{ opacity: saving || loading ? 0.6 : 1 }}>
            {saving ? "…" : "Enregistrer"}
          </button>
        </div>
      </div>
    </div>
  );
}

function GradesPage() {
  const { roles } = useAuth();
  const isAdmin = roles.includes("admin");

  const [classes, setClasses] = useState<ClassItem[]>([]);
  const [classId, setClassId] = useState("");
  const [students, setStudents] = useState<StudentItem[]>([]);
  const [loadingClasses, setLoadingClasses] = useState(true);
  const [loadingStudents, setLoadingStudents] = useState(false);

  // Vue admin uniquement : moyenne générale + détail multi-modules.
  const [overallGrades, setOverallGrades] = useState<Record<string, OverallGrade | null>>({});
  const [expanded, setExpanded] = useState<string | null>(null);

  // Synthèse cohorte (MPCC1/MPEFCFT1/MPEFCFP1/MG1) + Stage + pondération MG1
  // — vue admin consolidée uniquement, un seul appel groupé par classe.
  const [mg1Summary, setMg1Summary] = useState<Record<string, ClassSummary>>({});
  const [showStageModal, setShowStageModal] = useState(false);
  const [showClassWeights, setShowClassWeights] = useState(false);

  // Décision du jury (admission) par élève + jury de la décision finale
  // — mêmes conditions d'affichage que mg1Summary (vue admin consolidée).
  const [decisions, setDecisions] = useState<Record<string, DecisionEntry>>({});
  const [showJuryModal, setShowJuryModal] = useState(false);
  const [editingDecision, setEditingDecision] = useState<string | null>(null);
  const [decisionDraft, setDecisionDraft] = useState<{ status: string; mention: string }>({ status: "", mention: "" });
  const [savingDecision, setSavingDecision] = useState(false);
  const [exportingPv, setExportingPv] = useState<"xlsx" | "docx" | null>(null);
  const [exportingCcGrid, setExportingCcGrid] = useState(false);
  const [exportingPratiqueGrid, setExportingPratiqueGrid] = useState(false);

  // Saisie par module — professeur (ses cours) et admin.
  const [courses, setCourses] = useState<CourseItem[]>([]);
  const [moduleId, setModuleId] = useState("");
  const [moduleGrades, setModuleGrades] = useState<Record<string, ModuleGrade | null>>({});
  const [assignments, setAssignments] = useState<QuickAssignment[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState("");
  const [assignmentGrades, setAssignmentGrades] = useState<Record<string, string>>({});
  const [savingGrades, setSavingGrades] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newForm, setNewForm] = useState({ title: "", category: "devoir" as QuickCategory, max_grade: "20" });
  const [creatingBusy, setCreatingBusy] = useState(false);
  const [showWeights, setShowWeights] = useState(false);

  useEffect(() => {
    api.get("/api/classes")
      .then((rows: ClassItem[]) => {
        setClasses(rows ?? []);
        if (rows?.length) setClassId(rows[0].id);
      })
      .catch(() => setClasses([]))
      .finally(() => setLoadingClasses(false));
    api.get("/api/courses").then((rows: CourseItem[]) => setCourses(rows ?? [])).catch(() => setCourses([]));
  }, []);

  const loadStudents = useCallback((cid: string) => {
    if (!cid) { setStudents([]); return () => {}; }
    let alive = true;
    setLoadingStudents(true);
    api.get(`/api/classes/${cid}/students`)
      .then((rows: StudentItem[]) => { if (alive) setStudents(rows ?? []); })
      .catch(() => { if (alive) setStudents([]); })
      .finally(() => { if (alive) setLoadingStudents(false); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    setExpanded(null);
    setModuleId("");
    return loadStudents(classId);
  }, [classId, loadStudents]);

  // Vue admin (pas de module sélectionné) : moyenne générale consolidée.
  useEffect(() => {
    if (!isAdmin || moduleId || students.length === 0) { setOverallGrades({}); return; }
    let alive = true;
    Promise.all(
      students.map(async s => {
        try {
          const g = await api.get(`/api/students/${s.id}/overall-grade?class_id=${classId}`);
          return [s.id, g as OverallGrade] as const;
        } catch {
          return [s.id, null] as const;
        }
      })
    ).then(entries => { if (alive) setOverallGrades(Object.fromEntries(entries)); });
    return () => { alive = false; };
  }, [isAdmin, moduleId, students, classId]);

  // Synthèse cohorte (MG1) — un seul appel groupé par classe, pas par élève
  // (contrairement à overallGrades ci-dessus — le calcul EFCF est plus
  // coûteux à résoudre, cf. backend compute_class_efcf_averages).
  const loadMg1Summary = useCallback((cid: string) => {
    if (!cid) { setMg1Summary({}); return; }
    api.get(`/api/classes/${cid}/mg1-summary`)
      .then((d: Record<string, ClassSummary>) => setMg1Summary(d ?? {}))
      .catch(() => setMg1Summary({}));
  }, []);

  useEffect(() => {
    if (!isAdmin || moduleId || !classId) { setMg1Summary({}); return; }
    loadMg1Summary(classId);
  }, [isAdmin, moduleId, classId, loadMg1Summary]);

  // Décision du jury par élève — même déclenchement que mg1Summary ci-dessus.
  const loadDecisions = useCallback((cid: string) => {
    if (!cid) { setDecisions({}); return; }
    api.get(`/api/classes/${cid}/decisions`)
      .then((d: Record<string, DecisionEntry>) => setDecisions(d ?? {}))
      .catch(() => setDecisions({}));
  }, []);

  useEffect(() => {
    if (!isAdmin || moduleId || !classId) { setDecisions({}); return; }
    loadDecisions(classId);
  }, [isAdmin, moduleId, classId, loadDecisions]);

  // Modules assignés à la classe affichée, parmi les cours accessibles
  // (GET /courses filtre déjà par rôle : professeur -> ses cours, admin -> tous).
  const classCourses = courses.filter(c => c.assigned_classes.some(ac => ac.id === classId));

  const loadQuickAssignments = useCallback((mid: string) => {
    if (!mid) { setAssignments([]); return; }
    api.get(`/api/assignments/quick?course_id=${mid}`)
      .then((rows: QuickAssignment[]) => setAssignments(rows ?? []))
      .catch(() => setAssignments([]));
  }, []);

  const loadModuleGrades = useCallback((mid: string, roster: StudentItem[]) => {
    if (!mid || roster.length === 0) { setModuleGrades({}); return; }
    Promise.all(
      roster.map(async s => {
        try {
          const g = await api.get(`/api/courses/${mid}/students/${s.id}/grade`);
          return [s.id, g as ModuleGrade] as const;
        } catch {
          return [s.id, null] as const;
        }
      })
    ).then(entries => setModuleGrades(Object.fromEntries(entries)));
  }, []);

  useEffect(() => {
    setSelectedAssignmentId("");
    setCreating(false);
    if (moduleId) {
      loadQuickAssignments(moduleId);
      loadModuleGrades(moduleId, students);
    } else {
      setAssignments([]);
      setModuleGrades({});
    }
  }, [moduleId, students, loadQuickAssignments, loadModuleGrades]);

  useEffect(() => {
    const a = assignments.find(x => x.id === selectedAssignmentId);
    if (!a) { setAssignmentGrades({}); return; }
    const initial: Record<string, string> = {};
    students.forEach(s => { initial[s.id] = a.grades[s.id] != null ? String(a.grades[s.id]) : ""; });
    setAssignmentGrades(initial);
  }, [selectedAssignmentId, assignments, students]);

  async function createAssignment() {
    if (!newForm.title.trim()) { toast.error("Le titre est obligatoire."); return; }
    setCreatingBusy(true);
    try {
      const created = await api.post("/api/assignments", {
        title: newForm.title.trim(),
        course_id: moduleId,
        max_grade: parseFloat(newForm.max_grade) || 20,
        is_quick_grade: true,
        quick_grade_category: newForm.category,
      });
      toast.success("Évaluation créée.");
      setCreating(false);
      setNewForm({ title: "", category: "devoir", max_grade: "20" });
      loadQuickAssignments(moduleId);
      setSelectedAssignmentId(created.id);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la création.");
    } finally {
      setCreatingBusy(false);
    }
  }

  async function removeAssignment(a: QuickAssignment) {
    if (!window.confirm(`Supprimer « ${a.title} » et toutes ses notes ?`)) return;
    try {
      await api.delete(`/api/assignments/${a.id}`);
      toast.success("Évaluation supprimée.");
      if (selectedAssignmentId === a.id) setSelectedAssignmentId("");
      loadQuickAssignments(moduleId);
      loadModuleGrades(moduleId, students);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la suppression.");
    }
  }

  async function saveAssignmentGrades() {
    if (!selectedAssignmentId) return;
    const grades_: Record<string, number | null> = {};
    for (const s of students) {
      const raw = (assignmentGrades[s.id] ?? "").trim();
      grades_[s.id] = raw === "" ? null : parseFloat(raw);
    }
    setSavingGrades(true);
    try {
      await api.put(`/api/assignments/${selectedAssignmentId}/quick-grades`, { grades: grades_ });
      toast.success("Notes enregistrées.");
      loadQuickAssignments(moduleId);
      loadModuleGrades(moduleId, students);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'enregistrement.");
    } finally {
      setSavingGrades(false);
    }
  }

  function openDecisionEditor(studentId: string) {
    const d = decisions[studentId];
    setDecisionDraft({
      status: d?.status && d.status !== "a_examiner" ? d.status : "",
      mention: d?.mention ?? "",
    });
    setEditingDecision(studentId);
  }

  async function saveDecision(studentId: string) {
    if (!decisionDraft.status) { toast.error("Choisissez une décision."); return; }
    setSavingDecision(true);
    try {
      await api.put(`/api/classes/${classId}/decisions`, {
        grades: { [studentId]: { status: decisionDraft.status, mention: decisionDraft.mention.trim() || null } },
      });
      toast.success("Décision enregistrée.");
      setEditingDecision(null);
      loadDecisions(classId);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'enregistrement.");
    } finally {
      setSavingDecision(false);
    }
  }

  async function exportPv(kind: "xlsx" | "docx") {
    const cls = classes.find(c => c.id === classId);
    setExportingPv(kind);
    try {
      await api.download(`/api/classes/${classId}/pv.${kind}`, `PV_${cls?.name ?? classId}.${kind}`);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'export.");
    } finally {
      setExportingPv(null);
    }
  }

  async function exportCcGrid() {
    const cls = classes.find(c => c.id === classId);
    setExportingCcGrid(true);
    try {
      await api.download(`/api/classes/${classId}/cc-grid.xlsx`, `CC_${cls?.name ?? classId}.xlsx`);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'export.");
    } finally {
      setExportingCcGrid(false);
    }
  }

  async function exportPratiqueGrid() {
    const cls = classes.find(c => c.id === classId);
    setExportingPratiqueGrid(true);
    try {
      await api.download(`/api/classes/${classId}/pratique-grid.xlsx`, `Pratique_${cls?.name ?? classId}.xlsx`);
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'export.");
    } finally {
      setExportingPratiqueGrid(false);
    }
  }

  const ranked = [...students].sort((a, b) => {
    const ga = moduleId ? moduleGrades[a.id]?.grade : overallGrades[a.id]?.average;
    const gb = moduleId ? moduleGrades[b.id]?.grade : overallGrades[b.id]?.average;
    if (ga == null && gb == null) return (a.full_name || a.email).localeCompare(b.full_name || b.email);
    if (ga == null) return 1;
    if (gb == null) return -1;
    return (gb as number) - (ga as number);
  });

  const showCrossModuleView = !moduleId && isAdmin;
  const showRoster = moduleId ? true : (isAdmin ? true : false);

  return (
    <div style={{ fontFamily: sans }}>
      <PageHead
        eyebrow="Scolarité & pédagogie"
        title="Notes"
        sub="Moyenne par matière et générale, calculées à partir du Contrôle continu et des Examens."
      />

      <SectionLabel
        action={
          <select value={classId} onChange={e => setClassId(e.target.value)} style={{ ...fieldStyle, minWidth: 220 }}>
            {classes.length === 0 && <option value="">Aucune classe</option>}
            {classes.map(c => (
              <option key={c.id} value={c.id}>{c.name}{c.formation_code ? ` · ${c.formation_code}` : ""}</option>
            ))}
          </select>
        }
      >
        Classe
      </SectionLabel>

      {showCrossModuleView && classId && (
        <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
          <button type="button" onClick={() => setShowStageModal(true)} className="btn-c btn-c-ghost btn-c-sm">
            <SlidersHorizontal size={13} strokeWidth={1.8} />Stage
          </button>
          <button type="button" onClick={() => setShowClassWeights(true)} className="btn-c btn-c-ghost btn-c-sm" title="Pondération de la moyenne générale (MG1)">
            <SlidersHorizontal size={13} strokeWidth={1.8} />Pondération MG1
          </button>
          <button type="button" onClick={() => setShowJuryModal(true)} className="btn-c btn-c-ghost btn-c-sm" title="Jury de la décision finale">
            <Gavel size={13} strokeWidth={1.8} />Jury (décision)
          </button>
          <span style={{ width: 1, background: PAL.line, margin: "2px 2px" }} />
          <button type="button" onClick={() => exportPv("xlsx")} disabled={exportingPv !== null || exportingCcGrid || exportingPratiqueGrid} className="btn-c btn-c-ghost btn-c-sm" style={{ opacity: exportingPv !== null || exportingCcGrid || exportingPratiqueGrid ? 0.6 : 1 }}>
            <FileSpreadsheet size={13} strokeWidth={1.8} />{exportingPv === "xlsx" ? "Export…" : "Exporter PV (Excel)"}
          </button>
          <button type="button" onClick={() => exportPv("docx")} disabled={exportingPv !== null || exportingCcGrid || exportingPratiqueGrid} className="btn-c btn-c-ghost btn-c-sm" style={{ opacity: exportingPv !== null || exportingCcGrid || exportingPratiqueGrid ? 0.6 : 1 }}>
            <FileText size={13} strokeWidth={1.8} />{exportingPv === "docx" ? "Export…" : "Exporter PV (Word)"}
          </button>
          <button type="button" onClick={exportCcGrid} disabled={exportingPv !== null || exportingCcGrid || exportingPratiqueGrid} className="btn-c btn-c-ghost btn-c-sm" style={{ opacity: exportingPv !== null || exportingCcGrid || exportingPratiqueGrid ? 0.6 : 1 }}>
            <FileSpreadsheet size={13} strokeWidth={1.8} />{exportingCcGrid ? "Export…" : "Exporter Contrôle Continu (Excel)"}
          </button>
          <button type="button" onClick={exportPratiqueGrid} disabled={exportingPv !== null || exportingCcGrid || exportingPratiqueGrid} className="btn-c btn-c-ghost btn-c-sm" style={{ opacity: exportingPv !== null || exportingCcGrid || exportingPratiqueGrid ? 0.6 : 1 }}>
            <FileSpreadsheet size={13} strokeWidth={1.8} />{exportingPratiqueGrid ? "Export…" : "Exporter Examens Pratiques (Excel)"}
          </button>
        </div>
      )}

      {classCourses.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16, flexWrap: "wrap" }}>
          <span style={{ fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".08em", textTransform: "uppercase" as const }}>Module</span>
          <select value={moduleId} onChange={e => setModuleId(e.target.value)} style={{ ...fieldStyle, minWidth: 220 }}>
            <option value="">{isAdmin ? "— Vue consolidée (tous modules) —" : "— Choisir un module —"}</option>
            {classCourses.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
        </div>
      )}

      {moduleId && (
        <div className="dash-card" style={{ padding: 16, marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: creating || assignments.length ? 12 : 0 }}>
            <span style={{ fontFamily: sans, fontSize: 12.5, fontWeight: 700, color: PAL.ink }}>Évaluations du module</span>
            <div style={{ display: "flex", gap: 8 }}>
              <button type="button" onClick={() => setShowWeights(true)} className="btn-c btn-c-ghost btn-c-sm" title="Répartition Examens / Contrôle continu / Quiz">
                <SlidersHorizontal size={13} strokeWidth={1.8} />Pondération
              </button>
              {!creating && (
                <button type="button" onClick={() => setCreating(true)} className="btn-c btn-c-soft btn-c-sm">
                  <Plus size={13} strokeWidth={1.8} />Nouvelle évaluation
                </button>
              )}
            </div>
          </div>

          {creating && (
            <div style={{ display: "flex", alignItems: "flex-end", gap: 10, flexWrap: "wrap", marginBottom: 14, padding: 12, background: "var(--pal-pale)", borderRadius: 10 }}>
              <div style={{ flex: "2 1 180px" }}>
                <label style={{ fontFamily: sans, fontSize: 10.5, fontWeight: 600, color: PAL.muted, letterSpacing: ".06em", textTransform: "uppercase" as const }}>Titre</label>
                <input type="text" placeholder="Ex : Devoir 1" value={newForm.title} onChange={e => setNewForm(f => ({ ...f, title: e.target.value }))} style={{ ...fieldStyle, width: "100%", marginTop: 4 }} />
              </div>
              <div style={{ flex: "1 1 140px" }}>
                <label style={{ fontFamily: sans, fontSize: 10.5, fontWeight: 600, color: PAL.muted, letterSpacing: ".06em", textTransform: "uppercase" as const }}>Type</label>
                <select value={newForm.category} onChange={e => setNewForm(f => ({ ...f, category: e.target.value as QuickCategory }))} style={{ ...fieldStyle, width: "100%", marginTop: 4 }}>
                  <option value="devoir">Contrôle continu</option>
                  <option value="exam">Examen</option>
                </select>
              </div>
              <div style={{ flex: "0 1 90px" }}>
                <label style={{ fontFamily: sans, fontSize: 10.5, fontWeight: 600, color: PAL.muted, letterSpacing: ".06em", textTransform: "uppercase" as const }}>Barème</label>
                <input type="number" min={1} value={newForm.max_grade} onChange={e => setNewForm(f => ({ ...f, max_grade: e.target.value }))} style={{ ...fieldStyle, width: "100%", marginTop: 4 }} />
              </div>
              <button type="button" onClick={createAssignment} disabled={creatingBusy} className="btn-c btn-c-primary btn-c-sm" style={{ opacity: creatingBusy ? 0.6 : 1 }}>
                {creatingBusy ? "…" : "Créer"}
              </button>
              <button type="button" onClick={() => setCreating(false)} className="btn-c btn-c-ghost btn-c-sm"><X size={13} strokeWidth={1.8} /></button>
            </div>
          )}

          {assignments.length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {assignments.map(a => (
                <div key={a.id} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <button
                    type="button" onClick={() => setSelectedAssignmentId(selectedAssignmentId === a.id ? "" : a.id)}
                    style={{
                      padding: "6px 12px", borderRadius: 999, cursor: "pointer",
                      border: `1px solid ${selectedAssignmentId === a.id ? "var(--pal-primary)" : PAL.line}`,
                      background: selectedAssignmentId === a.id ? "var(--pal-pale)" : "transparent",
                      fontFamily: sans, fontSize: 12.5, fontWeight: 600,
                      color: selectedAssignmentId === a.id ? "var(--pal-primary-deep)" : PAL.ink,
                    }}
                  >
                    {a.title} <span style={{ color: PAL.muted, fontWeight: 500 }}>· {CATEGORY_LABELS[a.quick_grade_category]}</span>
                  </button>
                  <button type="button" onClick={() => removeAssignment(a)} title="Supprimer" style={{ background: "none", border: 0, cursor: "pointer", color: PAL.muted, padding: 4 }}>
                    <Trash2 size={13} strokeWidth={1.8} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {selectedAssignmentId && (
            <div style={{ marginTop: 14, paddingTop: 14, borderTop: `1px dashed ${PAL.line}` }}>
              <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
                <button type="button" onClick={saveAssignmentGrades} disabled={savingGrades} className="btn-c btn-c-primary btn-c-sm" style={{ opacity: savingGrades ? 0.6 : 1 }}>
                  <Save size={13} strokeWidth={1.8} />{savingGrades ? "Enregistrement…" : "Enregistrer les notes"}
                </button>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {students.map(s => (
                  <div key={s.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, padding: "6px 4px" }}>
                    <span style={{ fontSize: 13, color: PAL.ink }}>{s.full_name || s.email}</span>
                    <input
                      type="number" min={0} max={assignments.find(a => a.id === selectedAssignmentId)?.max_grade ?? 20} step="0.25"
                      value={assignmentGrades[s.id] ?? ""}
                      onChange={e => setAssignmentGrades(m => ({ ...m, [s.id]: e.target.value }))}
                      style={{ ...fieldStyle, width: 80, textAlign: "right", padding: "6px 8px" }}
                      placeholder="—"
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {loadingClasses ? (
        <div className="dash-card" style={{ padding: 26 }}><div className="shimmer" style={{ height: 18, width: 200, borderRadius: 999 }} /></div>
      ) : classes.length === 0 ? (
        <div className="dash-card"><EmptyHint icon={<Award size={28} strokeWidth={1.7} />} text="Aucune classe disponible." /></div>
      ) : loadingStudents ? (
        <div className="dash-card" style={{ padding: 26 }}><div className="shimmer" style={{ height: 18, width: 260, borderRadius: 999 }} /></div>
      ) : students.length === 0 ? (
        <div className="dash-card"><EmptyHint icon={<Award size={28} strokeWidth={1.7} />} text="Aucun élève dans cette classe." /></div>
      ) : !showRoster ? (
        <div className="dash-card"><EmptyHint icon={<Award size={28} strokeWidth={1.7} />} text="Sélectionnez un de vos modules ci-dessus pour consulter ou saisir les notes." /></div>
      ) : (
        <div className="dash-card overflow-hidden" style={{ padding: 0 }}>
          <div style={{ overflowX: "auto" }}>
            <table style={{ borderCollapse: "collapse", width: "100%", minWidth: 560 }}>
              <thead>
                <tr>
                  {["#", "Élève", moduleId ? "Note du module / 20" : (showCrossModuleView ? "MPCC1 / 20" : "Moyenne générale / 20"), ...(showCrossModuleView ? [""] : [])].map((h, i) => (
                    <th key={i} style={{ padding: "11px 14px", borderBottom: `1px solid ${PAL.line}`, textAlign: i === 2 ? "right" : "left", fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".08em", textTransform: "uppercase" as const, whiteSpace: "nowrap" }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ranked.map((s, i) => {
                  const value = moduleId ? moduleGrades[s.id]?.grade ?? null : overallGrades[s.id]?.average ?? null;
                  const isOpen = expanded === s.id;
                  const canExpand = showCrossModuleView;
                  return (
                    <Fragment key={s.id}>
                      <tr style={canExpand ? { cursor: "pointer" } : undefined} onClick={canExpand ? () => setExpanded(isOpen ? null : s.id) : undefined}>
                        <td style={{ padding: "10px 14px", borderBottom: `1px solid ${PAL.line}`, fontFamily: mono, fontSize: 12, color: PAL.muted }}>{i + 1}</td>
                        <td style={{ padding: "10px 14px", borderBottom: `1px solid ${PAL.line}`, fontSize: 13.5, color: PAL.ink, fontWeight: 600 }}>{s.full_name || s.email}</td>
                        <td style={{ padding: "10px 14px", borderBottom: `1px solid ${PAL.line}`, textAlign: "right", fontFamily: mono, fontWeight: 700, fontSize: 14, color: gradeColor(value) }}>
                          {value != null ? value.toFixed(2) : "—"}
                        </td>
                        {showCrossModuleView && (
                          <td style={{ padding: "10px 14px", borderBottom: `1px solid ${PAL.line}`, textAlign: "right", color: PAL.muted }}>
                            {isOpen ? <ChevronDown size={16} strokeWidth={1.8} /> : <ChevronRight size={16} strokeWidth={1.8} />}
                          </td>
                        )}
                      </tr>
                      {canExpand && isOpen && (
                        <tr key={`${s.id}-detail`}>
                          <td colSpan={4} style={{ padding: 0, borderBottom: `1px solid ${PAL.line}`, background: "var(--pal-pale)" }}>
                            {mg1Summary[s.id] && (
                              <div style={{ display: "flex", flexWrap: "wrap", gap: 20, padding: "12px 20px", borderBottom: `1px dashed ${PAL.line}` }}>
                                {([
                                  ["MPCC1", mg1Summary[s.id].mpcc1],
                                  ["MPEFCFT1", mg1Summary[s.id].mpefcft1],
                                  ["MPEFCFP1", mg1Summary[s.id].mpefcfp1],
                                  ["MG1", mg1Summary[s.id].mg1],
                                ] as const).map(([label, v]) => (
                                  <div key={label}>
                                    <div style={{ fontFamily: sans, fontSize: 10, fontWeight: 600, color: PAL.muted, letterSpacing: ".06em", textTransform: "uppercase" as const }}>{label}</div>
                                    <div style={{ fontFamily: mono, fontSize: 15, fontWeight: 700, color: gradeColor(v), marginTop: 2 }}>{v != null ? v.toFixed(2) : "—"}</div>
                                  </div>
                                ))}
                              </div>
                            )}
                            {decisions[s.id] && (
                              <div style={{ padding: "12px 20px", borderBottom: `1px dashed ${PAL.line}` }} onClick={e => e.stopPropagation()}>
                                <div style={{ fontFamily: sans, fontSize: 10, fontWeight: 600, color: PAL.muted, letterSpacing: ".06em", textTransform: "uppercase" as const, marginBottom: 6 }}>Décision du jury</div>
                                {editingDecision === s.id ? (
                                  <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                                    <select
                                      value={decisionDraft.status}
                                      onChange={e => setDecisionDraft(d => ({ ...d, status: e.target.value }))}
                                      style={{ ...fieldStyle, padding: "6px 8px", minWidth: 220 }}
                                    >
                                      <option value="">— Choisir —</option>
                                      {DECISION_STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                                    </select>
                                    <input
                                      type="text" placeholder="Mention (optionnel)"
                                      value={decisionDraft.mention}
                                      onChange={e => setDecisionDraft(d => ({ ...d, mention: e.target.value }))}
                                      style={{ ...fieldStyle, padding: "6px 8px", width: 160 }}
                                    />
                                    <button type="button" onClick={() => saveDecision(s.id)} disabled={savingDecision} className="btn-c btn-c-primary btn-c-sm" style={{ opacity: savingDecision ? 0.6 : 1 }}>
                                      <Save size={12} strokeWidth={1.8} />{savingDecision ? "…" : "Enregistrer"}
                                    </button>
                                    <button type="button" onClick={() => setEditingDecision(null)} className="btn-c btn-c-ghost btn-c-sm"><X size={12} strokeWidth={1.8} /></button>
                                  </div>
                                ) : (
                                  <div
                                    style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }}
                                    onClick={() => openDecisionEditor(s.id)}
                                    title="Modifier la décision"
                                  >
                                    {decisions[s.id].status ? (
                                      <span className={`chip-c ${decisionChipClass(decisions[s.id].status)}`}>
                                        {DECISION_LABELS[decisions[s.id].status as string] ?? decisions[s.id].status}
                                      </span>
                                    ) : (
                                      <span style={{ fontSize: 12.5, color: PAL.muted, fontStyle: "italic" }}>Aucune décision pour l'instant</span>
                                    )}
                                    {decisions[s.id].mention && (
                                      <span style={{ fontSize: 12.5, color: PAL.muted }}>{decisions[s.id].mention}</span>
                                    )}
                                    {decisions[s.id].status && !decisions[s.id].is_override && (
                                      <span style={{ fontSize: 10, fontWeight: 600, color: PAL.muted, fontStyle: "italic" }}>proposition</span>
                                    )}
                                    <Pencil size={13} strokeWidth={1.8} color={PAL.muted} />
                                  </div>
                                )}
                              </div>
                            )}
                            {!overallGrades[s.id]?.courses?.length ? (
                              <div style={{ padding: "12px 20px", fontSize: 12.5, color: PAL.muted, fontStyle: "italic" }}>Aucune note disponible pour cet élève.</div>
                            ) : (
                              <table style={{ borderCollapse: "collapse", width: "100%" }}>
                                <thead>
                                  <tr>
                                    {["Matière", "Coefficient", "Note / 20"].map((h, j) => (
                                      <th key={j} style={{ padding: "8px 20px", textAlign: j === 2 ? "right" : "left", fontFamily: sans, fontSize: 10.5, fontWeight: 600, color: PAL.muted, letterSpacing: ".06em", textTransform: "uppercase" as const }}>{h}</th>
                                    ))}
                                  </tr>
                                </thead>
                                <tbody>
                                  {overallGrades[s.id]!.courses.map(c => (
                                    <tr key={c.course_id}>
                                      <td style={{ padding: "6px 20px", fontSize: 13, color: PAL.ink }}>{c.title || "—"}</td>
                                      <td style={{ padding: "6px 20px", fontSize: 12.5, color: PAL.muted, fontFamily: mono }}>{c.coefficient}</td>
                                      <td style={{ padding: "6px 20px", textAlign: "right", fontFamily: mono, fontWeight: 600, fontSize: 13, color: gradeColor(c.grade) }}>
                                        {c.grade != null ? c.grade.toFixed(2) : "—"}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            )}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {showWeights && moduleId && (
        <WeightsModal
          courseId={moduleId}
          courseTitle={classCourses.find(c => c.id === moduleId)?.title ?? ""}
          onClose={() => { setShowWeights(false); loadModuleGrades(moduleId, students); }}
        />
      )}

      {showStageModal && classId && (
        <StageModal classId={classId} students={students} onClose={() => { setShowStageModal(false); loadMg1Summary(classId); }} />
      )}
      {showClassWeights && classId && (
        <ClassWeightsModal classId={classId} onClose={() => { setShowClassWeights(false); loadMg1Summary(classId); }} />
      )}
      {showJuryModal && classId && (
        <JuryModal classId={classId} onClose={() => setShowJuryModal(false)} />
      )}
    </div>
  );
}
