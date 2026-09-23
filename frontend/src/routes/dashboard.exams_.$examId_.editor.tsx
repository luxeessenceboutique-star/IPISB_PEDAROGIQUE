import { createFileRoute, redirect, useNavigate, useParams, Link } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useI18n } from "@/lib/i18n";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  ArrowLeft, Plus, Trash2, Copy, Image as ImageIcon, X, Loader2, Check,
  AlertTriangle, Eye, ChevronUp, ChevronDown, Lock, Send,
} from "lucide-react";
import { QuestionView } from "@/components/exams/QuestionView";

export const Route = createFileRoute("/dashboard/exams_/$examId_/editor")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: ExamEditorPage,
});

type QuestionType = "multiple_choice" | "true_false";
type Difficulty = "easy" | "medium" | "hard";

type Question = {
  id: string;
  question: string;
  options: string[];
  correct_index: number;
  order_num: number;
  type: QuestionType;
  difficulty: Difficulty;
  points: number;
  image_path?: string | null;
  image_url?: string | null;
  image_caption?: string | null;
};

type Exam = {
  id: string;
  course_id: string;
  course_title?: string;
  title: string;
  description: string | null;
  duration_minutes: number;
  is_published: boolean;
  is_editable: boolean;
  generation_config: { default_points?: number } | null;
};

type SaveState = "idle" | "saving" | "saved" | "error";

function blankQuestion(defaultPoints: number): Omit<Question, "id" | "order_num"> {
  return {
    question: "", options: ["", "", "", ""], correct_index: 0,
    type: "multiple_choice", difficulty: "medium", points: defaultPoints,
    image_path: null, image_url: null, image_caption: null,
  };
}

