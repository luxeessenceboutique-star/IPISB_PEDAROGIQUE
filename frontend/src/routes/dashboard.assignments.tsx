import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import {
  FileText, Plus, Loader2, AlertCircle,
  Send, Trash2, Paperclip, ExternalLink, BarChart3, ClipboardList, Upload, Check,
} from "lucide-react";
import { ListSkeleton } from "@/components/Skeletons";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";
import { useDeepLinkFocus } from "@/lib/deep-link";

export const Route = createFileRoute("/dashboard/assignments")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: AssignmentsPage,
});

type Assignment = {
  id: string; course_id: string; title: string; description: string | null;
  due_date: string | null; max_grade: number; created_at: string;
  course_title?: string; submission?: Submission | null;
};
type Submission = {
  id: string; content: string | null; file_url: string | null; submitted_at: string;
  grade: number | null; feedback: string | null; student_id?: string; student_name?: string;
};
type Course = { id: string; title: string };

type AStatus = "graded" | "submitted" | "late" | "todo";

function aStatus(a: Assignment): AStatus {
  if (a.submission) {
    if (a.submission.grade !== null && a.submission.grade !== undefined) return "graded";
    return "submitted";
  }
  if (a.due_date && new Date(a.due_date) < new Date()) return "late";
  return "todo";
}

function statusInfo(a: Assignment, lang: string) {
  const s = aStatus(a);
  if (s === "graded")
    return { label: lang === "fr" ? "Noté" : lang === "ar" ? "مصحَّح" : "Graded", chip: "chip-c-ink", icon: Check, iconColor: "var(--pal-primary)" };
  if (s === "submitted")
    return { label: lang === "fr" ? "Soumis" : lang === "ar" ? "مُسلَّم" : "Submitted", chip: "chip-c-green", icon: Upload, iconColor: "var(--pal-primary)" };
  if (s === "late")
    return { label: lang === "fr" ? "En retard" : lang === "ar" ? "متأخر" : "Late", chip: "chip-c-red", icon: AlertCircle, iconColor: "var(--pal-danger)" };
  return { label: lang === "fr" ? "À rendre" : lang === "ar" ? "قيد الانتظار" : "To submit", chip: "chip-c-amber", icon: ClipboardList, iconColor: "var(--pal-accent)" };
}

