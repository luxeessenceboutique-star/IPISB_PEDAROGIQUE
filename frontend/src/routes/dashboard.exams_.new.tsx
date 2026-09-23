import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ArrowLeft, ArrowRight, BookOpen, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { PageHead } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/exams_/new")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: NewExamPage,
});

type Course = { id: string; title: string };
type Lesson = { id: string; title: string; order_num: number; status: "draft" | "published" };
type ModuleT = { id: string; title: string; order_num: number; status: "draft" | "published"; lessons: Lesson[] };

type Difficulty = "easy" | "medium" | "hard";

function NewExamPage() {
  const { lang } = useI18n();
  const { roles } = useAuth();
  const navigate = useNavigate();
  const isAdmin = roles.includes("admin");
  const fr = lang === "fr";
  const ar = lang === "ar";
  const tt = (f: string, e: string, a: string) => (fr ? f : ar ? a : e);

  const [step, setStep] = useState<1 | 2>(1);

  // Step 1 — course + content
  const [courses, setCourses] = useState<Course[]>([]);
  const [loadingCourses, setLoadingCourses] = useState(true);
  const [courseId, setCourseId] = useState("");
  const [modules, setModules] = useState<ModuleT[]>([]);
  const [loadingModules, setLoadingModules] = useState(false);
  const [fullCourse, setFullCourse] = useState(true);
  const [selectedModules, setSelectedModules] = useState<Set<string>>(new Set());
  const [selectedLessons, setSelectedLessons] = useState<Set<string>>(new Set());
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  // Step 2 — configuration
  const [title, setTitle] = useState("");
  const [duration, setDuration] = useState("60");
  const [targetCount, setTargetCount] = useState("20");
  const [types, setTypes] = useState<{ multiple_choice: boolean; true_false: boolean }>({ multiple_choice: true, true_false: true });
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [mix, setMix] = useState({ easy: 20, medium: 60, hard: 20 });
  const [points, setPoints] = useState("1");
  const [randomizeQuestions, setRandomizeQuestions] = useState(true);
  const [randomizeAnswers, setRandomizeAnswers] = useState(true);
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    (async () => {
      setLoadingCourses(true);
      try {
        const data: Array<{ id: string; title: string }> = await api.get("/api/courses");
        setCourses(data.map(c => ({ id: c.id, title: c.title })));
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Error");
      } finally {
        setLoadingCourses(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!courseId) { setModules([]); return; }
    (async () => {
      setLoadingModules(true);
      try {
        const data: ModuleT[] = await api.get(`/api/courses/${courseId}/modules`);
        setModules(data);
        setFullCourse(true);
        setSelectedModules(new Set(data.map(m => m.id)));
        setSelectedLessons(new Set(data.flatMap(m => m.lessons.map(l => l.id))));
      } catch (e) {
        toast.error(e instanceof Error ? e.message : "Error");
      } finally {
        setLoadingModules(false);
      }
    })();
  }, [courseId]);

  const allModuleIds = useMemo(() => modules.map(m => m.id), [modules]);
  const allLessonIds = useMemo(() => modules.flatMap(m => m.lessons.map(l => l.id)), [modules]);
  const hasSelection = fullCourse ? modules.length > 0 : selectedModules.size > 0 || selectedLessons.size > 0;

  function toggleFullCourse(checked: boolean) {
    setFullCourse(checked);
    if (checked) {
      setSelectedModules(new Set(allModuleIds));
      setSelectedLessons(new Set(allLessonIds));
    }
  }

  function toggleModule(mod: ModuleT, checked: boolean) {
    setFullCourse(false);
    setSelectedModules(prev => {
      const next = new Set(prev);
      checked ? next.add(mod.id) : next.delete(mod.id);
      return next;
    });
    setSelectedLessons(prev => {
      const next = new Set(prev);
      for (const l of mod.lessons) checked ? next.add(l.id) : next.delete(l.id);
      return next;
    });
  }

  function toggleLesson(mod: ModuleT, lessonId: string, checked: boolean) {
    setFullCourse(false);
    setSelectedLessons(prev => {
      const next = new Set(prev);
      checked ? next.add(lessonId) : next.delete(lessonId);
      return next;
    });
    setSelectedModules(prev => {
      const next = new Set(prev);
      const allChecked = mod.lessons.every(l => (l.id === lessonId ? checked : selectedLessons.has(l.id)));
      allChecked ? next.add(mod.id) : next.delete(mod.id);
      return next;
    });
  }

  function toggleCollapsed(moduleId: string) {
    setCollapsed(prev => {
      const next = new Set(prev);
      next.has(moduleId) ? next.delete(moduleId) : next.add(moduleId);
      return next;
    });
  }

  function goToConfig() {
    if (!courseId) { toast.error(tt("Choisissez d'abord un cours.", "Choose a course first.", "اختر الدرس أولاً.")); return; }
    if (!hasSelection) { toast.error(tt("Sélectionnez au moins un module ou une leçon.", "Select at least one module or lesson.", "اختر وحدة أو درسًا واحدًا على الأقل.")); return; }
    if (!title.trim()) {
      const course = courses.find(c => c.id === courseId);
      setTitle(course ? `Examen — ${course.title}` : "");
    }
    setStep(2);
  }

  function updateMix(key: Difficulty, value: number) {
    setMix(prev => ({ ...prev, [key]: Math.max(0, Math.min(100, value)) }));
  }
  const mixSum = mix.easy + mix.medium + mix.hard;

  async function createDraft() {
    if (!title.trim()) { toast.error(tt("Le titre est obligatoire.", "Title is required.", "العنوان مطلوب.")); return; }
    const questionTypes = Object.entries(types).filter(([, v]) => v).map(([k]) => k);
    if (questionTypes.length === 0) { toast.error(tt("Choisissez au moins un type de question.", "Choose at least one question type.", "اختر نوع سؤال واحدًا على الأقل.")); return; }
    if (mixSum !== 100) { toast.error(tt("La distribution de difficulté doit totaliser 100%.", "The difficulty distribution must total 100%.", "يجب أن يصل توزيع الصعوبة إلى 100%.")); return; }

    setCreating(true);
    try {
      const exam = await api.post("/api/exams", {
        title: title.trim(),
        course_id: courseId,
        duration_minutes: parseInt(duration) || 60,
        type: "examen",
        content_scope: {
          mode: fullCourse ? "full_course" : "selected",
          module_ids: fullCourse ? [] : Array.from(selectedModules),
          lesson_ids: fullCourse ? [] : Array.from(selectedLessons),
        },
        generation_config: {
          target_question_count: parseInt(targetCount) || 10,
          question_types: questionTypes,
          difficulty_mix: mix,
          default_points: parseFloat(points) || 1,
        },
        randomize_questions: randomizeQuestions,
        randomize_answers: randomizeAnswers,
      });
      toast.success(tt("Brouillon d'examen créé.", "Exam draft created.", "تم إنشاء مسودة الامتحان."));
      navigate({ to: "/dashboard/exams/$examId/editor", params: { examId: exam.id } });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : tt("Échec de la création.", "Creation failed.", "فشل الإنشاء."));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHead
        eyebrow={tt("Studio d'examens IA", "AI Exam Studio", "استوديو الامتحانات بالذكاء الاصطناعي")}
        title={tt("Créer un examen", "Create an exam", "إنشاء امتحان")}
        sub={step === 1
          ? tt("Étape 1/2 — Choisissez le cours et le contenu à évaluer.", "Step 1/2 — Choose the course and the content to assess.", "الخطوة 1/2 — اختر الدرس والمحتوى المراد تقييمه.")
          : tt("Étape 2/2 — Configurez l'examen.", "Step 2/2 — Configure the exam.", "الخطوة 2/2 — قم بتهيئة الامتحان.")}
        actions={
          <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => (step === 1 ? navigate({ to: "/dashboard/exams" }) : setStep(1))}>
            <ArrowLeft size={14} strokeWidth={1.7} />{tt("Retour", "Back", "رجوع")}
          </button>
        }
      />

      {step === 1 && (
        <div className="space-y-5">
          <div className="dash-card p-5">
            <label className="text-sm font-medium">{tt("Cours", "Course", "الدرس")} *</label>
            <Select value={courseId} onValueChange={setCourseId}>
              <SelectTrigger className="mt-2">
                <SelectValue placeholder={loadingCourses ? "…" : tt("Choisir un cours", "Choose a course", "اختر درسًا")} />
              </SelectTrigger>
              <SelectContent>
                {courses.map(c => <SelectItem key={c.id} value={c.id}>{c.title}</SelectItem>)}
              </SelectContent>
            </Select>
            {isAdmin && courses.length === 0 && !loadingCourses && (
              <p className="mt-2 text-xs text-muted-foreground">{tt("Aucun cours trouvé.", "No courses found.", "لم يتم العثور على دروس.")}</p>
            )}
          </div>

          {courseId && (
            <div className="dash-card p-5">
              <div className="flex items-center justify-between">
                <h3 className="font-display font-semibold">{tt("Contenu à évaluer", "Content to assess", "المحتوى المراد تقييمه")}</h3>
              </div>
              {loadingModules ? (
                <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />{tt("Chargement…", "Loading…", "جارٍ التحميل…")}</div>
              ) : modules.length === 0 ? (
                <p className="py-6 text-sm text-muted-foreground">{tt("Ce cours n'a pas encore de contenu (modules/leçons).", "This course has no content yet (modules/lessons).", "لا يحتوي هذا الدرس على محتوى بعد.")}</p>
              ) : (
                <div className="mt-3 space-y-3">
                  <label className="flex items-center gap-2 rounded-xl border border-border bg-muted/40 px-3 py-2.5 text-sm font-medium">
                    <input type="checkbox" checked={fullCourse} onChange={e => toggleFullCourse(e.target.checked)} className="h-4 w-4 accent-[var(--pal-primary)]" />
                    {tt("Tout le cours", "Entire course", "الدرس بالكامل")}
                  </label>

                  <div className="space-y-1.5">
                    {modules.map(mod => {
                      const modChecked = selectedModules.has(mod.id);
                      const isCollapsed = collapsed.has(mod.id);
                      return (
                        <div key={mod.id} className="rounded-xl border border-border">
                          <div className="flex items-center gap-2 px-3 py-2.5">
                            <button type="button" onClick={() => toggleCollapsed(mod.id)} className="text-muted-foreground hover:text-foreground">
                              {isCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                            </button>
                            <input
                              type="checkbox" checked={modChecked}
                              onChange={e => toggleModule(mod, e.target.checked)}
                              className="h-4 w-4 accent-[var(--pal-primary)]"
                            />
                            <span className="text-sm font-medium">{mod.title}</span>
                            <span className="ml-auto text-xs text-muted-foreground">{mod.lessons.length} {tt("leçons", "lessons", "دروس")}</span>
                          </div>
                          {!isCollapsed && mod.lessons.length > 0 && (
                            <div className="space-y-1 border-t border-border px-3 py-2 pl-9">
                              {mod.lessons.map(l => (
                                <label key={l.id} className="flex items-center gap-2 py-1 text-sm">
                                  <input
                                    type="checkbox" checked={selectedLessons.has(l.id)}
                                    onChange={e => toggleLesson(mod, l.id, e.target.checked)}
                                    className="h-3.5 w-3.5 accent-[var(--pal-primary)]"
                                  />
                                  {l.title}
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end">
            <Button className="border-0 bg-gradient-brand text-white" onClick={goToConfig} disabled={!courseId || loadingModules}>
              {tt("Continuer", "Continue", "متابعة")}<ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <div className="dash-card space-y-4 p-5">
            <div>
              <label className="text-sm font-medium">{tt("Titre", "Title", "العنوان")} *</label>
              <Input className="mt-1.5" value={title} onChange={e => setTitle(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">{tt("Durée (minutes)", "Duration (minutes)", "المدة (دقائق)")}</label>
                <Input className="mt-1.5" type="number" min="5" value={duration} onChange={e => setDuration(e.target.value)} />
              </div>
              <div>
                <label className="text-sm font-medium">{tt("Nombre de questions", "Number of questions", "عدد الأسئلة")}</label>
                <Input className="mt-1.5" type="number" min="1" max="100" value={targetCount} onChange={e => setTargetCount(e.target.value)} />
                <p className="mt-1 text-[11px] text-muted-foreground">{tt("Cible pour la génération IA (phase suivante).", "Target for AI generation (next phase).", "الهدف للتوليد بالذكاء الاصطناعي (المرحلة القادمة).")}</p>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">{tt("Types de questions", "Question types", "أنواع الأسئلة")}</label>
              <div className="mt-2 space-y-1.5">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={types.multiple_choice} onChange={e => setTypes(t => ({ ...t, multiple_choice: e.target.checked }))} className="h-4 w-4 accent-[var(--pal-primary)]" />
                  QCM
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={types.true_false} onChange={e => setTypes(t => ({ ...t, true_false: e.target.checked }))} className="h-4 w-4 accent-[var(--pal-primary)]" />
                  {tt("Vrai / Faux", "True / False", "صح / خطأ")}
                </label>
                <label className="flex items-center gap-2 text-sm text-muted-foreground/60">
                  <input type="checkbox" disabled className="h-4 w-4" />
                  {tt("Question courte", "Short answer", "إجابة قصيرة")} <span className="chip-c">{tt("bientôt", "soon", "قريباً")}</span>
                </label>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">{tt("Difficulté cible", "Target difficulty", "الصعوبة المستهدفة")}</label>
              <div className="mt-2 flex gap-4">
                {(["easy", "medium", "hard"] as Difficulty[]).map(d => (
                  <label key={d} className="flex items-center gap-1.5 text-sm">
                    <input type="radio" name="difficulty" checked={difficulty === d} onChange={() => setDifficulty(d)} className="h-3.5 w-3.5 accent-[var(--pal-primary)]" />
                    {d === "easy" ? tt("Facile", "Easy", "سهل") : d === "medium" ? tt("Moyenne", "Medium", "متوسط") : tt("Difficile", "Hard", "صعب")}
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">{tt("Distribution de difficulté", "Difficulty distribution", "توزيع الصعوبة")}</label>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {(["easy", "medium", "hard"] as Difficulty[]).map(d => (
                  <div key={d}>
                    <span className="text-xs text-muted-foreground">{d === "easy" ? tt("Facile", "Easy", "سهل") : d === "medium" ? tt("Moyenne", "Medium", "متوسط") : tt("Difficile", "Hard", "صعب")}</span>
                    <div className="mt-1 flex items-center gap-1">
                      <Input type="number" min="0" max="100" value={mix[d]} onChange={e => updateMix(d, parseInt(e.target.value) || 0)} className="h-8 text-sm" />
                      <span className="text-xs text-muted-foreground">%</span>
                    </div>
                  </div>
                ))}
              </div>
              <p className={`mt-1.5 text-[11px] ${mixSum === 100 ? "text-muted-foreground" : "text-destructive"}`}>
                {tt("Total", "Total", "المجموع")}: {mixSum}% {mixSum !== 100 && `(${tt("doit être 100%", "must be 100%", "يجب أن يكون 100%")})`}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">{tt("Points par question (défaut)", "Points per question (default)", "النقاط لكل سؤال (افتراضي)")}</label>
                <Input className="mt-1.5" type="number" min="0.5" step="0.5" value={points} onChange={e => setPoints(e.target.value)} />
              </div>
              <div className="flex flex-col justify-end gap-2 pb-1">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={randomizeQuestions} onChange={e => setRandomizeQuestions(e.target.checked)} className="h-4 w-4 accent-[var(--pal-primary)]" />
                  {tt("Mélanger l'ordre des questions", "Shuffle question order", "خلط ترتيب الأسئلة")}
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" checked={randomizeAnswers} onChange={e => setRandomizeAnswers(e.target.checked)} className="h-4 w-4 accent-[var(--pal-primary)]" />
                  {tt("Mélanger l'ordre des réponses", "Shuffle answer order", "خلط ترتيب الإجابات")}
                </label>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-2">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground"><BookOpen size={13} strokeWidth={1.7} />
              {tt("La génération IA sera disponible dans une prochaine phase — l'examen démarre comme un brouillon vide que vous remplissez.", "AI generation will be available in a later phase — the exam starts as an empty draft you fill in.", "سيتوفر التوليد بالذكاء الاصطناعي في مرحلة لاحقة — يبدأ الامتحان كمسودة فارغة تقوم بملئها.")}
            </span>
            <Button className="shrink-0 border-0 bg-gradient-brand text-white" onClick={createDraft} disabled={creating}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {tt("Créer le brouillon", "Create draft", "إنشاء المسودة")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
