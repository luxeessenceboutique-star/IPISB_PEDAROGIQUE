import { useEffect, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Bold, Italic, List, Sparkles, Loader2, Check, X } from "lucide-react";

const PAL = { line: "oklch(88% 0.015 170)", muted: "oklch(48% 0.02 180)" };

/** Un champ de texte riche (Tiptap — gras/italique/liste à puces), avec un
 * bouton "IA" qui envoie le contenu actuel + une instruction libre au
 * backend et remplace le contenu par la réponse. Le HTML produit reste
 * volontairement borné (<p>/<strong>/<em>/<ul>/<li>) pour rester
 * convertible en paragraphes Word à l'export — cf.
 * backend/utils/controle_continu_docx.py. */
export function RichTextField({
  label, value, onChange, onAiRewrite, placeholder,
}: {
  label: string;
  value: string;
  onChange: (html: string) => void;
  onAiRewrite: (instruction: string) => Promise<string>;
  placeholder?: string;
}) {
  const editor = useEditor({
    extensions: [StarterKit.configure({ heading: false, codeBlock: false, blockquote: false, horizontalRule: false })],
    content: value || "<p></p>",
    editorProps: {
      attributes: { class: "rtf-content" },
    },
    onUpdate: ({ editor }) => onChange(editor.getHTML()),
  });

  // The assessment can be reloaded (e.g. after a sibling field's AI rewrite
  // round-trips through the backend) — keep the editor in sync when `value`
  // changes from outside rather than only on first mount.
  useEffect(() => {
    if (editor && value !== editor.getHTML()) {
      editor.commands.setContent(value || "<p></p>", { emitUpdate: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const [aiOpen, setAiOpen] = useState(false);
  const [instruction, setInstruction] = useState("");
  const [aiBusy, setAiBusy] = useState(false);

  async function runAi() {
    if (!instruction.trim()) return;
    setAiBusy(true);
    try {
      const html = await onAiRewrite(instruction.trim());
      editor?.commands.setContent(html, { emitUpdate: false });
      onChange(html);
      setAiOpen(false);
      setInstruction("");
    } finally {
      setAiBusy(false);
    }
  }

  if (!editor) return null;

  return (
    <div style={{ border: `1px solid ${PAL.line}`, borderRadius: 10, overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 2, padding: "6px 8px", borderBottom: `1px solid ${PAL.line}`, background: "var(--pal-pale)" }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".06em", textTransform: "uppercase", marginRight: "auto" }}>{label}</span>
        <button type="button" title="Gras" onClick={() => editor.chain().focus().toggleBold().run()}
          className={`rtf-btn${editor.isActive("bold") ? " is-active" : ""}`}><Bold size={13} strokeWidth={2} /></button>
        <button type="button" title="Italique" onClick={() => editor.chain().focus().toggleItalic().run()}
          className={`rtf-btn${editor.isActive("italic") ? " is-active" : ""}`}><Italic size={13} strokeWidth={2} /></button>
        <button type="button" title="Liste à puces" onClick={() => editor.chain().focus().toggleBulletList().run()}
          className={`rtf-btn${editor.isActive("bulletList") ? " is-active" : ""}`}><List size={13} strokeWidth={2} /></button>
        <button type="button" title="Réécrire avec l'IA" onClick={() => setAiOpen(o => !o)}
          className={`rtf-btn${aiOpen ? " is-active" : ""}`} style={{ marginLeft: 4, color: "var(--pal-primary)" }}>
          <Sparkles size={13} strokeWidth={2} />
        </button>
      </div>

      {aiOpen && (
        <div style={{ display: "flex", gap: 6, padding: "8px", borderBottom: `1px solid ${PAL.line}`, background: "var(--pal-pale)" }}>
          <input
            autoFocus
            value={instruction}
            onChange={e => setInstruction(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") runAi(); if (e.key === "Escape") setAiOpen(false); }}
            placeholder="ex. simplifie, ajoute un exemple, reformule plus précisément…"
            className="u-input"
            style={{ flex: 1, padding: "6px 10px", fontSize: 12.5, border: `1px solid ${PAL.line}`, borderRadius: 8, background: "white" }}
          />
          <button type="button" onClick={runAi} disabled={aiBusy || !instruction.trim()} className="rtf-btn" style={{ color: "var(--pal-primary)" }}>
            {aiBusy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} strokeWidth={2} />}
          </button>
          <button type="button" onClick={() => setAiOpen(false)} className="rtf-btn"><X size={14} strokeWidth={2} /></button>
        </div>
      )}

      <EditorContent editor={editor} />
      {!value && placeholder && (
        <div style={{ padding: "0 12px 10px", fontSize: 12, color: PAL.muted, fontStyle: "italic" }}>{placeholder}</div>
      )}
    </div>
  );
}