function AssignmentsPage() {
  const { t, lang } = useI18n();
  const { user, roles } = useAuth();
  const isAdmin   = roles.includes("admin");
  const isProf    = roles.includes("professor");
  const canCreate = isAdmin || isProf;

  const [assignments,        setAssignments]        = useState<Assignment[]>([]);
  const [myCourses,          setMyCourses]          = useState<Course[]>([]);
  const [loading,            setLoading]            = useState(true);
  const { focusId, attachFocus } = useDeepLinkFocus();

  // Create dialog
  const [showCreate,  setShowCreate]  = useState(false);
  const [creating,    setCreating]    = useState(false);
  const [createForm,  setCreateForm]  = useState({ title: "", description: "", due_date: "", max_grade: "20", course_id: "" });

  // Delete
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Status filter (pill tabs — IPISB Connect redesign)
  const [filter, setFilter] = useState<"all" | "todo" | "submitted" | "graded">("all");

  // Submit dialog
  const [submitDialog,   setSubmitDialog]   = useState<Assignment | null>(null);
  const [submitContent,  setSubmitContent]  = useState("");
  const [submitFile,     setSubmitFile]     = useState<File | null>(null);
  const [submitting,     setSubmitting]     = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Grade dialog
  const [gradeDialog,        setGradeDialog]        = useState<{ assignment: Assignment; submissions: Submission[] } | null>(null);
  const [gradeValues,        setGradeValues]        = useState<Record<string, { grade: string; feedback: string }>>({});
  const [grading,            setGrading]            = useState<string | null>(null);
  const [loadingSubmissions, setLoadingSubmissions] = useState(false);

  async function load() {
    if (!user) return;
    setLoading(true);
    try {
      if (canCreate) {
        const courseQuery = isAdmin
          ? supabase.from("courses").select("id, title")
          : supabase.from("courses").select("id, title").eq("professor_id", user!.id);
        const { data: courses } = await courseQuery;
        const courseMap: Record<string, string> = Object.fromEntries((courses ?? []).map((c: any) => [c.id, c.title]));
        const courseIds = Object.keys(courseMap);
        setMyCourses((courses ?? []) as Course[]);
        if (!courseIds.length) { setAssignments([]); return; }
        const { data: raw } = await supabase.from("assignments").select("*").in("course_id", courseIds).order("created_at", { ascending: false });
        setAssignments((raw ?? []).map((a: any) => ({ ...a, course_title: courseMap[a.course_id] ?? "—" })));
      } else {
        const { data: enrollments } = await supabase.from("course_enrollments").select("course_id").eq("student_id", user!.id);
        const enrolledIds = (enrollments ?? []).map((e: any) => e.course_id);
        if (!enrolledIds.length) { setAssignments([]); return; }
        const { data: courses } = await supabase.from("courses").select("id, title").in("id", enrolledIds);
        const courseMap: Record<string, string> = Object.fromEntries((courses ?? []).map((c: any) => [c.id, c.title]));
        const { data: raw } = await supabase.from("assignments").select("*").in("course_id", enrolledIds).order("due_date");
        const aList = raw ?? [];
        if (!aList.length) { setAssignments([]); return; }
        const assignIds = aList.map((a: any) => a.id);
        const { data: subs } = await supabase.from("submissions").select("*").eq("student_id", user!.id).in("assignment_id", assignIds);
        const subMap: Record<string, any> = Object.fromEntries((subs ?? []).map((s: any) => [s.assignment_id, s]));
        setAssignments(aList.map((a: any) => ({ ...a, course_title: courseMap[a.course_id] ?? "—", submission: subMap[a.id] ?? null })));
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { if (user) load(); }, [user]);

  if (!user) return null;

  // ---------- Stats ----------
  const total     = assignments.length;
  const submitted = assignments.filter(a => a.submission).length;
  const graded    = assignments.filter(a => a.submission?.grade !== null && a.submission?.grade !== undefined).length;
  const pending   = assignments.filter(a => !a.submission && !(a.due_date && new Date(a.due_date) < new Date())).length;

  // ---------- Create ----------
  async function createAssignment() {
    if (!createForm.title.trim()) { toast.error(t("assignments.title_required")); return; }
    if (!createForm.course_id)    { toast.error(t("assignments.course_required")); return; }
    setCreating(true);
    const { error } = await supabase.from("assignments").insert({
      title:       createForm.title,
      description: createForm.description || null,
      due_date:    createForm.due_date || null,
      max_grade:   parseFloat(createForm.max_grade) || 20,
      course_id:   createForm.course_id,
    });
    setCreating(false);
    if (error) { toast.error(error.message); return; }
    toast.success(t("assignments.created"));
    setShowCreate(false);
    setCreateForm({ title: "", description: "", due_date: "", max_grade: "20", course_id: "" });
    load();
  }

  // ---------- Delete ----------
  async function deleteAssignment(id: string) {
    setDeletingId(id);
    const { error } = await supabase.from("assignments").delete().eq("id", id);
    setDeletingId(null);
    if (error) { toast.error(error.message); return; }
    toast.success(t("assignments.deleted"));
    setAssignments(prev => prev.filter(a => a.id !== id));
  }

  // ---------- Submit ----------
  async function submitAssignment() {
    if (!submitDialog) return;
    setSubmitting(true);

    let fileUrl: string | null = submitDialog.submission?.file_url ?? null;

    // Upload new file if provided
    if (submitFile) {
      const ext   = submitFile.name.split(".").pop();
      const path  = `${user!.id}/${submitDialog.id}_${Date.now()}.${ext}`;
      const { error: upErr } = await supabase.storage.from("submissions").upload(path, submitFile, { upsert: true });
      if (upErr) {
        toast.error(upErr.message);
        setSubmitting(false);
        return;
      }
      const { data: urlData } = supabase.storage.from("submissions").getPublicUrl(path);
      fileUrl = urlData.publicUrl;
    }

    const existing = submitDialog.submission;
    let error: any;
    if (existing) {
      ({ error } = await supabase.from("submissions").update({ content: submitContent || null, file_url: fileUrl }).eq("id", existing.id));
    } else {
      ({ error } = await supabase.from("submissions").insert({ assignment_id: submitDialog.id, student_id: user!.id, content: submitContent || null, file_url: fileUrl }));
    }
    setSubmitting(false);
    if (error) { toast.error(error.message); return; }
    toast.success(t("assignments.submitted"));
    setSubmitDialog(null);
    setSubmitContent("");
    setSubmitFile(null);
    load();
  }

  // ---------- Grade ----------
  async function openGradeDialog(assignment: Assignment) {
    setLoadingSubmissions(true);
    setGradeDialog({ assignment, submissions: [] });
    const { data: subs } = await supabase.from("submissions").select("*").eq("assignment_id", assignment.id);
    const subList: Submission[] = subs ?? [];
    const studentIds = subList.map(s => s.student_id!).filter(Boolean);
    let nameMap: Record<string, string> = {};
    if (studentIds.length) {
      const { data: profiles } = await supabase.from("profiles").select("id, full_name").in("id", studentIds);
      nameMap = Object.fromEntries((profiles ?? []).map((p: any) => [p.id, p.full_name ?? p.id]));
    }
    const withNames = subList.map(s => ({ ...s, student_name: nameMap[s.student_id!] ?? s.student_id! }));
    const initGrades: Record<string, { grade: string; feedback: string }> = {};
    withNames.forEach(s => { initGrades[s.id] = { grade: s.grade !== null ? String(s.grade) : "", feedback: s.feedback ?? "" }; });
    setGradeValues(initGrades);
    setGradeDialog({ assignment, submissions: withNames });
    setLoadingSubmissions(false);
  }

  async function saveGrade(submissionId: string) {
    const vals = gradeValues[submissionId];
    if (!vals) return;
    setGrading(submissionId);
    const { error } = await supabase.from("submissions").update({
      grade:    vals.grade !== "" ? parseFloat(vals.grade) : null,
      feedback: vals.feedback || null,
    }).eq("id", submissionId);
    setGrading(null);
    if (error) { toast.error(error.message); return; }
    toast.success(t("assignments.graded"));
  }

  const fmt = (d: string | null) =>
    d ? new Date(d).toLocaleDateString(lang === "fr" ? "fr-FR" : lang === "ar" ? "ar-MA" : "en-US", { year: "numeric", month: "short", day: "numeric" }) : "—";

  const tabs: Array<[typeof filter, string]> = [
    ["all",       lang === "fr" ? "Tous" : lang === "ar" ? "الكل" : "All"],
    ["todo",      lang === "fr" ? "À rendre" : lang === "ar" ? "قيد الانتظار" : "To submit"],
    ["submitted", lang === "fr" ? "Soumis" : lang === "ar" ? "مُسلَّم" : "Submitted"],
    ["graded",    lang === "fr" ? "Notés" : lang === "ar" ? "مصحَّح" : "Graded"],
  ];
  const visible = assignments.filter(a => {
    if (filter === "all") return true;
    const s = aStatus(a);
    if (filter === "todo") return s === "todo" || s === "late";
    return s === filter;
  });

  return (
    <div>
      <PageHead
        eyebrow={lang === "fr" ? "Travaux & rendus" : lang === "ar" ? "الأعمال والتسليمات" : "Work & submissions"}
        title={t("dash.assignments")}
        sub={!loading && total > 0
          ? (lang === "fr"
              ? `${pending} en attente · ${submitted} soumis · ${graded} notés`
              : `${pending} pending · ${submitted} submitted · ${graded} graded`)
          : t("assignments.subtitle")}
        actions={canCreate ? (
          <button type="button" onClick={() => setShowCreate(true)} className="btn-c btn-c-primary">
            <Plus size={15} strokeWidth={1.7} />{t("assignments.create")}
          </button>
        ) : undefined}
      />

      {/* Pill tab filter — student view */}
      {!canCreate && !loading && total > 0 && (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {tabs.map(([k, l]) => (
            <button key={k} type="button" className={`tab-c${filter === k ? " is-active" : ""}`} onClick={() => setFilter(k)}>
              {l}
            </button>
          ))}
        </div>
      )}

      {/* List */}
      {loading ? (
        <ListSkeleton rows={4} />
      ) : assignments.length === 0 ? (
        <div className="dash-card">
          <EmptyHint icon={<FileText size={28} strokeWidth={1.7} />} text={t("assignments.empty")} />
        </div>
      ) : (
        <div className="dash-card card-pop overflow-hidden">
          {visible.map(a => {
            const { label, chip, icon: Icon, iconColor } = statusInfo(a, lang);
            return (
              <div key={a.id} ref={a.id === focusId ? attachFocus : undefined} className="row-c flex-wrap">
                <span className="flex shrink-0" style={{ color: iconColor }}>
                  <Icon size={20} strokeWidth={1.7} />
                </span>
                <div className="min-w-0 flex-1" style={{ minWidth: 180 }}>
                  <div style={{ fontWeight: 700, fontSize: 14, color: "var(--pal-ink)" }}>{a.title}</div>
                  <div className="mt-0.5" style={{ fontSize: 12, color: "var(--pal-muted)" }}>
                    {a.course_title} · {t("assignments.due")}: {fmt(a.due_date)} · /{a.max_grade} {t("assignments.points")}
                  </div>
                  {!canCreate && a.submission?.feedback && (
                    <div className="mt-0.5" style={{ fontSize: 12, color: "var(--pal-primary-deep)" }}>{a.submission.feedback}</div>
                  )}
                </div>
                {!canCreate && (
                  aStatus(a) === "graded"
                    ? <span className="chip-c chip-c-ink">{label} · {a.submission!.grade} / {a.max_grade}</span>
                    : <span className={`chip-c ${chip}`}>{label}</span>
                )}
                {!canCreate && (
                  <button
                    type="button"
                    className={`btn-c btn-c-sm ${a.submission ? "btn-c-ghost" : "btn-c-primary"}`}
                    onClick={() => { setSubmitContent(a.submission?.content ?? ""); setSubmitFile(null); setSubmitDialog(a); }}
                  >
                    <Send size={13} strokeWidth={1.7} />
                    {a.submission
                      ? (lang === "fr" ? "Modifier" : lang === "ar" ? "تعديل" : "Edit")
                      : (lang === "fr" ? "Déposer" : lang === "ar" ? "تسليم" : t("assignments.submit.btn"))}
                  </button>
                )}
                {canCreate && (
                  <>
                    <button type="button" className="btn-c btn-c-ghost btn-c-sm" onClick={() => openGradeDialog(a)}>
                      <BarChart3 size={13} strokeWidth={1.7} />{t("assignments.view_submissions")}
                    </button>
                    <button
                      type="button"
                      className="rounded-lg p-1.5 text-muted-foreground hover:text-destructive"
                      disabled={deletingId === a.id}
                      aria-label="Delete"
                      onClick={() => {
                        if (window.confirm(t("assignments.delete_confirm"))) deleteAssignment(a.id);
                      }}
                    >
                      {deletingId === a.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    </button>
                  </>
                )}
              </div>
            );
          })}
          {visible.length === 0 && (
            <EmptyHint icon={<FileText size={28} strokeWidth={1.7} />} text={t("assignments.empty")} />
          )}
        </div>
      )}

      {/* ── Create Dialog ── */}
      <Dialog open={showCreate} onOpenChange={setShowCreate}>
        <DialogContent>
          <DialogHeader><DialogTitle className="font-display">{t("assignments.create")}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t("assignments.form.course")} *</label>
              <Select value={createForm.course_id} onValueChange={v => setCreateForm(f => ({ ...f, course_id: v }))}>
                <SelectTrigger className="mt-1.5"><SelectValue placeholder={lang === "fr" ? "Choisir un cours" : lang === "ar" ? "اختر درسًا" : "Choose a course"} /></SelectTrigger>
                <SelectContent>{myCourses.map(c => <SelectItem key={c.id} value={c.id}>{c.title}</SelectItem>)}</SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-sm font-medium">{t("assignments.form.title")} *</label>
              <Input className="mt-1.5" value={createForm.title} onChange={e => setCreateForm(f => ({ ...f, title: e.target.value }))} />
            </div>
            <div>
              <label className="text-sm font-medium">{t("assignments.form.description")}</label>
              <Textarea className="mt-1.5" rows={3} value={createForm.description} onChange={e => setCreateForm(f => ({ ...f, description: e.target.value }))} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">{t("assignments.form.due_date")}</label>
                <Input className="mt-1.5" type="datetime-local" value={createForm.due_date} onChange={e => setCreateForm(f => ({ ...f, due_date: e.target.value }))} />
              </div>
              <div>
                <label className="text-sm font-medium">{t("assignments.form.max_grade")}</label>
                <Input className="mt-1.5" type="number" min="1" value={createForm.max_grade} onChange={e => setCreateForm(f => ({ ...f, max_grade: e.target.value }))} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreate(false)}>{t("common.cancel")}</Button>
            <Button className="border-0 bg-gradient-brand text-white" disabled={creating} onClick={createAssignment}>
              {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : t("assignments.create")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Submit Dialog ── */}
      <Dialog open={!!submitDialog} onOpenChange={o => { if (!o) { setSubmitDialog(null); setSubmitFile(null); setSubmitContent(""); } }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="font-display">{submitDialog?.title}</DialogTitle>
            {submitDialog?.description && <p className="mt-1 text-sm text-muted-foreground">{submitDialog.description}</p>}
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium">{t("assignments.submit.label")}</label>
              <Textarea
                className="mt-1.5"
                rows={5}
                value={submitContent}
                onChange={e => setSubmitContent(e.target.value)}
                placeholder={lang === "fr" ? "Votre réponse…" : lang === "ar" ? "إجابتك…" : "Your answer…"}
              />
            </div>
            <div>
              <label className="text-sm font-medium">{lang === "fr" ? "Pièce jointe (optionnel)" : lang === "ar" ? "مرفق (اختياري)" : "Attachment (optional)"}</label>
              <div className="mt-1.5 flex items-center gap-2">
                <input ref={fileInputRef} type="file" className="hidden" onChange={e => setSubmitFile(e.target.files?.[0] ?? null)} />
                <Button type="button" variant="outline" size="sm" className="h-8 text-xs" onClick={() => fileInputRef.current?.click()}>
                  <Paperclip className="h-3 w-3" />{lang === "fr" ? "Choisir un fichier" : lang === "ar" ? "اختر ملفًا" : "Choose file"}
                </Button>
                {submitFile && <span className="truncate text-xs text-muted-foreground">{submitFile.name}</span>}
                {!submitFile && submitDialog?.submission?.file_url && (
                  <a href={submitDialog.submission.file_url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-xs text-primary hover:underline">
                    <ExternalLink className="h-3 w-3" />{lang === "fr" ? "Fichier actuel" : lang === "ar" ? "الملف الحالي" : "Current file"}
                  </a>
                )}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setSubmitDialog(null); setSubmitFile(null); setSubmitContent(""); }}>{t("common.cancel")}</Button>
            <Button className="border-0 bg-gradient-brand text-white" disabled={submitting} onClick={submitAssignment}>
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : t("assignments.submit.btn")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Grade Dialog ── */}
      <Dialog open={!!gradeDialog} onOpenChange={o => !o && setGradeDialog(null)}>
        <DialogContent className="max-h-[90vh] sm:max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-display">{t("assignments.submissions")} — {gradeDialog?.assignment.title}</DialogTitle>
            <p className="text-sm text-muted-foreground">
              {gradeDialog?.submissions.length ?? 0} {t("assignments.submissions")} · {lang === "fr" ? "max" : "max"} {gradeDialog?.assignment.max_grade} {t("assignments.points")}
            </p>
          </DialogHeader>
          {loadingSubmissions ? (
            <div className="flex items-center justify-center py-10"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
          ) : gradeDialog?.submissions.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">{t("assignments.no_submission")}</p>
          ) : (
            <div className="space-y-4">
              {gradeDialog?.submissions.map(sub => (
                <div key={sub.id} className="rounded-xl border border-border p-4">
                  <p className="font-medium">{sub.student_name}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">{fmt(sub.submitted_at)}</p>
                  {sub.content && <p className="mt-2 rounded-lg bg-muted p-3 text-sm">{sub.content}</p>}
                  {sub.file_url && (
                    <a href={sub.file_url} target="_blank" rel="noreferrer" className="mt-2 flex items-center gap-1.5 text-xs text-primary hover:underline">
                      <Paperclip className="h-3 w-3" />{lang === "fr" ? "Voir la pièce jointe" : lang === "ar" ? "عرض المرفق" : "View attachment"}<ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium">{t("assignments.grade.label")} / {gradeDialog.assignment.max_grade}</label>
                      <Input
                        className="mt-1 h-8 text-sm"
                        type="number" min="0" max={gradeDialog.assignment.max_grade}
                        value={gradeValues[sub.id]?.grade ?? ""}
                        onChange={e => setGradeValues(v => ({ ...v, [sub.id]: { ...(v[sub.id] ?? { grade: "", feedback: "" }), grade: e.target.value } }))}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-medium">{t("assignments.grade.feedback")}</label>
                      <Input
                        className="mt-1 h-8 text-sm"
                        value={gradeValues[sub.id]?.feedback ?? ""}
                        onChange={e => setGradeValues(v => ({ ...v, [sub.id]: { ...(v[sub.id] ?? { grade: "", feedback: "" }), feedback: e.target.value } }))}
                      />
                    </div>
                  </div>
                  <Button
                    size="sm"
                    className="mt-3 h-8 border-0 bg-gradient-brand text-xs text-white"
                    disabled={grading === sub.id}
                    onClick={() => saveGrade(sub.id)}
                  >
                    {grading === sub.id ? <Loader2 className="h-3 w-3 animate-spin" /> : t("assignments.grade.btn")}
                  </Button>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
