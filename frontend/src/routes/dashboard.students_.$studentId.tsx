import { createFileRoute, redirect, Link } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowLeft, Download, Eye, FileText, FolderOpen, IdCard, Loader2,
  QrCode, RefreshCw, ScanSearch, Sparkles, Trash2, TriangleAlert,
  Upload, UserRound, X,
} from "lucide-react";
import { EmptyHint, DashAvatar } from "@/components/dashboard/ui";
import { PreviewModal, urlIsPdf, urlIsInlineViewable, type Preview } from "@/components/dashboard/preview";

export const Route = createFileRoute("/dashboard/students_/$studentId")({
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
  component: StudentDetailPage,
});

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  muted:   "oklch(48% 0.02 180)",
  primary: "oklch(48% 0.085 175)",
  line:    "oklch(88% 0.015 170)",
  paper:   "oklch(99% 0.005 160)",
  pale:    "oklch(95% 0.015 170)",
  danger:  "oklch(64% 0.18 25)",
};
const sans = '"Manrope", system-ui, sans-serif';
const API = import.meta.env.VITE_API_URL ?? "http://localhost:9000";

const STATUT_LABEL: Record<string, string> = {
  actif: "Actif", suspendu: "Suspendu", diplome: "Diplômé", abandon: "Abandon",
};

const FILE_TYPES: { value: string; label: string }[] = [
  { value: "cin", label: "CIN" },
  { value: "bac", label: "Certificat Bac" },
  { value: "photo", label: "Photo d'identité" },
  { value: "cv", label: "CV" },
  { value: "motivation", label: "Lettre de motivation" },
  { value: "autre", label: "Autre" },
];
const FILE_TYPE_LABEL = Object.fromEntries(FILE_TYPES.map(t => [t.value, t.label]));

/** Guess the dossier type from the filename, so "Photo.jpg" doesn't get
 *  uploaded as a CIN just because that's the dropdown default. */
function suggestFileType(filename: string): string | null {
  const n = filename.toLowerCase();
  if (/photo|portrait|identit/.test(n)) return "photo";
  if (/cin|carte.*identite|identite.*carte/.test(n)) return "cin";
  if (/bac|dipl|releve|notes/.test(n)) return "bac";
  if (/\bcv\b|curriculum/.test(n)) return "cv";
  if (/motiv|lettre/.test(n)) return "motivation";
  return null;
}

type StudentDetails = {
  nom: string | null;
  prenom: string | null;
  date_naissance: string | null;
  lieu_naissance: string | null;
  cin: string | null;
  matricule: string | null;
  telephone: string | null;
  email_personnel: string | null;
  adresse: string | null;
  bac_annee: string | null;
};

type StudentDetail = {
  id: string;
  email: string | null;
  full_name: string | null;
  statut: string;
  photo_url: string | null;
  created_at: string;
  classes: { id: string; name: string }[];
  details: StudentDetails | null;
};

const DETAIL_FIELDS: { key: keyof StudentDetails; label: string; type?: string; wide?: boolean }[] = [
  { key: "nom", label: "Nom" },
  { key: "prenom", label: "Prénom" },
  { key: "date_naissance", label: "Date de naissance", type: "date" },
  { key: "lieu_naissance", label: "Lieu de naissance" },
  { key: "cin", label: "N° CIN" },
  { key: "matricule", label: "Matricule" },
  { key: "telephone", label: "Téléphone" },
  { key: "email_personnel", label: "Email personnel" },
  { key: "bac_annee", label: "Année du bac" },
  { key: "adresse", label: "Adresse", wide: true },
];

type StudentFile = {
  id: string;
  type: string;
  filename: string;
  content_type: string;
  created_at: string;
};

type Doc = {
  id: string;
  type: string;
  label: string;
  student_id: string;
  statut: "valide" | "revoque";
  verification_code: string;
  created_at: string;
};

type Template = { id: string; name: string };

