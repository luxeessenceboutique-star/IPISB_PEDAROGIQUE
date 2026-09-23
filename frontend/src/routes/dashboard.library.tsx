import { createFileRoute, redirect } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { Library, Upload, Trash2, Loader2, ExternalLink, FileText, FileImage, File as FileIcon } from "lucide-react";
import { PageHead, EmptyHint } from "@/components/dashboard/ui";

export const Route = createFileRoute("/dashboard/library")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: LibraryPage,
});

type LibFile = {
  id: string; title: string; url: string; size_bytes?: number; mime_type?: string; created_at?: string;
  specialty_id?: string | null; specialty_name?: string | null; uploaded_by?: string; can_delete?: boolean;
};
type Specialty = { id: string; name: string };

const CATEGORY_LABEL: Record<string, { fr: string; en: string }> = {
  cdc:            { fr: "Cahiers des charges (CDC)", en: "Program specs (CDC)" },
  programmes:     { fr: "Programmes de formation",   en: "Training programs" },
  fiches_examens: { fr: "Fiches & banques d'examens", en: "Exam sheets & banks" },
  reglements:     { fr: "Règlements & procédures",   en: "Rules & procedures" },
  autres:         { fr: "Autres",                     en: "Other" },
};
const CATEGORIES = Object.keys(CATEGORY_LABEL);
// Filière-specific categories — an uploader must pick a specialty, and the
// list can be filtered by one. reglements/autres stay institution-wide.
const SPECIALTY_SCOPED = new Set(["cdc", "programmes", "fiches_examens"]);

const API = import.meta.env.VITE_API_URL ?? "http://localhost:9000";

