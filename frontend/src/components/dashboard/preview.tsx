/**
 * Shared document preview modal — used by the Documents page and the
 * student detail page. PDFs render inline in an iframe; .docx files are
 * rendered client-side by docx-preview (browsers have no native viewer);
 * anything else falls back to a download link.
 */
import { useEffect, useRef, useState } from "react";
import { Download, ExternalLink, FileText, Loader2, X } from "lucide-react";

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  muted:   "oklch(48% 0.02 180)",
  primary: "oklch(48% 0.085 175)",
  line:    "oklch(88% 0.015 170)",
  paper:   "oklch(99% 0.005 160)",
};
const sans = '"Manrope", system-ui, sans-serif';

export type Preview = { url: string; title: string; isPdf: boolean };

/** Extension of a signed URL — `.../documents/<code>.pdf?token=…` keeps the
 * extension in the path, before the query string. */
function urlExt(url: string): string {
  return (url.split("?")[0].split(".").pop() ?? "").toLowerCase();
}

export function urlIsPdf(url: string): boolean {
  return urlExt(url) === "pdf";
}

export function urlIsDocx(url: string): boolean {
  return urlExt(url) === "docx";
}

export function urlIsImage(url: string): boolean {
  return ["jpg", "jpeg", "png"].includes(urlExt(url));
}

export function urlIsInlineViewable(url: string): boolean {
  return urlIsPdf(url) || urlIsDocx(url) || urlIsImage(url);
}

/** Renders a .docx into real HTML in the browser — same pages, fonts, tables
 * and borders as Word, no server-side conversion and no download detour. */
function DocxView({ url }: { url: string }) {
  const host = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    let cancelled = false;
    setState("loading");

    (async () => {
      try {
        const [{ renderAsync }, res] = await Promise.all([
          import("docx-preview"),
          fetch(url),
        ]);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (cancelled || !host.current) return;
        host.current.innerHTML = "";
        await renderAsync(blob, host.current, undefined, {
          className: "docx",
          inWrapper: true,
          breakPages: true,
          renderHeaders: true,
          renderFooters: true,
          // Signed-URL blobs can outlive the modal; base64 keeps embedded
          // images (the IPISB logo) alive without leaking object URLs.
          useBase64URL: true,
        });
        if (!cancelled) setState("ready");
      } catch {
        if (!cancelled) setState("error");
      }
    })();

    return () => { cancelled = true; };
  }, [url]);

  return (
    <div style={{ flex: 1, overflow: "auto", background: "oklch(93% 0.008 180)", padding: 16 }}>
      {state === "loading" && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, padding: "48px 0", fontFamily: sans, fontSize: 13, color: PAL.muted }}>
          <Loader2 size={15} strokeWidth={1.7} className="animate-spin" />
          Chargement de l'aperçu…
        </div>
      )}
      {state === "error" && (
        <div style={{ padding: "48px 24px", textAlign: "center", fontFamily: sans, fontSize: 13, color: PAL.muted }}>
          Impossible d'afficher l'aperçu de ce document.
        </div>
      )}
      {/* Kept mounted while loading — renderAsync needs the node to exist. */}
      <div ref={host} style={{ display: state === "ready" ? "block" : "none" }} />
    </div>
  );
}

export function PreviewModal({ preview, onClose }: { preview: Preview; onClose: () => void }) {
  const isDocx = urlIsDocx(preview.url);
  const isImage = urlIsImage(preview.url);
  const fullHeight = preview.isPdf || isDocx;

  return (
    <div className="anim-fade" style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.55)", zIndex: 300, display: "flex", alignItems: "center", justifyContent: "center", backdropFilter: "blur(3px)", padding: 16 }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="anim-pop" style={{ background: PAL.paper, borderRadius: 16, width: "min(920px, 96vw)", height: fullHeight ? "min(88vh, 1100px)" : "auto", display: "flex", flexDirection: "column", boxShadow: "0 24px 60px rgba(0,0,0,.25)", overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 18px", borderBottom: `1px solid ${PAL.line}` }}>
          <FileText size={17} strokeWidth={1.7} style={{ color: PAL.primary, flexShrink: 0 }} />
          <div style={{ fontFamily: sans, fontWeight: 700, fontSize: 14, color: PAL.ink, flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {preview.title}
          </div>
          {isDocx && (
            <a href={preview.url} download title="Télécharger" style={{ color: PAL.muted, display: "flex", padding: 6 }}>
              <Download size={15} strokeWidth={1.7} />
            </a>
          )}
          <a href={preview.url} target="_blank" rel="noreferrer" title="Ouvrir dans un onglet" style={{ color: PAL.muted, display: "flex", padding: 6 }}>
            <ExternalLink size={15} strokeWidth={1.7} />
          </a>
          <button type="button" onClick={onClose} aria-label="Fermer" style={{ background: "transparent", border: 0, color: PAL.muted, cursor: "pointer", display: "flex", padding: 6 }}>
            <X size={17} strokeWidth={1.7} />
          </button>
        </div>
        {preview.isPdf ? (
          <iframe src={preview.url} title={preview.title} style={{ flex: 1, width: "100%", border: 0, background: "#525659" }} />
        ) : isDocx ? (
          <DocxView url={preview.url} />
        ) : isImage ? (
          <div style={{ background: "oklch(93% 0.008 180)", padding: 16, display: "flex", justifyContent: "center" }}>
            <img src={preview.url} alt={preview.title} style={{ maxWidth: "100%", maxHeight: "72vh", objectFit: "contain", borderRadius: 8 }} />
          </div>
        ) : (
          <div style={{ padding: "36px 24px", textAlign: "center", fontFamily: sans, fontSize: 13, color: PAL.muted }}>
            L'aperçu intégré n'est pas disponible pour ce format.
            <div style={{ marginTop: 14 }}>
              <a href={preview.url} target="_blank" rel="noreferrer" className="btn-c btn-c-primary btn-c-sm" style={{ textDecoration: "none" }}>
                <Download size={13} strokeWidth={1.7} />Télécharger le document
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