async function authHeader(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

/* ─── Générer un document (student fixed, pick a template) ─── */
function GenerateForStudentModal({ student, onClose, onGenerated, onPreview }: {
  student: StudentDetail; onClose: () => void; onGenerated: () => void; onPreview: (p: Preview) => void;
}) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [templateId, setTemplateId] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.get("/api/document-templates")
      .then((ts: Template[]) => { setTemplates(ts); if (ts.length) setTemplateId(ts[0].id); })
      .catch(() => {});
  }, []);

  async function generate() {
    if (!templateId) { toast.error("Sélectionnez un modèle."); return; }
    setBusy(true);
    try {
      const doc = await api.post(`/api/document-templates/${templateId}/generate`, { student_id: student.id });
      toast.success("Document généré !");
      onGenerated();
      onClose();
      if (doc.signed_url) {
        const tpl = templates.find(t => t.id === templateId);
        onPreview({ url: doc.signed_url, title: `${tpl?.name ?? "Document"} — ${student.full_name ?? ""}`, isPdf: urlIsPdf(doc.signed_url) });
      }
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la génération.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 200, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(2px)" }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 16, padding: 32, width: 440, maxWidth: "95vw", boxShadow: "0 24px 60px rgba(0,0,0,.18)" }}>
        <h2 style={{ fontFamily: '"Cormorant Garamond", Georgia, serif', fontSize: 24, fontWeight: 500, color: PAL.ink, margin: "0 0 6px" }}>
          Générer pour {student.full_name}
        </h2>
        {templates.length === 0 ? (
          <p style={{ fontFamily: sans, fontSize: 13, color: PAL.muted }}>
            Aucun modèle disponible. Ajoutez-en un depuis la page Documents.
          </p>
        ) : (
          <>
            <label style={{ fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const }}>Modèle</label>
            <select value={templateId} onChange={e => setTemplateId(e.target.value)} className="u-input"
              style={{ marginTop: 8, marginBottom: 24, width: "100%", padding: "11px 14px", border: `1px solid ${PAL.line}`, borderRadius: 10, fontFamily: sans, fontSize: 14, color: PAL.ink, background: PAL.paper, outline: "none" }}>
              {templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </>
        )}
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button onClick={onClose} className="u-ghost" style={{ fontFamily: sans, fontSize: 13, color: PAL.muted, background: "transparent", border: `1px solid ${PAL.line}`, borderRadius: 8, padding: "10px 18px", cursor: "pointer" }}>Annuler</button>
          {templates.length > 0 && (
            <button onClick={generate} disabled={busy} style={{ fontFamily: sans, fontSize: 13, fontWeight: 600, color: PAL.paper, background: PAL.ink, border: 0, borderRadius: 8, padding: "10px 24px", cursor: busy ? "not-allowed" : "pointer", opacity: busy ? .6 : 1 }}>
              {busy ? "Génération…" : "Générer"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Fichiers tab: dropzone + list ─── */
function FilesTab({ student, onPhotoChanged, onPreview }: {
  student: StudentDetail; onPhotoChanged: () => void; onPreview: (p: Preview) => void;
}) {
  const [files, setFiles] = useState<StudentFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [fileType, setFileType] = useState("cin");
  const [typeTouched, setTypeTouched] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function load() {
    setLoading(true);
    try {
      setFiles(await api.get(`/api/students/${student.id}/files`));
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors du chargement des fichiers.");
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [student.id]);

  async function upload(file: File) {
    // Filename beats the dropdown default ("Photo.jpg" as type CIN would
    // silently skip the profile-photo wiring), but a type the admin picked
    // by hand is never second-guessed.
    const suggested = typeTouched ? null : suggestFileType(file.name);
    const type = suggested ?? fileType;
    if (suggested && suggested !== fileType) setFileType(suggested);
    setUploading(true);
    try {
      const headers = await authHeader();
      const form = new FormData();
      form.append("type", type);
      form.append("file", file);
      const res = await fetch(`${API}/api/students/${student.id}/files`, { method: "POST", headers, body: form });
      if (!res.ok) {
        const text = await res.text();
        try { throw new Error(JSON.parse(text).detail || text); } catch (e: any) { throw new Error(e.message || text); }
      }
      toast.success(type === "photo" ? "Photo ajoutée — elle sera utilisée sur les documents générés." : "Fichier ajouté.");
      if (type === "photo") onPhotoChanged();
      load();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'envoi.");
    } finally {
      setUploading(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function openFile(f: StudentFile) {
    try {
      const res = await api.get(`/api/students/${student.id}/files/${f.id}/download`);
      if (!res.signed_url) return;
      if (urlIsInlineViewable(res.signed_url)) {
        onPreview({ url: res.signed_url, title: `${FILE_TYPE_LABEL[f.type] ?? f.type} — ${f.filename}`, isPdf: urlIsPdf(res.signed_url) });
      } else {
        window.open(res.signed_url, "_blank");
      }
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'ouverture.");
    }
  }

  async function remove(f: StudentFile) {
    if (!window.confirm(`Supprimer « ${f.filename} » ?`)) return;
    try {
      await api.delete(`/api/students/${student.id}/files/${f.id}`);
      toast.success("Fichier supprimé.");
      if (f.type === "photo") onPhotoChanged();
      load();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la suppression.");
    }
  }

  return (
    <div>
      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={e => {
          e.preventDefault(); setDragOver(false);
          const f = e.dataTransfer.files?.[0];
          if (f) upload(f);
        }}
        style={{
          border: `2px dashed ${dragOver ? PAL.primary : PAL.line}`,
          background: dragOver ? PAL.pale : "transparent",
          borderRadius: 14, padding: "34px 20px", textAlign: "center",
          cursor: uploading ? "wait" : "pointer", transition: "all .15s ease", marginBottom: 18,
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.jpg,.jpeg,.png"
          style={{ display: "none" }}
          onChange={e => { const f = e.target.files?.[0]; if (f) upload(f); }}
        />
        <span style={{ display: "inline-flex", color: PAL.muted, opacity: .6 }}>
          {uploading ? <Loader2 size={26} strokeWidth={1.7} className="animate-spin" /> : <Upload size={26} strokeWidth={1.7} />}
        </span>
        <div style={{ fontSize: 13.5, fontWeight: 600, color: PAL.ink, marginTop: 10 }}>
          {uploading ? "Envoi en cours…" : "Déposer un fichier ici"}
        </div>
        <div style={{ fontSize: 12, color: PAL.muted, marginTop: 4 }}>
          PDF, DOCX, JPG, PNG — cliquer pour sélectionner
        </div>
        <div style={{ marginTop: 12, display: "inline-flex", alignItems: "center", gap: 8 }} onClick={e => e.stopPropagation()}>
          <span style={{ fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".08em", textTransform: "uppercase" as const }}>Type :</span>
          <select value={fileType} onChange={e => { setFileType(e.target.value); setTypeTouched(true); }} className="u-input"
            style={{ padding: "6px 10px", border: `1px solid ${PAL.line}`, borderRadius: 8, fontFamily: sans, fontSize: 12.5, color: PAL.ink, background: PAL.paper, outline: "none" }}>
            {FILE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="shimmer" style={{ height: 40, borderRadius: 10 }} />
      ) : files.length === 0 ? (
        <EmptyHint icon={<FolderOpen size={26} strokeWidth={1.7} />} text="Aucun fichier dans le dossier." />
      ) : (
        <div className="dash-card overflow-hidden">
          {files.map(f => (
            <div key={f.id} className="row-c flex-wrap">
              <span className="flex shrink-0" style={{ color: PAL.primary }}>
                <FileText size={18} strokeWidth={1.7} />
              </span>
              <div className="min-w-0 flex-1" style={{ minWidth: 160 }}>
                <div style={{ fontWeight: 700, fontSize: 13.5, color: PAL.ink }}>{f.filename}</div>
                <div className="mt-0.5" style={{ fontSize: 11.5, color: PAL.muted }}>
                  {new Date(f.created_at).toLocaleDateString("fr-FR")}
                </div>
              </div>
              <span className="chip-c">{FILE_TYPE_LABEL[f.type] ?? f.type}</span>
              <button type="button" onClick={() => openFile(f)} className="btn-c btn-c-sm btn-c-ghost" title="Ouvrir">
                <Eye size={13} strokeWidth={1.7} />
              </button>
              <button
                type="button"
                onClick={() => remove(f)}
                className="rounded-lg p-1.5 text-muted-foreground hover:text-destructive"
                aria-label="Supprimer" title="Supprimer"
              >
                <Trash2 size={14} strokeWidth={1.7} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ─── Documents tab: generated documents for this student ─── */
function DocumentsTab({ student, refreshKey, onPreview }: {
  student: StudentDetail; refreshKey: number; onPreview: (p: Preview) => void;
}) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get("/api/documents")
      .then((all: Doc[]) => setDocs(all.filter(d => d.student_id === student.id)))
      .catch((err: any) => toast.error(err?.message ?? "Erreur lors du chargement."))
      .finally(() => setLoading(false));
  }, [student.id, refreshKey]);

  async function openDoc(d: Doc) {
    try {
      const res = await api.get(`/api/documents/${d.id}/download`);
      if (res.signed_url) onPreview({ url: res.signed_url, title: `${d.label} — ${student.full_name ?? ""}`, isPdf: urlIsPdf(res.signed_url) });
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'aperçu.");
    }
  }

  async function download(d: Doc) {
    try {
      const res = await api.get(`/api/documents/${d.id}/download`);
      if (res.signed_url) window.open(res.signed_url, "_blank");
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors du téléchargement.");
    }
  }

  if (loading) return <div className="shimmer" style={{ height: 40, borderRadius: 10 }} />;
  if (docs.length === 0) return <EmptyHint icon={<FileText size={26} strokeWidth={1.7} />} text="Aucun document généré pour ce stagiaire." />;

  return (
    <div className="dash-card overflow-hidden">
      {docs.map(d => (
        <div key={d.id} className="row-c flex-wrap">
          <span className="flex shrink-0" style={{ color: d.statut === "valide" ? PAL.primary : PAL.muted }}>
            <FileText size={18} strokeWidth={1.7} />
          </span>
          <div className="min-w-0 flex-1" style={{ minWidth: 160 }}>
            <div style={{ fontWeight: 700, fontSize: 13.5, color: PAL.ink }}>{d.label}</div>
            <div className="mt-0.5" style={{ fontSize: 11.5, color: PAL.muted, display: "flex", alignItems: "center", gap: 5 }}>
              {new Date(d.created_at).toLocaleDateString("fr-FR")}
              <span style={{ display: "inline-flex", alignItems: "center", gap: 3, fontFamily: '"JetBrains Mono", ui-monospace, monospace', fontSize: 10 }}>
                <QrCode size={10} strokeWidth={1.7} />{d.verification_code}
              </span>
            </div>
          </div>
          <span className={`chip-c ${d.statut === "valide" ? "chip-c-green" : "chip-c-red"}`}>
            {d.statut === "valide" ? "Valide" : "Révoqué"}
          </span>
          <button type="button" onClick={() => openDoc(d)} className="btn-c btn-c-sm btn-c-ghost" title="Aperçu">
            <Eye size={13} strokeWidth={1.7} />
          </button>
          <button type="button" onClick={() => download(d)} className="btn-c btn-c-sm btn-c-ghost" title="Télécharger">
            <Download size={13} strokeWidth={1.7} />
          </button>
        </div>
      ))}
    </div>
  );
}

/* ─── Analyse IA tab: extract student info from dossier files ─── */
type Analysis = {
  resume: string;
  infos: { label: string; valeur: string; source: string }[];
  alertes: string[];
  details?: Record<string, string>;
};
type AnalysisState = {
  analysis: Analysis | null;
  analyzed_at?: string;
  file_count?: number;
  stale?: boolean;
  applied?: number;
};

function AnalyseTab({ student, onApplied }: { student: StudentDetail; onApplied: () => void }) {
  const [state, setState] = useState<AnalysisState | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.get(`/api/students/${student.id}/analysis`)
      .then(setState)
      .catch((err: any) => toast.error(err?.message ?? "Erreur lors du chargement de l'analyse."));
  }, [student.id]);

  async function run() {
    setRunning(true);
    try {
      const res: AnalysisState = await api.post(`/api/students/${student.id}/analysis`, {});
      setState(res);
      toast.success(
        res.applied
          ? `Analyse terminée — fiche administrative remplie (${res.applied} champ${res.applied > 1 ? "s" : ""}).`
          : "Analyse terminée !"
      );
      onApplied(); // the analysis fills the fiche directly — refresh the profile
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de l'analyse.");
    } finally {
      setRunning(false);
    }
  }

  if (!state) return <div className="shimmer" style={{ height: 60, borderRadius: 12 }} />;

  if (running) {
    return (
      <div className="dash-card anim-fade" style={{ padding: "44px 24px", textAlign: "center" }}>
        <Loader2 size={28} strokeWidth={1.7} className="animate-spin" style={{ color: PAL.primary, display: "inline-block" }} />
        <div style={{ fontSize: 14, fontWeight: 700, color: PAL.ink, marginTop: 14 }}>Analyse en cours…</div>
        <div style={{ fontSize: 12.5, color: PAL.muted, marginTop: 6 }}>
          L'IA lit les fichiers du dossier (CIN, bac, CV…) et en extrait les informations. Cela peut prendre jusqu'à une minute.
        </div>
      </div>
    );
  }

  if (!state.analysis) {
    return (
      <div className="dash-card anim-fade" style={{ padding: "44px 24px", textAlign: "center" }}>
        <span style={{ display: "inline-flex", color: PAL.muted, opacity: .55 }}>
          <ScanSearch size={30} strokeWidth={1.6} />
        </span>
        <div style={{ fontSize: 14.5, fontWeight: 700, color: PAL.ink, marginTop: 12 }}>Aucune analyse pour le moment</div>
        <div style={{ fontSize: 12.5, color: PAL.muted, marginTop: 6, maxWidth: 420, marginInline: "auto" }}>
          L'IA lit les fichiers du dossier de {student.full_name ?? "ce stagiaire"} (CIN, certificat du bac, CV…),
          en extrait les informations et remplit directement la fiche administrative du profil.
        </div>
        <button type="button" onClick={run} className="btn-c btn-c-primary" style={{ marginTop: 18 }}>
          <Sparkles size={14} strokeWidth={1.7} />Analyser le dossier
        </button>
      </div>
    );
  }

  const a = state.analysis;
  return (
    <div className="anim-fade">
      {state.stale && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "11px 16px", borderRadius: 12, background: "oklch(96% 0.04 85)", border: "1px solid oklch(85% 0.08 85)", marginBottom: 16, fontSize: 12.5, color: "oklch(40% 0.07 70)" }}>
          <TriangleAlert size={15} strokeWidth={1.8} style={{ flexShrink: 0 }} />
          Le dossier a changé depuis cette analyse — relancez-la pour la mettre à jour.
        </div>
      )}

      {a.resume && (
        <div className="dash-card" style={{ padding: "18px 22px", marginBottom: 16 }}>
          <div style={{ display: "flex", gap: 10 }}>
            <Sparkles size={16} strokeWidth={1.7} style={{ color: PAL.primary, flexShrink: 0, marginTop: 2 }} />
            <p style={{ margin: 0, fontSize: 13.5, lineHeight: 1.65, color: PAL.ink }}>{a.resume}</p>
          </div>
        </div>
      )}

      {a.infos.length > 0 && (
        <div className="dash-card" style={{ padding: "8px 22px 10px", marginBottom: 16 }}>
          {a.infos.map((info, i) => (
            <div key={i} style={{ display: "flex", gap: 14, padding: "11px 0", borderBottom: i < a.infos.length - 1 ? `1px solid ${PAL.line}` : "none", flexWrap: "wrap", alignItems: "baseline" }}>
              <div style={{ width: 170, flexShrink: 0, fontSize: 11.5, fontWeight: 600, color: PAL.muted, letterSpacing: ".07em", textTransform: "uppercase" as const }}>{info.label}</div>
              <div style={{ fontSize: 13.5, color: PAL.ink, flex: 1, minWidth: 160 }}>{info.valeur}</div>
              {info.source && <span className="chip-c" title="Fichier source" style={{ fontSize: 10.5 }}>{info.source}</span>}
            </div>
          ))}
        </div>
      )}

      {a.alertes.length > 0 && (
        <div className="dash-card" style={{ padding: "16px 22px", marginBottom: 16, borderColor: "oklch(85% 0.08 85)" }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".08em", textTransform: "uppercase" as const, color: "oklch(52% 0.12 70)", display: "flex", alignItems: "center", gap: 7, marginBottom: 10 }}>
            <TriangleAlert size={13} strokeWidth={1.8} />À vérifier
          </div>
          {a.alertes.map((al, i) => (
            <div key={i} style={{ fontSize: 13, color: PAL.ink, lineHeight: 1.55, padding: "4px 0" }}>• {al}</div>
          ))}
        </div>
      )}

      <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
        {a.details && Object.keys(a.details).length > 0 && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: PAL.primary, fontWeight: 600 }}>
            <IdCard size={14} strokeWidth={1.7} />
            Fiche administrative remplie automatiquement ({Object.keys(a.details).length} champs)
          </span>
        )}
        <span style={{ fontSize: 12, color: PAL.muted }}>
          Analysé le {state.analyzed_at ? new Date(state.analyzed_at).toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
          {typeof state.file_count === "number" ? ` • ${state.file_count} fichier${state.file_count > 1 ? "s" : ""}` : ""}
        </span>
        <button type="button" onClick={run} className="btn-c btn-c-sm btn-c-ghost">
          <RefreshCw size={13} strokeWidth={1.7} />Relancer l'analyse
        </button>
      </div>
    </div>
  );
}

/* ─── Profil tab ─── */
function detailsToForm(d: StudentDetails | null): Record<string, string> {
  return Object.fromEntries(DETAIL_FIELDS.map(f => [f.key, (d?.[f.key] ?? "") as string]));
}

function ProfilTab({ student, onSaved }: { student: StudentDetail; onSaved: () => void }) {
  const [statut, setStatut] = useState(student.statut);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Record<string, string>>(() => detailsToForm(student.details));
  const [savingDetails, setSavingDetails] = useState(false);

  // Parent reloads the student after a save (or after "Enregistrer dans le
  // profil" on the Analyse tab) — sync the form with the fresh values.
  useEffect(() => { setForm(detailsToForm(student.details)); }, [student.details]);

  const dirty = JSON.stringify(form) !== JSON.stringify(detailsToForm(student.details));

  async function save() {
    setSaving(true);
    try {
      await api.patch(`/api/students/${student.id}`, { statut });
      toast.success("Profil mis à jour.");
      onSaved();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la mise à jour.");
    } finally {
      setSaving(false);
    }
  }

  async function saveDetails() {
    setSavingDetails(true);
    try {
      await api.patch(`/api/students/${student.id}/details`, form);
      toast.success("Fiche administrative mise à jour.");
      onSaved();
    } catch (err: any) {
      toast.error(err?.message ?? "Erreur lors de la mise à jour.");
    } finally {
      setSavingDetails(false);
    }
  }

  const row = (label: string, value: React.ReactNode) => (
    <div style={{ display: "flex", gap: 14, padding: "12px 0", borderBottom: `1px solid ${PAL.line}` }}>
      <div style={{ width: 160, flexShrink: 0, fontSize: 11.5, fontWeight: 600, color: PAL.muted, letterSpacing: ".07em", textTransform: "uppercase" as const, paddingTop: 2 }}>{label}</div>
      <div style={{ fontSize: 13.5, color: PAL.ink }}>{value}</div>
    </div>
  );

  return (
    <div>
      <div className="dash-card" style={{ padding: "8px 22px 18px", marginBottom: 20 }}>
        {row("Nom complet", student.full_name || "—")}
        {row("Email", student.email || "—")}
        {row("Classe(s)", student.classes.length ? student.classes.map(c => c.name).join(", ") : <span style={{ color: PAL.danger }}>Aucune classe assignée</span>)}
        {row("Inscrit le", new Date(student.created_at).toLocaleDateString("fr-FR"))}
        {row("Statut", (
          <span style={{ display: "inline-flex", gap: 10, alignItems: "center" }}>
            <select value={statut} onChange={e => setStatut(e.target.value)} className="u-input"
              style={{ padding: "7px 12px", border: `1px solid ${PAL.line}`, borderRadius: 8, fontFamily: sans, fontSize: 13, color: PAL.ink, background: PAL.paper, outline: "none" }}>
              {Object.entries(STATUT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            {statut !== student.statut && (
              <button onClick={save} disabled={saving} className="btn-c btn-c-sm btn-c-primary">
                {saving ? "…" : "Enregistrer"}
              </button>
            )}
          </span>
        ))}
      </div>

      <div style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".1em", textTransform: "uppercase" as const, color: PAL.muted, marginBottom: 10 }}>
        Fiche administrative
      </div>
      <div className="dash-card" style={{ padding: 22 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "14px 18px" }}>
          {DETAIL_FIELDS.map(f => (
            <div key={f.key} style={f.wide ? { gridColumn: "1 / -1" } : undefined}>
              <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".08em", textTransform: "uppercase" as const, marginBottom: 6 }}>
                {f.label}
              </label>
              <input
                type={f.type ?? "text"}
                value={form[f.key] ?? ""}
                onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                className="u-input"
                style={{ width: "100%", padding: "9px 12px", border: `1px solid ${PAL.line}`, borderRadius: 9, fontFamily: sans, fontSize: 13.5, color: PAL.ink, background: PAL.paper, outline: "none", boxSizing: "border-box" as const }}
              />
            </div>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 18 }}>
          <button
            onClick={saveDetails}
            disabled={savingDetails || !dirty}
            className="btn-c btn-c-primary"
            style={{ opacity: savingDetails || !dirty ? .55 : 1 }}
          >
            {savingDetails ? "Enregistrement…" : "Enregistrer la fiche"}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Page ─── */
function StudentDetailPage() {
  const { studentId } = Route.useParams();
  const [student, setStudent] = useState<StudentDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [tab, setTab] = useState<"profil" | "fichiers" | "documents" | "analyse">("profil");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [showGenerate, setShowGenerate] = useState(false);
  const [docsRefresh, setDocsRefresh] = useState(0);

  async function load() {
    try {
      setStudent(await api.get(`/api/students/${studentId}`));
    } catch {
      setNotFound(true);
    }
  }
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [studentId]);

  if (notFound) {
    return (
      <div style={{ fontFamily: sans }}>
        <EmptyHint icon={<UserRound size={28} strokeWidth={1.7} />} text="Stagiaire introuvable." />
      </div>
    );
  }
  if (!student) {
    return (
      <div className="dash-card" style={{ padding: 26, fontFamily: sans }}>
        <div className="shimmer" style={{ height: 48, width: 48, borderRadius: 999 }} />
        <div className="shimmer" style={{ height: 22, width: "40%", borderRadius: 8, marginTop: 14 }} />
      </div>
    );
  }

  const TABS: { key: typeof tab; label: string }[] = [
    { key: "profil", label: "Profil" },
    { key: "fichiers", label: "Fichiers" },
    { key: "documents", label: "Documents" },
    { key: "analyse", label: "Analyse IA" },
  ];

  return (
    <div style={{ fontFamily: sans }}>
      {preview && <PreviewModal preview={preview} onClose={() => setPreview(null)} />}
      {showGenerate && (
        <GenerateForStudentModal
          student={student}
          onClose={() => setShowGenerate(false)}
          onGenerated={() => setDocsRefresh(v => v + 1)}
          onPreview={setPreview}
        />
      )}

      <Link to="/dashboard/students" style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12.5, color: PAL.muted, textDecoration: "none", marginBottom: 16 }}>
        <ArrowLeft size={14} strokeWidth={1.7} />Stagiaires
      </Link>

      {/* Header card */}
      <div className="dash-card" style={{ padding: 24, marginBottom: 22 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
          {student.photo_url ? (
            <img
              src={student.photo_url}
              alt={student.full_name ?? ""}
              style={{ width: 64, height: 64, borderRadius: 999, objectFit: "cover", flexShrink: 0, border: `1px solid ${PAL.line}` }}
              onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
          ) : (
            <DashAvatar name={student.full_name || student.email || "?"} size={64} tone="primary" />
          )}
          <div style={{ flex: 1, minWidth: 200 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <h1 className="h-serif" style={{ fontSize: 26, lineHeight: 1.1 }}>{student.full_name || "—"}</h1>
              <span className={`chip-c ${student.statut === "actif" ? "chip-c-green" : student.statut === "diplome" ? "" : "chip-c-red"}`}>
                {STATUT_LABEL[student.statut] ?? student.statut}
              </span>
            </div>
            <div style={{ fontSize: 13, color: PAL.muted, marginTop: 5, display: "flex", gap: 14, flexWrap: "wrap" }}>
              <span>{student.email}</span>
              {student.classes.length > 0 && (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                  <IdCard size={13} strokeWidth={1.7} />{student.classes.map(c => c.name).join(", ")}
                </span>
              )}
            </div>
          </div>
          <button type="button" onClick={() => { setShowGenerate(true); }} className="btn-c btn-c-primary">
            <Sparkles size={14} strokeWidth={1.7} />Générer un document
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: "flex", gap: 4, borderBottom: `1px solid ${PAL.line}`, marginBottom: 20 }}>
        {TABS.map(t => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            style={{
              fontFamily: sans, fontSize: 13.5, fontWeight: 600, padding: "10px 16px",
              background: "transparent", border: 0, cursor: "pointer",
              color: tab === t.key ? PAL.primary : PAL.muted,
              borderBottom: tab === t.key ? `2px solid ${PAL.primary}` : "2px solid transparent",
              marginBottom: -1,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "profil" && <ProfilTab student={student} onSaved={load} />}
      {tab === "fichiers" && <FilesTab student={student} onPhotoChanged={load} onPreview={setPreview} />}
      {tab === "documents" && <DocumentsTab student={student} refreshKey={docsRefresh} onPreview={setPreview} />}
      {tab === "analyse" && <AnalyseTab student={student} onApplied={load} />}
    </div>
  );
}