function ExamEditorPage() {
  const { lang } = useI18n();
  const { examId } = useParams({ from: "/dashboard/exams_/$examId_/editor" });
  const navigate = useNavigate();
  const fr = lang === "fr";
  const ar = lang === "ar";
  const tt = (f: string, e: string, a: string) => (fr ? f : ar ? a : e);

  const [exam, setExam] = useState<Exam | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [savingIds, setSavingIds] = useState<Set<string>>(new Set());
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [publishing, setPublishing] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewIndex, setPreviewIndex] = useState(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const uploadTargetId = useRef<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [examData, questionsData] = await Promise.all([
        api.get(`/api/exams/${examId}`) as Promise<Exam>,
        api.get(`/api/exams/${examId}/questions`) as Promise<Question[]>,
      ]);
      setExam(examData);
      setQuestions(questionsData.sort((a, b) => a.order_num - b.order_num));
      setActiveId(prev => prev ?? (questionsData[0]?.id ?? null));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : tt("Impossible de charger l'examen.", "Could not load the exam.", "تعذر تحميل الامتحان."));
      navigate({ to: "/dashboard/exams" });
    } finally {
      setLoading(false);
    }
  }, [examId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  const locked = exam ? !exam.is_editable : false;
  const active = questions.find(q => q.id === activeId) ?? null;

  function markSaving(id: string, on: boolean) {
    setSavingIds(prev => {
      const next = new Set(prev);
      on ? next.add(id) : next.delete(id);
      return next;
    });
  }

  async function patchExam(fields: Partial<Pick<Exam, "title" | "duration_minutes">>) {
    if (!exam || locked) return;
    setSaveState("saving");
    try {
      await api.patch(`/api/exams/${examId}`, fields);
      setSaveState("saved");
      setTimeout(() => setSaveState(s => (s === "saved" ? "idle" : s)), 2500);
    } catch (e) {
      setSaveState("error");
      toast.error(e instanceof ApiError ? e.message : tt("Échec de l'enregistrement.", "Save failed.", "فشل الحفظ."));
    }
  }

  async function patchQuestion(id: string, fields: Partial<Question>) {
    if (locked) return;
    markSaving(id, true);
    setSaveState("saving");
    try {
      const updated: Question = await api.patch(`/api/exams/${examId}/questions/${id}`, fields);
      setQuestions(qs => qs.map(q => (q.id === id ? { ...q, ...updated } : q)));
      setSaveState("saved");
      setTimeout(() => setSaveState(s => (s === "saved" ? "idle" : s)), 2500);
    } catch (e) {
      setSaveState("error");
      toast.error(e instanceof ApiError ? e.message : tt("Échec de l'enregistrement de la question.", "Failed to save the question.", "فشل حفظ السؤال."));
    } finally {
      markSaving(id, false);
    }
  }

  function updateLocal(id: string, fields: Partial<Question>) {
    setQuestions(qs => qs.map(q => (q.id === id ? { ...q, ...fields } : q)));
  }

  async function addQuestion(template?: Question) {
    if (!exam || locked) return;
    const base = template
      ? { question: template.question, options: [...template.options], correct_index: template.correct_index, type: template.type, difficulty: template.difficulty, points: template.points }
      : blankQuestion(exam.generation_config?.default_points ?? 1);
    try {
      const created: Question = await api.post(`/api/exams/${examId}/questions`, { ...base, order_num: questions.length });
      setQuestions(qs => [...qs, created]);
      setActiveId(created.id);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : tt("Échec de l'ajout de la question.", "Failed to add the question.", "فشل إضافة السؤال."));
    }
  }

  async function deleteQuestion(id: string) {
    if (locked) return;
    try {
      await api.delete(`/api/exams/${examId}/questions/${id}`);
      setQuestions(qs => {
        const next = qs.filter(q => q.id !== id);
        if (activeId === id) setActiveId(next[0]?.id ?? null);
        return next;
      });
      toast.success(tt("Question supprimée.", "Question deleted.", "تم حذف السؤال."));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : tt("Échec de la suppression.", "Delete failed.", "فشل الحذف."));
    } finally {
      setConfirmDeleteId(null);
    }
  }

  async function moveQuestion(id: string, dir: -1 | 1) {
    if (locked) return;
    const idx = questions.findIndex(q => q.id === id);
    const newIdx = idx + dir;
    if (idx < 0 || newIdx < 0 || newIdx >= questions.length) return;
    const reordered = [...questions];
    [reordered[idx], reordered[newIdx]] = [reordered[newIdx], reordered[idx]];
    setQuestions(reordered);
    try {
      await api.put(`/api/exams/${examId}/questions/reorder`, { question_ids: reordered.map(q => q.id) });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : tt("Échec de la réorganisation.", "Reorder failed.", "فشل إعادة الترتيب."));
      load();
    }
  }

  function openImagePicker(questionId: string) {
    uploadTargetId.current = questionId;
    fileInputRef.current?.click();
  }

  async function handleFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    const qid = uploadTargetId.current;
    e.target.value = "";
    if (!file || !qid) return;
    markSaving(qid, true);
    try {
      const { data: { session } } = await supabase.auth.getSession();
      const form = new FormData();
      form.append("file", file);
      const base = import.meta.env.VITE_API_URL ?? "http://localhost:9000";
      const res = await fetch(`${base}/api/exams/${examId}/questions/${qid}/image`, {
        method: "POST",
        headers: session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {},
        body: form,
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      updateLocal(qid, { image_path: data.image_path, image_url: data.image_url, image_caption: data.image_caption });
      toast.success(tt("Image ajoutée.", "Image added.", "تمت إضافة الصورة."));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : tt("Échec de l'envoi de l'image.", "Image upload failed.", "فشل رفع الصورة."));
    } finally {
      markSaving(qid, false);
    }
  }

  async function removeImage(qid: string) {
    markSaving(qid, true);
    try {
      await api.delete(`/api/exams/${examId}/questions/${qid}/image`);
      updateLocal(qid, { image_path: null, image_url: null, image_caption: null });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : tt("Échec de la suppression de l'image.", "Failed to remove the image.", "فشل حذف الصورة."));
    } finally {
      markSaving(qid, false);
    }
  }

  async function togglePublish() {
    if (!exam) return;
    if (!exam.is_published && questions.length === 0) {
      toast.error(tt("Ajoutez au moins une question avant de publier.", "Add at least one question before publishing.", "أضف سؤالاً واحدًا على الأقل قبل النشر."));
      return;
    }
    setPublishing(true);
    try {
      const res: { is_published: boolean } = await api.put(`/api/exams/${examId}/publish`);
      setExam(ex => (ex ? { ...ex, is_published: res.is_published } : ex));
      toast.success(res.is_published
        ? tt("Examen publié — les étudiants inscrits peuvent maintenant le passer.", "Exam published — enrolled students can now take it.", "تم نشر الامتحان — يمكن للطلاب المسجلين الآن إجراؤه.")
        : tt("Examen dépublié.", "Exam unpublished.", "تم إلغاء نشر الامتحان."));
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : tt("Échec de la publication.", "Publish failed.", "فشل النشر."));
    } finally {
      setPublishing(false);
    }
  }

  function saveStateLabel() {
    if (saveState === "saving") return <><Loader2 className="h-3.5 w-3.5 animate-spin" />{tt("Enregistrement…", "Saving…", "جارٍ الحفظ…")}</>;
    if (saveState === "saved") return <><Check className="h-3.5 w-3.5 text-green-600" />{tt("Enregistré", "Saved", "تم الحفظ")}</>;
    if (saveState === "error") return <><AlertTriangle className="h-3.5 w-3.5 text-destructive" />{tt("Échec — réessayez", "Failed — retry", "فشل — أعد المحاولة")}</>;
    return null;
  }

  if (loading || !exam) {
    return <div className="flex h-64 items-center justify-center text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin" /></div>;
  }

  return (
    <div className="-m-1">
      <input ref={fileInputRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={handleFileChosen} />

      {/* Toolbar */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border bg-card px-4 py-3 shadow-card">
        <div className="flex items-center gap-3">
          <Link to="/dashboard/exams" className="btn-c btn-c-ghost btn-c-sm"><ArrowLeft size={14} strokeWidth={1.7} />{tt("Examens", "Exams", "الامتحانات")}</Link>
          <div className="hidden items-center gap-1.5 text-xs text-muted-foreground sm:flex">{saveStateLabel()}</div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`chip-c ${exam.is_published ? "chip-c-green" : ""}`}>
            {exam.is_published ? tt("Publié", "Published", "منشور") : tt("Brouillon", "Draft", "مسودة")}
          </span>
          <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => { setPreviewIndex(0); setShowPreview(true); }}>
            <Eye size={14} strokeWidth={1.7} />{tt("Aperçu", "Preview", "معاينة")}
          </button>
          <button type="button" className="btn-c btn-c-primary btn-c-sm" disabled={publishing} onClick={togglePublish}>
            {publishing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send size={14} strokeWidth={1.7} />}
            {exam.is_published ? tt("Dépublier", "Unpublish", "إلغاء النشر") : tt("Publier", "Publish", "نشر")}
          </button>
        </div>
      </div>

      {locked && (
        <div className="mb-4 flex items-center gap-2 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Lock className="h-4 w-4 shrink-0" />
          {tt(
            "Cet examen a déjà des réponses d'étudiants — lecture seule. Créez un nouvel examen pour une nouvelle version.",
            "This exam already has student responses — read only. Create a new exam for a new version.",
            "هذا الامتحان لديه بالفعل إجابات طلابية — للقراءة فقط. أنشئ امتحانًا جديدًا لإصدار جديد.",
          )}
        </div>
      )}

      {/* Exam-level fields */}
      <div className="mb-4 dash-card grid grid-cols-1 gap-3 p-4 sm:grid-cols-[1fr_160px]">
        <div>
          <label className="text-xs font-medium text-muted-foreground">{tt("Titre de l'examen", "Exam title", "عنوان الامتحان")}</label>
          <Input
            className="mt-1"
            value={exam.title}
            disabled={locked}
            onChange={e => setExam(ex => (ex ? { ...ex, title: e.target.value } : ex))}
            onBlur={e => patchExam({ title: e.target.value })}
          />
          {exam.course_title && <p className="mt-1 text-xs text-muted-foreground">{exam.course_title}</p>}
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">{tt("Durée (min)", "Duration (min)", "المدة (دقائق)")}</label>
          <Input
            className="mt-1" type="number" min="5"
            value={exam.duration_minutes}
            disabled={locked}
            onChange={e => setExam(ex => (ex ? { ...ex, duration_minutes: parseInt(e.target.value) || ex.duration_minutes } : ex))}
            onBlur={e => patchExam({ duration_minutes: parseInt(e.target.value) || exam.duration_minutes })}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[240px_1fr]">
        {/* Sidebar */}
        <div className="dash-card h-fit p-3">
          <div className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            {tt("Questions", "Questions", "الأسئلة")} ({questions.length})
          </div>
          <div className="space-y-1">
            {questions.map((q, i) => (
              <div
                key={q.id}
                className={`group flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm ${activeId === q.id ? "bg-primary/10 font-medium text-primary" : "hover:bg-muted/60"}`}
              >
                <button type="button" className="min-w-0 flex-1 truncate text-left" onClick={() => setActiveId(q.id)}>
                  Q{i + 1}. {q.question.trim() || <span className="italic text-muted-foreground">{tt("sans texte", "untitled", "بدون نص")}</span>}
                </button>
                {savingIds.has(q.id) && <Loader2 className="h-3 w-3 shrink-0 animate-spin text-muted-foreground" />}
                {!locked && (
                  <div className="hidden shrink-0 items-center group-hover:flex">
                    <button type="button" title={tt("Monter", "Move up", "تحريك لأعلى")} disabled={i === 0} onClick={() => moveQuestion(q.id, -1)} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronUp className="h-3.5 w-3.5" /></button>
                    <button type="button" title={tt("Descendre", "Move down", "تحريك لأسفل")} disabled={i === questions.length - 1} onClick={() => moveQuestion(q.id, 1)} className="p-0.5 text-muted-foreground hover:text-foreground disabled:opacity-30"><ChevronDown className="h-3.5 w-3.5" /></button>
                  </div>
                )}
              </div>
            ))}
          </div>
          {!locked && (
            <button type="button" onClick={() => addQuestion()} className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-border py-2 text-xs font-medium text-muted-foreground hover:border-primary/50 hover:text-primary">
              <Plus className="h-3.5 w-3.5" />{tt("Question", "Question", "سؤال")}
            </button>
          )}
        </div>

        {/* Main editor panel */}
        <div className="dash-card p-5">
          {!active ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center text-muted-foreground">
              <p className="text-sm">{tt("Aucune question pour l'instant.", "No questions yet.", "لا توجد أسئلة بعد.")}</p>
              {!locked && (
                <button type="button" onClick={() => addQuestion()} className="btn-c btn-c-primary btn-c-sm">
                  <Plus size={14} strokeWidth={1.7} />{tt("Ajouter une question", "Add a question", "إضافة سؤال")}
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Q{questions.findIndex(q => q.id === active.id) + 1}
                </span>
                {!locked && (
                  <div className="flex items-center gap-1">
                    <button type="button" title={tt("Dupliquer", "Duplicate", "تكرار")} onClick={() => addQuestion(active)} className="btn-c btn-c-ghost btn-c-sm"><Copy className="h-3.5 w-3.5" /></button>
                    <button type="button" title={tt("Supprimer", "Delete", "حذف")} onClick={() => setConfirmDeleteId(active.id)} className="btn-c btn-c-ghost btn-c-sm text-destructive"><Trash2 className="h-3.5 w-3.5" /></button>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-4">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">{tt("Type", "Type", "النوع")}</label>
                  <div className="mt-1 flex gap-3">
                    {(["multiple_choice", "true_false"] as QuestionType[]).map(t => (
                      <label key={t} className="flex items-center gap-1.5 text-sm">
                        <input type="radio" name={`type-${active.id}`} disabled={locked} checked={active.type === t}
                          onChange={() => { updateLocal(active.id, { type: t }); patchQuestion(active.id, { type: t }); }} className="h-3.5 w-3.5 accent-[var(--pal-primary)]" />
                        {t === "multiple_choice" ? "QCM" : tt("Vrai / Faux", "True / False", "صح / خطأ")}
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">{tt("Difficulté", "Difficulty", "الصعوبة")}</label>
                  <div className="mt-1 flex gap-3">
                    {(["easy", "medium", "hard"] as Difficulty[]).map(d => (
                      <label key={d} className="flex items-center gap-1.5 text-sm">
                        <input type="radio" name={`diff-${active.id}`} disabled={locked} checked={active.difficulty === d}
                          onChange={() => { updateLocal(active.id, { difficulty: d }); patchQuestion(active.id, { difficulty: d }); }} className="h-3.5 w-3.5 accent-[var(--pal-primary)]" />
                        {d === "easy" ? tt("Facile", "Easy", "سهل") : d === "medium" ? tt("Moyenne", "Medium", "متوسط") : tt("Difficile", "Hard", "صعب")}
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">{tt("Points", "Points", "النقاط")}</label>
                  <Input
                    className="mt-1 h-8 w-20 text-sm" type="number" min="0.5" step="0.5" disabled={locked}
                    value={active.points}
                    onChange={e => updateLocal(active.id, { points: parseFloat(e.target.value) || active.points })}
                    onBlur={e => patchQuestion(active.id, { points: parseFloat(e.target.value) || active.points })}
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-medium text-muted-foreground">{tt("Énoncé de la question", "Question text", "نص السؤال")}</label>
                <Textarea
                  className="mt-1" rows={3} disabled={locked}
                  value={active.question}
                  onChange={e => updateLocal(active.id, { question: e.target.value })}
                  onBlur={e => patchQuestion(active.id, { question: e.target.value })}
                />
              </div>

              {/* Image */}
              <div>
                <label className="text-xs font-medium text-muted-foreground">{tt("Image", "Image", "صورة")}</label>
                {active.image_url ? (
                  <div className="mt-1.5 space-y-2">
                    <img src={active.image_url} alt="" className="max-h-56 rounded-xl border border-border object-contain" />
                    {!locked && (
                      <div className="flex gap-2">
                        <button type="button" onClick={() => openImagePicker(active.id)} className="btn-c btn-c-ghost btn-c-sm"><ImageIcon className="h-3.5 w-3.5" />{tt("Remplacer", "Replace", "استبدال")}</button>
                        <button type="button" onClick={() => removeImage(active.id)} className="btn-c btn-c-ghost btn-c-sm text-destructive"><X className="h-3.5 w-3.5" />{tt("Retirer", "Remove", "إزالة")}</button>
                      </div>
                    )}
                  </div>
                ) : !locked ? (
                  <button type="button" onClick={() => openImagePicker(active.id)} className="mt-1.5 flex items-center gap-2 rounded-xl border border-dashed border-border px-4 py-3 text-xs text-muted-foreground hover:border-primary/50 hover:text-primary">
                    <ImageIcon className="h-4 w-4" />{tt("Ajouter une image (JPEG/PNG/WebP, max 8 Mo)", "Add an image (JPEG/PNG/WebP, max 8MB)", "إضافة صورة (JPEG/PNG/WebP، الحد الأقصى 8 ميغابايت)")}
                  </button>
                ) : (
                  <p className="mt-1.5 text-xs text-muted-foreground">{tt("Aucune image.", "No image.", "لا توجد صورة.")}</p>
                )}
              </div>

              {/* Options */}
              <div>
                <label className="text-xs font-medium text-muted-foreground">{tt("Réponses", "Answers", "الإجابات")}</label>
                <div className="mt-1.5 space-y-2">
                  {active.options.map((opt, oi) => (
                    <div key={oi} className="flex items-center gap-2">
                      <button
                        type="button" disabled={locked}
                        onClick={() => { updateLocal(active.id, { correct_index: oi }); patchQuestion(active.id, { correct_index: oi }); }}
                        title={tt("Marquer comme bonne réponse", "Mark as correct answer", "وضع علامة كإجابة صحيحة")}
                        className={`h-5 w-5 shrink-0 rounded-full border-2 transition-colors ${active.correct_index === oi ? "border-primary bg-primary" : "border-muted-foreground/30"}`}
                      />
                      {active.type === "true_false" ? (
                        <span className="text-sm">{opt}</span>
                      ) : (
                        <>
                          <Input
                            className="h-8 text-sm" disabled={locked}
                            placeholder={`${tt("Option", "Option", "خيار")} ${String.fromCharCode(65 + oi)}`}
                            value={opt}
                            onChange={e => updateLocal(active.id, { options: active.options.map((o, j) => (j === oi ? e.target.value : o)) })}
                            onBlur={e => patchQuestion(active.id, { options: active.options.map((o, j) => (j === oi ? e.target.value : o)) })}
                          />
                          {!locked && active.options.length > 2 && (
                            <button type="button" onClick={() => {
                              const nextOptions = active.options.filter((_, j) => j !== oi);
                              const nextCorrect = active.correct_index === oi ? 0 : active.correct_index > oi ? active.correct_index - 1 : active.correct_index;
                              updateLocal(active.id, { options: nextOptions, correct_index: nextCorrect });
                              patchQuestion(active.id, { options: nextOptions, correct_index: nextCorrect });
                            }} className="text-muted-foreground hover:text-destructive"><X className="h-3.5 w-3.5" /></button>
                          )}
                        </>
                      )}
                    </div>
                  ))}
                  {!locked && active.type === "multiple_choice" && active.options.length < 8 && (
                    <button type="button" onClick={() => updateLocal(active.id, { options: [...active.options, ""] })} className="text-xs font-medium text-primary hover:underline">
                      + {tt("Ajouter une option", "Add an option", "إضافة خيار")}
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Delete confirm */}
      <Dialog open={!!confirmDeleteId} onOpenChange={o => !o && setConfirmDeleteId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display">{tt("Supprimer cette question ?", "Delete this question?", "حذف هذا السؤال؟")}</DialogTitle>
            <DialogDescription>{tt("Cette action est définitive.", "This action is permanent.", "هذا الإجراء نهائي.")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDeleteId(null)}>{tt("Annuler", "Cancel", "إلغاء")}</Button>
            <Button variant="destructive" onClick={() => confirmDeleteId && deleteQuestion(confirmDeleteId)}>{tt("Supprimer", "Delete", "حذف")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Preview — same QuestionView component the real student exam renders */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="font-display">{tt("Aperçu — vue étudiant", "Preview — student view", "معاينة — عرض الطالب")}</DialogTitle>
            <DialogDescription>{exam.title} · {exam.duration_minutes} {tt("min", "min", "دقيقة")}</DialogDescription>
          </DialogHeader>
          {questions.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">{tt("Aucune question à prévisualiser.", "No questions to preview.", "لا توجد أسئلة للمعاينة.")}</p>
          ) : (
            <div className="space-y-4">
              <p className="text-xs text-muted-foreground">{tt("Question", "Question", "سؤال")} {previewIndex + 1} / {questions.length}</p>
              <QuestionView q={questions[previewIndex]} index={previewIndex} />
              <div className="flex justify-between pt-2">
                <Button variant="outline" size="sm" disabled={previewIndex === 0} onClick={() => setPreviewIndex(i => i - 1)}>{tt("Précédent", "Previous", "السابق")}</Button>
                <Button variant="outline" size="sm" disabled={previewIndex === questions.length - 1} onClick={() => setPreviewIndex(i => i + 1)}>{tt("Suivant", "Next", "التالي")}</Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