async function authHeader(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

function formatBytes(n?: number) {
  if (!n) return "";
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function fileIcon(mime?: string) {
  const t = (mime ?? "").toLowerCase();
  if (t.includes("pdf")) return <FileText className="h-4 w-4 text-red-500 shrink-0" />;
  if (t.includes("image")) return <FileImage className="h-4 w-4 text-blue-500 shrink-0" />;
  return <FileIcon className="h-4 w-4 text-muted-foreground shrink-0" />;
}

function LibraryPage() {
  const { lang } = useI18n();
  const { user, roles } = useAuth();
  const isAdmin = roles.includes("admin");
  const isProf  = roles.includes("professor");
  const isStaff = isAdmin || isProf;

  const [category, setCategory] = useState(CATEGORIES[0]);
  const [specialties, setSpecialties] = useState<Specialty[]>([]);
  const [mySpecialtyIds, setMySpecialtyIds] = useState<Set<string> | null>(null);
  const [specialtyId, setSpecialtyId] = useState("");
  const [files,    setFiles]    = useState<LibFile[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const scoped = SPECIALTY_SCOPED.has(category);

  useEffect(() => {
    if (!user) return;
    (async () => {
      try {
        const data: Specialty[] = await api.get("/api/specialties");
        setSpecialties(data);
      } catch {
        // non-blocking — the reglements/autres categories still work without it
      }
    })();
  }, [user]);

  // A professor only browses their own filière(s) here — inferred from the
  // classes they created, same source of truth the backend now enforces
  // server-side (list/upload both reject/scope outside this set). Admins
  // see everything, so this stays null (meaning "no restriction") for them.
  useEffect(() => {
    if (!user || isAdmin) return;
    (async () => {
      try {
        const classes: { specialty_id?: string | null }[] = await api.get("/api/classes");
        setMySpecialtyIds(new Set(classes.map(c => c.specialty_id).filter((id): id is string => !!id)));
      } catch {
        setMySpecialtyIds(new Set());
      }
    })();
  }, [user, isAdmin]);

  const visibleSpecialties = mySpecialtyIds ? specialties.filter(s => mySpecialtyIds.has(s.id)) : specialties;

  // Professors land directly on their own filière when they have exactly
  // one — no reason to make them pick from a list of one, or see a
  // "toutes les filières" choice that isn't really theirs to make.
  useEffect(() => {
    if (mySpecialtyIds && mySpecialtyIds.size === 1 && !specialtyId) {
      setSpecialtyId([...mySpecialtyIds][0]);
    }
  }, [mySpecialtyIds]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset the filter when leaving a filière-scoped category — no auto-pick of
  // a specialty on entry: "" means "toutes les filières (général)", a valid
  // choice on its own (e.g. a document that covers several filières at once).
  useEffect(() => {
    if (!scoped && specialtyId) setSpecialtyId("");
  }, [scoped]); // eslint-disable-line react-hooks/exhaustive-deps

  async function load(cat: string, spec: string) {
    setLoading(true);
    try {
      const qs = scoped && spec ? `?specialty_id=${spec}` : "";
      const data: LibFile[] = await api.get(`/api/library/${cat}${qs}`);
      setFiles(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur de chargement");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!user) return;
    load(category, specialtyId);
  }, [user, category, specialtyId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!user || !isStaff) return null;

  async function handleFiles(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    const toUpload = Array.from(fileList);
    if (fileRef.current) fileRef.current.value = "";
    setUploading(true);
    let ok = 0;
    for (const file of toUpload) {
      try {
        const headers = await authHeader();
        const form = new FormData();
        form.append("file", file);
        if (scoped && specialtyId) form.append("specialty_id", specialtyId);
        const res = await fetch(`${API}/api/library/${category}/upload`, { method: "POST", headers, body: form });
        if (!res.ok) throw new Error(await res.text());
        ok++;
      } catch (e) {
        toast.error(`${file.name} — ${e instanceof Error ? e.message : "erreur"}`);
      }
    }
    setUploading(false);
    if (ok > 0) { toast.success(`${ok} fichier${ok > 1 ? "s" : ""} ajouté${ok > 1 ? "s" : ""}`); load(category, specialtyId); }
  }

  async function removeFile(f: LibFile) {
    if (!window.confirm(lang === "fr" ? `Supprimer « ${f.title} » ?` : `Delete "${f.title}"?`)) return;
    try {
      await api.delete(`/api/library/${category}/${encodeURIComponent(f.id)}`);
      setFiles(prev => prev.filter(x => x.id !== f.id));
      toast.success(lang === "fr" ? "Supprimé" : "Deleted");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Erreur");
    }
  }

  return (
    <div className="space-y-6">
      <PageHead
        eyebrow={lang === "fr" ? "Programme" : "Curriculum"}
        title={lang === "fr" ? "Bibliothèque de référence" : "Reference Library"}
        sub={lang === "fr"
          ? "Documents officiels (CDC, programmes, règlements) par filière — consultables par le staff."
          : "Official documents (CDC, programs, rules) by filière — available to staff."}
      />

      {/* Category tabs */}
      <div className="flex gap-1.5 flex-wrap">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            onClick={() => setCategory(cat)}
            className="rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors border"
            style={{
              background: category === cat ? "oklch(22% 0.025 175)" : "transparent",
              color: category === cat ? "white" : "oklch(48% 0.02 180)",
              borderColor: category === cat ? "oklch(22% 0.025 175)" : "oklch(88% 0.015 170)",
            }}
          >
            {lang === "fr" ? CATEGORY_LABEL[cat].fr : CATEGORY_LABEL[cat].en}
          </button>
        ))}
      </div>

      {/* Filière selector — only for filière-scoped categories */}
      {scoped && (
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">
            {lang === "fr" ? "Filière :" : "Filière:"}
          </span>
          <select
            value={specialtyId}
            onChange={e => setSpecialtyId(e.target.value)}
            className="rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs font-medium"
          >
            {/* "Toutes les filières" is an admin concept — a professor only
                ever has their own filière(s) to choose from. */}
            {isAdmin && <option value="">{lang === "fr" ? "Toutes les filières (général)" : "All filières (general)"}</option>}
            {visibleSpecialties.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
      )}

      {/* Upload (admin + professor) */}
      {isStaff && (
        <div
          className="rounded-xl border-2 border-dashed border-border px-4 py-4 text-center text-xs text-muted-foreground cursor-pointer hover:border-primary/60 hover:bg-muted/30 transition-colors"
          onClick={() => fileRef.current?.click()}
          onDragOver={e => e.preventDefault()}
          onDrop={e => { e.preventDefault(); handleFiles(e.dataTransfer.files); }}
        >
          <input ref={fileRef} type="file" multiple accept="*/*" className="hidden" onChange={e => handleFiles(e.target.files)} />
          <Upload className="h-4 w-4 inline mr-1.5 mb-0.5" />
          {uploading
            ? (lang === "fr" ? "Envoi en cours…" : "Uploading…")
            : (lang === "fr"
                ? `Glissez un fichier ici, ou cliquez pour en choisir un — « ${CATEGORY_LABEL[category].fr} »${scoped ? ` · ${specialtyId ? (specialties.find(s => s.id === specialtyId)?.name ?? "") : "toutes les filières"}` : ""}`
                : `Drop a file here, or click to choose one — "${CATEGORY_LABEL[category].en}"${scoped ? ` · ${specialtyId ? (specialties.find(s => s.id === specialtyId)?.name ?? "") : "all filières"}` : ""}`)}
        </div>
      )}

      {/* File list */}
      {loading ? (
        <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div>
      ) : files.length === 0 ? (
        <div className="dash-card">
          <EmptyHint icon={<Library size={28} strokeWidth={1.7} />} text={lang === "fr" ? "Aucun document dans cette catégorie." : "No document in this category."} />
        </div>
      ) : (
        <div className="space-y-2">
          {files.map(f => (
            <div key={f.id} className="rounded-xl border border-border bg-card overflow-hidden">
              <div className="flex items-center gap-3 px-4 py-3">
                {fileIcon(f.mime_type)}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{f.title}</p>
                  <p className="text-xs text-muted-foreground truncate">
                    {formatBytes(f.size_bytes)}
                    {f.specialty_name ? ` · ${f.specialty_name}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <a href={f.url} target="_blank" rel="noopener noreferrer">
                    <button type="button" className="h-7 w-7 p-0 flex items-center justify-center rounded hover:bg-muted transition-colors" title={lang === "fr" ? "Ouvrir" : "Open"}>
                      <ExternalLink className="h-3.5 w-3.5" />
                    </button>
                  </a>
                  {f.can_delete && (
                    <button type="button" onClick={() => removeFile(f)} className="h-7 w-7 p-0 flex items-center justify-center rounded text-destructive hover:bg-destructive/10 transition-colors">
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
