import { createFileRoute, redirect, useParams, useNavigate } from "@tanstack/react-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Stage, Layer, Rect, Ellipse, Line as KonvaLine, Text as KonvaText, Image as KonvaImage, Shape as KonvaShape, Transformer } from "react-konva";
import Konva from "konva";
import { supabase } from "@/integrations/supabase/client";
import { api } from "@/lib/api";
import { toast } from "sonner";
import {
  ArrowLeft, Plus, Trash2, Copy, Type, Image as ImageIcon, Bold, Italic,
  AlignLeft, AlignCenter, AlignRight, Undo2, Redo2, Save, Loader2, Check, Eye, Sparkles,
  Square, Circle, Minus, ChevronsUp, ChevronUp, ChevronDown, ChevronsDown, Underline,
} from "lucide-react";
import {
  SlideStatic, STAGE_H, STAGE_W,
  type ShapeEl, type SlideElement, type TextEl, type ViewerSlide,
} from "@/components/dashboard/SlideCanvas";

export const Route = createFileRoute("/dashboard/courses_/$courseId_/editor/$moduleId")({
  beforeLoad: async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) throw redirect({ to: "/auth" });
  },
  component: SlideEditorPage,
});

/* ─── Slide/element model — this IS the source of truth, saved as
   course_lessons.slides (jsonb). Nothing here is ever derived from a
   PDF/PPTX; export (later) reads FROM this, never the other way.

   The M101 template (backend utils/slide_template_m101.py) is expressed
   entirely in these same element types — its pill header, its vertical
   CHAPITRE tab, its footer and its dot trames are ordinary elements the
   teacher can select, restyle or delete like any other. Three fields exist
   specifically so that template can be rendered faithfully rather than
   approximated:
     · cornerRadius — the stadium header, rounded cards, badges
     · opacity      — the watermark canopies and connector lines
     · motif        — a repeating dot grid as ONE element (the cover tiles
                      ~150 dots; that many discrete circles would be
                      "editable" in name only)
   All three are optional, so decks saved before the template shipped load
   unchanged.

   The types themselves live in components/dashboard/SlideCanvas alongside
   the read-only renderer, so the authoring canvas and everything that
   displays its output cannot drift apart. ───────────────────────────── */
type Slide = ViewerSlide;

function uid() {
  return (crypto as any).randomUUID ? crypto.randomUUID() : `id-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function newTextElement(): TextEl {
  return {
    id: uid(), type: "text", x: 80, y: 180, width: 400, height: 80, rotation: 0,
    content: "Nouveau texte", fontSize: 24, fontFamily: "Manrope, sans-serif",
    bold: false, italic: false, underline: false, align: "left", color: "#1C2331", backgroundColor: null,
  };
}
function newShapeElement(shapeType: ShapeEl["shapeType"]): ShapeEl {
  return {
    id: uid(), type: "shape", shapeType, x: 250, y: 150, width: 200, height: 150, rotation: 0,
    fill: shapeType === "line" ? "transparent" : "#DCEEE8", stroke: "#2F6F5E", strokeWidth: shapeType === "line" ? 3 : 2,
  };
}
function newSlide(title: string): Slide {
  return { id: uid(), title, elements: [] };
}

/* ─── Gabarits M101 (spec §12) — each produces REAL, independently editable
   elements (text/shape/motif), never a flattened image. A "photo" slot is a
   labeled placeholder rectangle the teacher deletes and replaces with the
   actual Image button — there's no such thing as an empty <Image> element
   (nothing to render), so a placeholder frame is the honest equivalent.

   The catalogue itself is FETCHED from GET /api/courses/slide-layouts
   rather than declared here: the backend already owns those ~15 layouts
   because generation has to emit them, and maintaining the same
   coordinates a second time in TypeScript would guarantee the two drift.
   A gabarit inserted by hand is therefore byte-for-byte the one generation
   produces. ─────────────────────────────────────────────────────────── */
const HEADING_COLOR = "#2F6F5E";
const BODY_COLOR = "#1C2331";
const MUTED_COLOR = "#6B7280";

type SlideLayout = {
  id: string; name: string; description: string; group: string;
  background: string | null; elements: SlideElement[];
};
// Fixed display order for the picker's sections — the catalogue's own
// `group` values, listed so "Structure" (couverture, sommaire, intros)
// always precedes "Contenu" regardless of payload order.
const GABARIT_GROUPS = ["Structure", "Contenu"] as const;

function tTitle(x: number, y: number, w: number, h: number, content: string, opts: Partial<TextEl> = {}): TextEl {
  return {
    id: uid(), type: "text", x, y, width: w, height: h, rotation: 0, content,
    fontSize: 30, fontFamily: "Manrope, sans-serif", bold: true, italic: false, underline: false,
    align: "left", color: HEADING_COLOR, backgroundColor: null, ...opts,
  };
}
function tBody(x: number, y: number, w: number, h: number, content: string, opts: Partial<TextEl> = {}): TextEl {
  return {
    id: uid(), type: "text", x, y, width: w, height: h, rotation: 0, content,
    fontSize: 18, fontFamily: "Manrope, sans-serif", bold: false, italic: false, underline: false,
    align: "left", color: BODY_COLOR, backgroundColor: null, ...opts,
  };
}
// Phase 7 (spec §17) quick actions — literally the spec's own example
// instructions, one click instead of retyping them every time. The free-text
// box below covers anything not on this list.
const AI_QUICK_ACTIONS: { label: string; instruction: string }[] = [
  { label: "Simplifier", instruction: "Rends ce texte plus simple, avec des mots plus accessibles." },
  { label: "Développer", instruction: "Développe ce texte avec plus de détails et d'explications." },
  { label: "Résumer", instruction: "Résume ce texte en une version plus courte et concise." },
  { label: "Exemple marocain", instruction: "Ajoute un exemple concret ancré dans le contexte marocain." },
  { label: "Niveau débutant", instruction: "Adapte le niveau de ce texte pour des étudiants de première année." },
];


/* ─── Whole-slide AI regeneration — the AI returns role+content pairs,
   NEVER coordinates (asking an LLM for pixel positions invites overlap or
   off-canvas placement), and this lays each role out using the same fixed
   vertical-stack positions the templates above use, so the result is
   always visually sane. Images/shapes already on the slide aren't sent to
   the AI and aren't touched by this — only text gets restructured. ────── */
type AIRoleItem = { role: "title" | "subtitle" | "body" | "bullets"; content: string };
const SLIDE_AI_QUICK_ACTIONS: { label: string; instruction: string }[] = [
  { label: "Simplifier", instruction: "Simplifie et raccourcis le contenu de cette diapositive." },
  { label: "Liste à puces", instruction: "Transforme le contenu de cette diapositive en liste à puces claire." },
  { label: "Transformer en exercice", instruction: "Transforme cette diapositive en exercice pratique pour les stagiaires." },
  { label: "Question de quiz", instruction: "Transforme cette diapositive en question de quiz à choix multiples avec ses réponses." },
];
function layoutRegeneratedText(items: AIRoleItem[]): TextEl[] {
  let y = 35;
  const out: TextEl[] = [];
  for (const item of items) {
    if (item.role === "title") {
      out.push(tTitle(50, y, 700, 55, item.content, { fontSize: 30, align: "left" }));
      y += 65;
    } else if (item.role === "subtitle") {
      out.push(tBody(50, y, 700, 35, item.content, { italic: true, fontSize: 16, color: MUTED_COLOR }));
      y += 45;
    } else {
      const lines = item.content.split("\n").filter(Boolean).length || 1;
      const h = Math.max(50, Math.min(300, lines * 28));
      out.push(tBody(50, y, 700, h, item.content, { fontSize: 18 }));
      y += h + 15;
    }
  }
  return out;
}

const API = import.meta.env.VITE_API_URL ?? "http://localhost:9000";
async function authHeader(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {};
}

/* ─── Editable text overlay — Konva can't edit text in-canvas, the
   documented pattern is to swap in a real <textarea> positioned on top
   while editing, then commit back to state on blur. ────────────────── */
function TextEditOverlay({ el, scale, onCommit, onCancel }: {
  el: TextEl; scale: number; onCommit: (content: string) => void; onCancel: () => void;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { ref.current?.focus(); ref.current?.select(); }, []);
  return (
    <textarea
      ref={ref}
      defaultValue={el.content}
      onBlur={e => onCommit(e.target.value)}
      onKeyDown={e => { if (e.key === "Escape") onCancel(); }}
      style={{
        position: "absolute",
        left: el.x * scale, top: el.y * scale, width: el.width * scale, height: el.height * scale,
        fontSize: el.fontSize * scale, fontFamily: el.fontFamily, fontWeight: el.bold ? 700 : 400,
        fontStyle: el.italic ? "italic" : "normal", textDecoration: el.underline ? "underline" : "none",
        textAlign: el.align, color: el.color,
        background: el.backgroundColor || "transparent", border: "2px solid var(--pal-primary, #2F6F5E)",
        outline: "none", resize: "none", padding: 2, lineHeight: 1.2, zIndex: 20,
      }}
    />
  );
}

function SlideEditorPage() {
  const { courseId, moduleId } = useParams({ from: "/dashboard/courses_/$courseId_/editor/$moduleId" });
  const navigate = useNavigate();

  const [courseTitle, setCourseTitle] = useState("");
  const [moduleTitle, setModuleTitle] = useState("");
  const [lessonId, setLessonId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [slides, setSlides] = useState<Slide[]>([]);
  const [activeSlideId, setActiveSlideId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [editingTextId, setEditingTextId] = useState<string | null>(null);

  const [past, setPast] = useState<Slide[][]>([]);
  const [future, setFuture] = useState<Slide[][]>([]);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [generatingSlides, setGeneratingSlides] = useState(false);
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);
  // Fetched once on mount rather than per-open: it's a static catalogue, and
  // the picker should never show a spinner on a keystroke-fast interaction.
  const [layouts, setLayouts] = useState<SlideLayout[]>([]);
  const [aiEditing, setAiEditing] = useState(false);
  const [aiInstruction, setAiInstruction] = useState("");
  const [showSlideAIPanel, setShowSlideAIPanel] = useState(false);
  const [slideAiInstruction, setSlideAiInstruction] = useState("");
  const [regeneratingSlide, setRegeneratingSlide] = useState(false);

  const stageWrapRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const stageRef = useRef<Konva.Stage>(null);
  const transformerRef = useRef<Konva.Transformer>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const imageCacheRef = useRef<Map<string, HTMLImageElement>>(new Map());
  const [, forceImgLoad] = useState(0);

  /* ── Load ── */
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [courses, modules] = await Promise.all([
          api.get("/api/courses") as Promise<{ id: string; title: string }[]>,
          api.get(`/api/courses/${courseId}/modules`) as Promise<any[]>,
        ]);
        setCourseTitle(courses.find(c => c.id === courseId)?.title ?? "");
        const mod = modules.find(m => m.id === moduleId);
        if (!mod) { toast.error("Chapitre introuvable"); navigate({ to: "/dashboard/courses" }); return; }
        setModuleTitle(mod.title);
        const lesson = mod.lessons?.[0];
        setLessonId(lesson?.id ?? null);
        const loadedSlides: Slide[] = (lesson?.slides && lesson.slides.length > 0) ? lesson.slides : [newSlide("Diapositive 1")];
        setSlides(loadedSlides);
        setActiveSlideId(loadedSlides[0].id);
      } catch (e: any) {
        toast.error(e.message || "Erreur de chargement");
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId, moduleId]);

  /* ── M101 gabarits for the "Ajouter une diapositive" picker. A failure
     here is non-fatal on purpose: the editor still works with blank slides
     and every drawing tool, so a catalogue that won't load costs the
     teacher a shortcut, not their session. ── */
  useEffect(() => {
    api.get("/api/courses/slide-layouts")
      .then(data => setLayouts(data as SlideLayout[]))
      .catch(() => setLayouts([]));
  }, []);

  /* ── Responsive stage scale (design space stays STAGE_W×STAGE_H always) ── */
  useEffect(() => {
    function resize() {
      if (!stageWrapRef.current) return;
      const w = stageWrapRef.current.clientWidth;
      setScale(Math.min(1, w / STAGE_W));
    }
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  const activeSlide = slides.find(s => s.id === activeSlideId) ?? null;
  const selectedEl = activeSlide?.elements.find(e => e.id === selectedId) ?? null;
  const isBlankDeck = slides.length <= 1 && slides.every(s => s.elements.length === 0);

  /* ── History-tracked mutation helper — every real change goes through
     this so undo/redo always has a consistent snapshot to fall back to.
     Deliberately NOT using setSlides(prev => { ...side effects...; return next })
     — React 18 StrictMode double-invokes functional state updaters in dev to
     catch impurities, and an updater that also calls setPast/setFuture/setDirty
     as a side effect gets those side effects fired twice per commit, which
     produced real, hard-to-repro slide/element loss under rapid edits. Reading
     "current" slides from a ref kept in sync via a plain (non-updater) effect
     and issuing one plain setState per piece of state keeps every call pure. ── */
  const slidesRef = useRef<Slide[]>(slides);
  useEffect(() => { slidesRef.current = slides; }, [slides]);

  const commit = useCallback((updater: (prev: Slide[]) => Slide[]) => {
    const prev = slidesRef.current;
    const next = updater(prev);
    setPast(p => [...p, prev]);
    setFuture([]);
    setDirty(true);
    setSlides(next);
    slidesRef.current = next;
  }, []);

  function undo() {
    if (!past.length) return;
    setFuture(f => [slides, ...f]);
    setSlides(past[past.length - 1]);
    setPast(p => p.slice(0, -1));
    setDirty(true);
  }
  function redo() {
    if (!future.length) return;
    setPast(p => [...p, slides]);
    setSlides(future[0]);
    setFuture(f => f.slice(1));
    setDirty(true);
  }

  function updateElement(elId: string, patch: Partial<SlideElement>) {
    commit(prev => prev.map(s => s.id !== activeSlideId ? s : {
      ...s, elements: s.elements.map(e => e.id === elId ? ({ ...e, ...patch } as SlideElement) : e),
    }));
  }
  function addElement(el: SlideElement) {
    commit(prev => prev.map(s => s.id !== activeSlideId ? s : { ...s, elements: [...s.elements, el] }));
    setSelectedId(el.id);
  }
  // Slide-level ground colour. The M101 content gabarits sit on a sage
  // wash and the intro ones on white, so this had to be per-slide rather
  // than a single canvas colour — and, like everything else here, the
  // teacher can override it.
  function setSlideBackground(background: string | null) {
    commit(prev => prev.map(s => s.id !== activeSlideId ? s : { ...s, background }));
  }
  function deleteSelected() {
    if (!selectedId) return;
    commit(prev => prev.map(s => s.id !== activeSlideId ? s : { ...s, elements: s.elements.filter(e => e.id !== selectedId) }));
    setSelectedId(null);
  }

  // Z-order = position in the elements array (later = drawn on top). Applies
  // to any element type, not just shapes — a photo can just as easily need
  // to sit behind a text caption as a rectangle needs to sit behind an icon.
  function reorderElement(elId: string, direction: "front" | "back" | "forward" | "backward") {
    commit(prev => prev.map(s => {
      if (s.id !== activeSlideId) return s;
      const idx = s.elements.findIndex(e => e.id === elId);
      if (idx === -1) return s;
      const arr = [...s.elements];
      const [el] = arr.splice(idx, 1);
      if (direction === "front") arr.push(el);
      else if (direction === "back") arr.unshift(el);
      else if (direction === "forward") arr.splice(Math.min(idx + 1, arr.length), 0, el);
      else arr.splice(Math.max(idx - 1, 0), 0, el);
      return { ...s, elements: arr };
    }));
  }

  function addSlide(layout?: SlideLayout) {
    const s = newSlide(layout ? layout.name : `Diapositive ${slides.length + 1}`);
    if (layout) {
      // Fresh ids per insert — the catalogue is a shared payload, so reusing
      // its ids would give two slides colliding element ids and make the
      // Transformer's #id lookup ambiguous.
      s.elements = layout.elements.map(el => ({ ...el, id: uid() }));
      s.background = layout.background;
    }
    commit(prev => [...prev, s]);
    setActiveSlideId(s.id);
    setSelectedId(null);
    setShowTemplatePicker(false);
  }
  function duplicateSlide(id: string) {
    const src = slides.find(s => s.id === id);
    if (!src) return;
    const copy: Slide = { id: uid(), title: `${src.title} (copie)`, elements: src.elements.map(e => ({ ...e, id: uid() })) };
    const idx = slides.findIndex(s => s.id === id);
    commit(prev => [...prev.slice(0, idx + 1), copy, ...prev.slice(idx + 1)]);
    setActiveSlideId(copy.id);
  }
  function deleteSlide(id: string) {
    if (slides.length <= 1) { toast.error("Le cours doit avoir au moins une diapositive"); return; }
    if (!window.confirm("Supprimer cette diapositive ?")) return;
    commit(prev => prev.filter(s => s.id !== id));
    if (activeSlideId === id) setActiveSlideId(slides.find(s => s.id !== id)?.id ?? null);
  }
  function reorderSlide(fromId: string, toId: string) {
    if (fromId === toId) return;
    commit(prev => {
      const arr = [...prev];
      const fromIdx = arr.findIndex(s => s.id === fromId);
      const toIdx = arr.findIndex(s => s.id === toId);
      const [moved] = arr.splice(fromIdx, 1);
      arr.splice(toIdx, 0, moved);
      return arr;
    });
  }

  async function handleImageUpload(fileList: FileList | null) {
    if (!fileList || fileList.length === 0 || !lessonId) return;
    const file = fileList[0];
    if (fileRef.current) fileRef.current.value = "";
    setUploading(true);
    try {
      const headers = await authHeader();
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/api/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}/images`, { method: "POST", headers, body: form });
      if (!res.ok) throw new Error(await res.text());
      const img = await res.json();
      addElement({ id: uid(), type: "image", x: 200, y: 120, width: 320, height: 220, rotation: 0, src: img.url });
    } catch (e: any) {
      toast.error(e.message || "Échec de l'ajout de l'image");
    } finally {
      setUploading(false);
    }
  }

  // Seeds the deck from the chapter's already-generated text (utils/course_slides.py
  // on the backend) — resolves the "why is this blank" gap: a chapter the AI already
  // wrote gets converted into starter slides instead of forcing the teacher to
  // retype everything by hand. Never silently overwrites an existing hand-built
  // deck — the backend 409s, and we ask before retrying with force=true.
  async function generateSlidesFromContent(force = false) {
    if (!lessonId) return;
    setGeneratingSlides(true);
    try {
      const headers = await authHeader();
      const res = await fetch(
        `${API}/api/courses/${courseId}/modules/${moduleId}/generate-slides${force ? "?force=true" : ""}`,
        { method: "POST", headers },
      );
      if (res.status === 409) {
        const proceed = window.confirm("Ce chapitre a déjà des diapositives. Les remplacer par une nouvelle génération à partir du texte ?");
        if (proceed) await generateSlidesFromContent(true);
        return;
      }
      if (!res.ok) throw new Error(await res.text());
      const data: { slides: Slide[] } = await res.json();
      commit(() => data.slides);
      setActiveSlideId(data.slides[0]?.id ?? null);
      setSelectedId(null);
      toast.success("Diapositives générées à partir du contenu");
    } catch (e: any) {
      toast.error(e.message || "Échec de la génération des diapositives");
    } finally {
      setGeneratingSlides(false);
    }
  }

  // Phase 7 (spec §17) — select a text element, ask AI to modify it. Applies
  // through updateElement() → commit(), so it's just as undoable as any
  // manual edit and nothing is saved to the server until the teacher hits
  // Enregistrer themselves — a bad AI result costs one Ctrl+Z, not a lost chapter.
  async function applyAIEdit(instruction: string) {
    if (!selectedEl || selectedEl.type !== "text" || !instruction.trim()) return;
    setAiEditing(true);
    try {
      const data: { text: string } = await api.post(`/api/courses/${courseId}/ai-edit-text`, {
        text: selectedEl.content, instruction,
      });
      updateElement(selectedEl.id, { content: data.text });
      setAiInstruction("");
      toast.success("Texte modifié par l'IA");
    } catch (e: any) {
      toast.error(e.message || "Échec de la modification IA");
    } finally {
      setAiEditing(false);
    }
  }

  // Whole-slide AI regeneration — unlike applyAIEdit above (rewrites ONE
  // selected text box), this restructures every text block on the active
  // slide at once. Images/shapes on the slide are preserved untouched;
  // only the text elements are replaced, and only in local state — same
  // undo/save story as every other edit here.
  async function regenerateActiveSlide(instruction: string) {
    if (!activeSlide || !instruction.trim()) return;
    setRegeneratingSlide(true);
    try {
      const texts = activeSlide.elements.filter((e): e is TextEl => e.type === "text").map(e => e.content);
      const data: { items: AIRoleItem[] } = await api.post(`/api/courses/${courseId}/ai-regenerate-slide`, {
        texts, instruction,
      });
      const newTextEls = layoutRegeneratedText(data.items);
      const nonTextEls = activeSlide.elements.filter(e => e.type !== "text");
      commit(prev => prev.map(s => s.id !== activeSlideId ? s : { ...s, elements: [...nonTextEls, ...newTextEls] }));
      setSelectedId(null);
      setSlideAiInstruction("");
      setShowSlideAIPanel(false);
      toast.success("Diapositive régénérée par l'IA");
    } catch (e: any) {
      toast.error(e.message || "Échec de la régénération IA");
    } finally {
      setRegeneratingSlide(false);
    }
  }

  async function save() {
    if (!lessonId) return;
    setSaving(true);
    try {
      await api.patch(`/api/courses/${courseId}/modules/${moduleId}/lessons/${lessonId}`, { slides });
      setDirty(false);
      toast.success("Enregistré");
    } catch (e: any) {
      toast.error(e.message || "Échec de l'enregistrement");
    } finally {
      setSaving(false);
    }
  }

  // Opens the SAME course reader students use — not a separate mock preview
  // (spec §20/§31). Saves first if there are pending edits, otherwise the
  // preview would show the last-saved deck, not what's on screen.
  async function previewAsStudent() {
    if (dirty) await save();
    window.open(`/dashboard/courses/${courseId}?chapter=${moduleId}`, "_blank");
  }

  /* ── Keyboard shortcuts ── */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT") return;
      if ((e.key === "Delete" || e.key === "Backspace") && selectedId) { e.preventDefault(); deleteSelected(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !e.shiftKey) { e.preventDefault(); undo(); }
      else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === "y" || (e.key.toLowerCase() === "z" && e.shiftKey))) { e.preventDefault(); redo(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, past, future, slides, lessonId]);

  /* ── Attach transformer to the selected node ── */
  useEffect(() => {
    if (!transformerRef.current || !stageRef.current) return;
    const node = selectedId ? stageRef.current.findOne(`#${selectedId}`) : null;
    transformerRef.current.nodes(node ? [node] : []);
    transformerRef.current.getLayer()?.batchDraw();
  }, [selectedId, activeSlideId, slides]);

  /* ── Preload images referenced on this slide ── */
  useEffect(() => {
    (activeSlide?.elements || []).forEach(el => {
      if (el.type !== "image" || imageCacheRef.current.has(el.src)) return;
      const img = new window.Image();
      img.crossOrigin = "anonymous";
      img.src = el.src;
      img.onload = () => { imageCacheRef.current.set(el.src, img); forceImgLoad(n => n + 1); };
    });
  }, [activeSlide]);

  function onTransformEnd(elId: string, node: Konva.Node) {
    const scaleX = node.scaleX(), scaleY = node.scaleY();
    node.scaleX(1); node.scaleY(1);
    const current = activeSlide?.elements.find(e => e.id === elId);
    if (!current) return;
    updateElement(elId, {
      x: node.x(), y: node.y(), rotation: node.rotation(),
      width: Math.max(20, current.width * scaleX), height: Math.max(20, current.height * scaleY),
    });
  }

  // Konva's Ellipse is center-anchored (x/y = center, radiusX/radiusY) while
  // every other element here is top-left-anchored (x/y/width/height) so the
  // Transformer's default resize math applies uniformly — this converts back
  // and forth at just this one boundary rather than special-casing storage.
  function onEllipseTransformEnd(elId: string, node: Konva.Node) {
    const scaleX = node.scaleX(), scaleY = node.scaleY();
    node.scaleX(1); node.scaleY(1);
    const current = activeSlide?.elements.find(e => e.id === elId);
    if (!current) return;
    const width = Math.max(20, current.width * scaleX);
    const height = Math.max(20, current.height * scaleY);
    updateElement(elId, { x: node.x() - width / 2, y: node.y() - height / 2, rotation: node.rotation(), width, height });
  }

  if (loading) {
    return <div className="flex justify-center py-24"><Loader2 className="h-6 w-6 animate-spin text-muted-foreground" /></div>;
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-background">
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-border shrink-0 bg-card">
        <div className="flex items-center gap-3 min-w-0">
          <button onClick={() => navigate({ to: "/dashboard/courses" })} className="rounded-full p-1.5 hover:bg-muted transition-colors shrink-0" title="Retour">
            <ArrowLeft className="h-4 w-4" />
          </button>
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground truncate">{courseTitle}</p>
            <p className="text-sm font-semibold truncate">{moduleTitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <button onClick={undo} disabled={!past.length} className="btn-c btn-c-ghost btn-c-sm" title="Annuler (Ctrl+Z)"><Undo2 className="h-4 w-4" /></button>
          <button onClick={redo} disabled={!future.length} className="btn-c btn-c-ghost btn-c-sm" title="Rétablir (Ctrl+Y)"><Redo2 className="h-4 w-4" /></button>
          <div className="w-px h-5 bg-border mx-1" />
          <span className="text-xs text-muted-foreground flex items-center gap-1">
            {saving ? <><Loader2 className="h-3 w-3 animate-spin" />Enregistrement…</> : dirty ? "Modifications non enregistrées" : <><Check className="h-3 w-3 text-green-600" />Enregistré</>}
          </span>
          <button onClick={save} disabled={saving || !dirty} className="btn-c btn-c-primary btn-c-sm">
            <Save className="h-3.5 w-3.5 mr-1.5" />Enregistrer
          </button>
          <div className="w-px h-5 bg-border mx-1" />
          <button onClick={previewAsStudent} disabled={saving} className="btn-c btn-c-soft btn-c-sm" title="Ouvre la page que verrait un étudiant">
            <Eye className="h-3.5 w-3.5 mr-1.5" />Aperçu élève
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Slide list */}
        <div className="w-48 border-r border-border overflow-y-auto p-2 space-y-2 shrink-0 bg-muted/20">
          {slides.map((s, i) => (
            <div
              key={s.id}
              draggable
              onDragStart={e => e.dataTransfer.setData("text/slide-id", s.id)}
              onDragOver={e => e.preventDefault()}
              onDrop={e => { e.preventDefault(); reorderSlide(e.dataTransfer.getData("text/slide-id"), s.id); }}
              onClick={() => { setActiveSlideId(s.id); setSelectedId(null); }}
              className="rounded-lg border-2 p-2 cursor-pointer transition-colors bg-card"
              style={{ borderColor: s.id === activeSlideId ? "var(--pal-primary, #2F6F5E)" : "var(--pal-line-soft, #e2e2e2)" }}
            >
              {s.elements.length === 0 ? (
                <div className="aspect-video rounded bg-white border border-border/60 flex items-center justify-center text-[10px] text-muted-foreground">Vide</div>
              ) : (
                <SlideStatic slide={s} className="rounded border border-border/60" />
              )}
              <div className="flex items-center justify-between mt-1.5">
                <span className="text-[11px] font-medium truncate flex-1">{i + 1}. {s.title}</span>
                <div className="flex items-center gap-0.5 shrink-0">
                  <button onClick={e => { e.stopPropagation(); duplicateSlide(s.id); }} className="h-5 w-5 flex items-center justify-center rounded hover:bg-muted" title="Dupliquer"><Copy className="h-3 w-3" /></button>
                  <button onClick={e => { e.stopPropagation(); deleteSlide(s.id); }} className="h-5 w-5 flex items-center justify-center rounded hover:bg-destructive/10 text-destructive" title="Supprimer"><Trash2 className="h-3 w-3" /></button>
                </div>
              </div>
            </div>
          ))}
          <button onClick={() => setShowTemplatePicker(true)} className="w-full rounded-lg border-2 border-dashed border-border py-2.5 text-xs font-semibold text-muted-foreground hover:border-primary/60 hover:text-foreground transition-colors flex items-center justify-center gap-1.5">
            <Plus className="h-3.5 w-3.5" />Ajouter une diapositive
          </button>
        </div>

        {showTemplatePicker && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40" onClick={() => setShowTemplatePicker(false)}>
            <div className="bg-card rounded-xl border border-border shadow-xl w-full max-w-2xl max-h-[80vh] overflow-y-auto p-5" onClick={e => e.stopPropagation()}>
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-display text-lg font-semibold">Choisir un modèle de diapositive</h3>
                <button onClick={() => setShowTemplatePicker(false)} className="rounded-full p-1.5 hover:bg-muted transition-colors" title="Fermer">✕</button>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <button
                  onClick={() => addSlide()}
                  className="rounded-lg border-2 border-dashed border-border p-3 text-left hover:border-primary/60 transition-colors"
                >
                  <div className="aspect-video rounded bg-muted/50 mb-2 flex items-center justify-center text-muted-foreground"><Plus className="h-5 w-5" /></div>
                  <p className="text-xs font-semibold">Vierge</p>
                  <p className="text-[11px] text-muted-foreground">Diapositive vide</p>
                </button>
              </div>
              {layouts.length === 0 && (
                <p className="text-xs text-muted-foreground mt-4">Chargement des gabarits…</p>
              )}
              {GABARIT_GROUPS.map(group => {
                const inGroup = layouts.filter(l => l.group === group);
                if (!inGroup.length) return null;
                return (
                  <div key={group} className="mt-5">
                    <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide mb-2">{group}</p>
                    <div className="grid grid-cols-3 gap-3">
                      {inGroup.map(l => (
                        <button
                          key={l.id}
                          onClick={() => addSlide(l)}
                          className="rounded-lg border-2 border-border p-3 text-left hover:border-primary/60 transition-colors bg-white"
                        >
                          <SlideStatic slide={l} className="rounded border border-border/60 mb-2" />
                          <p className="text-xs font-semibold">{l.name}</p>
                          <p className="text-[11px] text-muted-foreground">{l.description}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Canvas */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center gap-2 px-4 py-2 border-b border-border shrink-0">
            <button onClick={() => addElement(newTextElement())} className="btn-c btn-c-soft btn-c-sm"><Type className="h-3.5 w-3.5 mr-1.5" />Texte</button>
            <label className="cursor-pointer">
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={e => handleImageUpload(e.target.files)} />
              <span className="btn-c btn-c-soft btn-c-sm inline-flex items-center">
                {uploading ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5 mr-1.5" />}Image
              </span>
            </label>
            <div className="flex items-center gap-1 border-l border-border pl-2 ml-0.5">
              <button onClick={() => addElement(newShapeElement("rectangle"))} className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-muted transition-colors" title="Rectangle"><Square className="h-3.5 w-3.5" /></button>
              <button onClick={() => addElement(newShapeElement("circle"))} className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-muted transition-colors" title="Cercle"><Circle className="h-3.5 w-3.5" /></button>
              <button onClick={() => addElement(newShapeElement("line"))} className="h-7 w-7 flex items-center justify-center rounded-md hover:bg-muted transition-colors" title="Ligne"><Minus className="h-3.5 w-3.5" /></button>
            </div>
            {selectedId && (
              <button onClick={deleteSelected} className="btn-c btn-c-ghost btn-c-sm text-destructive"><Trash2 className="h-3.5 w-3.5 mr-1.5" />Supprimer l'élément</button>
            )}
            <div className="flex-1" />
            <div className="relative">
              <button onClick={() => setShowSlideAIPanel(v => !v)} disabled={!activeSlide} className="btn-c btn-c-ghost btn-c-sm" title="Restructurer tout le texte de cette diapositive avec l'IA">
                <Sparkles className="h-3.5 w-3.5 mr-1.5" />Régénérer la diapositive
              </button>
              {showSlideAIPanel && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowSlideAIPanel(false)} />
                  <div className="absolute right-0 top-full mt-2 z-50 w-80 bg-card border border-border rounded-lg shadow-xl p-3 space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Régénérer avec l'IA</p>
                    <div className="flex flex-wrap gap-1.5">
                      {SLIDE_AI_QUICK_ACTIONS.map(a => (
                        <button
                          key={a.label} disabled={regeneratingSlide} onClick={() => regenerateActiveSlide(a.instruction)}
                          className="text-[11px] px-2 py-1 rounded-full border border-border hover:border-primary/60 hover:text-primary transition-colors disabled:opacity-50"
                        >
                          {a.label}
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-1.5">
                      <input
                        type="text" value={slideAiInstruction} onChange={e => setSlideAiInstruction(e.target.value)}
                        placeholder="Instruction personnalisée…"
                        onKeyDown={e => { if (e.key === "Enter" && slideAiInstruction.trim()) regenerateActiveSlide(slideAiInstruction); }}
                        className="flex-1 h-8 rounded-md border border-border px-2 text-xs"
                      />
                      <button
                        onClick={() => regenerateActiveSlide(slideAiInstruction)} disabled={regeneratingSlide || !slideAiInstruction.trim()}
                        className="btn-c btn-c-primary btn-c-sm shrink-0 px-2.5"
                      >
                        {regeneratingSlide ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                    <p className="text-[11px] text-muted-foreground italic">Remplace tout le texte de cette diapositive. Images et formes restent inchangées.</p>
                  </div>
                </>
              )}
            </div>
            <button onClick={() => generateSlidesFromContent(false)} disabled={generatingSlides} className="btn-c btn-c-ghost btn-c-sm" title="Créer des diapositives à partir du contenu déjà rédigé pour ce chapitre">
              {generatingSlides ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 mr-1.5" />}Générer depuis le texte
            </button>
          </div>

          {isBlankDeck && (
            <div className="mx-4 mt-3 rounded-lg border border-dashed border-primary/40 bg-primary/5 px-4 py-3 flex items-center justify-between gap-3">
              <p className="text-xs text-muted-foreground">
                Ce chapitre a peut-être déjà du contenu généré par l'IA — créez les diapositives à partir de ce texte plutôt que de repartir de zéro.
              </p>
              <button onClick={() => generateSlidesFromContent(false)} disabled={generatingSlides} className="btn-c btn-c-primary btn-c-sm shrink-0">
                {generatingSlides ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5 mr-1.5" />}Générer
              </button>
            </div>
          )}

          <div ref={stageWrapRef} className="flex-1 overflow-auto flex items-start justify-center p-6 bg-muted/30 relative">
            <div style={{ position: "relative", width: STAGE_W * scale, height: STAGE_H * scale }}>
              <Stage
                ref={stageRef}
                width={STAGE_W * scale}
                height={STAGE_H * scale}
                scale={{ x: scale, y: scale }}
                onMouseDown={e => { if (e.target === e.target.getStage()) setSelectedId(null); }}
                style={{ background: "white", boxShadow: "0 2px 16px rgba(0,0,0,0.12)" }}
              >
                <Layer>
                  <Rect x={0} y={0} width={STAGE_W} height={STAGE_H} fill={activeSlide?.background || "#ffffff"} />
                  {activeSlide?.elements.map(el => {
                    if (el.type === "motif") {
                      // Drawn with a sceneFunc rather than as N circles so the
                      // whole trame stays one selectable, resizable element.
                      return (
                        <KonvaShape
                          key={el.id} id={el.id}
                          x={el.x} y={el.y} width={el.width} height={el.height} rotation={el.rotation}
                          opacity={el.opacity ?? 1} draggable
                          sceneFunc={(ctx, shape) => {
                            const w = shape.width(), h = shape.height(), r = el.dotSize / 2;
                            ctx.beginPath();
                            for (let y = r; y <= h - r; y += el.gap) {
                              for (let x = r; x <= w - r; x += el.gap) {
                                ctx.moveTo(x + r, y);
                                ctx.arc(x, y, r, 0, Math.PI * 2);
                              }
                            }
                            ctx.closePath();
                            ctx.fillStrokeShape(shape);
                          }}
                          fill={el.color}
                          // Without a hit region a sceneFunc shape is only
                          // clickable on the dots themselves — a 3px target.
                          hitFunc={(ctx, shape) => {
                            ctx.beginPath();
                            ctx.rect(0, 0, shape.width(), shape.height());
                            ctx.closePath();
                            ctx.fillStrokeShape(shape);
                          }}
                          onClick={() => setSelectedId(el.id)} onTap={() => setSelectedId(el.id)}
                          onDragEnd={e => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                          onTransformEnd={e => onTransformEnd(el.id, e.target)}
                        />
                      );
                    }
                    if (el.type === "text") {
                      return (
                        <KonvaText
                          key={el.id} id={el.id}
                          x={el.x} y={el.y} width={el.width} height={el.height} rotation={el.rotation}
                          text={el.content} fontSize={el.fontSize} fontFamily={el.fontFamily}
                          fontStyle={`${el.bold ? "bold" : ""} ${el.italic ? "italic" : ""}`.trim() || "normal"}
                          textDecoration={el.underline ? "underline" : ""}
                          align={el.align} fill={el.color}
                          draggable
                          onClick={() => setSelectedId(el.id)} onTap={() => setSelectedId(el.id)}
                          onDblClick={() => setEditingTextId(el.id)} onDblTap={() => setEditingTextId(el.id)}
                          onDragEnd={e => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                          onTransformEnd={e => onTransformEnd(el.id, e.target)}
                        />
                      );
                    }
                    if (el.type === "shape") {
                      const commonProps = {
                        key: el.id, id: el.id, draggable: true, opacity: el.opacity ?? 1,
                        onClick: () => setSelectedId(el.id), onTap: () => setSelectedId(el.id),
                      };
                      if (el.shapeType === "circle") {
                        return (
                          <Ellipse
                            {...commonProps}
                            x={el.x + el.width / 2} y={el.y + el.height / 2}
                            radiusX={el.width / 2} radiusY={el.height / 2} rotation={el.rotation}
                            fill={el.fill} stroke={el.stroke} strokeWidth={el.strokeWidth}
                            onDragEnd={e => updateElement(el.id, { x: e.target.x() - el.width / 2, y: e.target.y() - el.height / 2 })}
                            onTransformEnd={e => onEllipseTransformEnd(el.id, e.target)}
                          />
                        );
                      }
                      if (el.shapeType === "line") {
                        return (
                          <KonvaLine
                            {...commonProps}
                            x={el.x} y={el.y} rotation={el.rotation}
                            points={[0, 0, el.width, el.height]}
                            stroke={el.stroke} strokeWidth={el.strokeWidth}
                            onDragEnd={e => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                            onTransformEnd={e => onTransformEnd(el.id, e.target)}
                          />
                        );
                      }
                      return (
                        <Rect
                          {...commonProps}
                          x={el.x} y={el.y} width={el.width} height={el.height} rotation={el.rotation}
                          fill={el.fill} stroke={el.stroke} strokeWidth={el.strokeWidth}
                          cornerRadius={el.cornerRadius ?? 0}
                          onDragEnd={e => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                          onTransformEnd={e => onTransformEnd(el.id, e.target)}
                        />
                      );
                    }
                    const img = imageCacheRef.current.get(el.src);
                    return (
                      <KonvaImage
                        key={el.id} id={el.id}
                        x={el.x} y={el.y} width={el.width} height={el.height} rotation={el.rotation}
                        image={img} draggable opacity={el.opacity ?? 1}
                        onClick={() => setSelectedId(el.id)} onTap={() => setSelectedId(el.id)}
                        onDragEnd={e => updateElement(el.id, { x: e.target.x(), y: e.target.y() })}
                        onTransformEnd={e => onTransformEnd(el.id, e.target)}
                      />
                    );
                  })}
                  <Transformer ref={transformerRef} keepRatio={selectedEl?.type === "image"} boundBoxFunc={(_old, next) => (next.width < 20 || next.height < 20 ? _old : next)} />
                </Layer>
              </Stage>
              {editingTextId && activeSlide && (() => {
                const el = activeSlide.elements.find(e => e.id === editingTextId) as TextEl | undefined;
                if (!el) return null;
                return (
                  <TextEditOverlay
                    el={el} scale={scale}
                    onCommit={content => { updateElement(el.id, { content }); setEditingTextId(null); }}
                    onCancel={() => setEditingTextId(null)}
                  />
                );
              })()}
            </div>
          </div>
        </div>

        {/* Properties panel */}
        <div className="w-64 border-l border-border overflow-y-auto p-3 space-y-3 shrink-0 bg-muted/20">
          {activeSlide && (
            <div className="space-y-2 pb-3 border-b border-border/60">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Diapositive</p>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Nom</span>
                <input
                  type="text" value={activeSlide.title}
                  onChange={e => commit(prev => prev.map(s => s.id !== activeSlideId ? s : { ...s, title: e.target.value }))}
                  className="w-full h-8 rounded-md border border-border px-2 text-xs"
                />
              </label>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Couleur de fond</span>
                <input type="color" value={activeSlide.background || "#ffffff"}
                  onChange={e => setSlideBackground(e.target.value)}
                  className="w-full h-8 rounded-md border border-border" />
              </label>
            </div>
          )}

          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Propriétés</p>
          {!selectedEl ? (
            <p className="text-xs text-muted-foreground">Sélectionnez un élément pour le modifier.</p>
          ) : selectedEl.type === "text" ? (
            <div className="space-y-3">
              <div className="flex gap-1.5">
                <button onClick={() => updateElement(selectedEl.id, { bold: !selectedEl.bold })} className={`btn-c btn-c-sm flex-1 ${selectedEl.bold ? "btn-c-primary" : "btn-c-ghost"}`}><Bold className="h-3.5 w-3.5" /></button>
                <button onClick={() => updateElement(selectedEl.id, { italic: !selectedEl.italic })} className={`btn-c btn-c-sm flex-1 ${selectedEl.italic ? "btn-c-primary" : "btn-c-ghost"}`}><Italic className="h-3.5 w-3.5" /></button>
                <button onClick={() => updateElement(selectedEl.id, { underline: !selectedEl.underline })} className={`btn-c btn-c-sm flex-1 ${selectedEl.underline ? "btn-c-primary" : "btn-c-ghost"}`}><Underline className="h-3.5 w-3.5" /></button>
              </div>
              <div className="flex gap-1.5">
                {(["left", "center", "right"] as const).map(a => (
                  <button key={a} onClick={() => updateElement(selectedEl.id, { align: a })} className={`btn-c btn-c-sm flex-1 ${selectedEl.align === a ? "btn-c-primary" : "btn-c-ghost"}`}>
                    {a === "left" ? <AlignLeft className="h-3.5 w-3.5" /> : a === "center" ? <AlignCenter className="h-3.5 w-3.5" /> : <AlignRight className="h-3.5 w-3.5" />}
                  </button>
                ))}
              </div>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Taille de police</span>
                <input type="number" min={8} max={120} value={selectedEl.fontSize}
                  onChange={e => updateElement(selectedEl.id, { fontSize: Number(e.target.value) || 12 })}
                  className="w-full h-8 rounded-md border border-border px-2 text-xs" />
              </label>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Couleur du texte</span>
                <input type="color" value={selectedEl.color} onChange={e => updateElement(selectedEl.id, { color: e.target.value })} className="w-full h-8 rounded-md border border-border" />
              </label>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                <input type="checkbox" checked={!!selectedEl.backgroundColor} onChange={e => updateElement(selectedEl.id, { backgroundColor: e.target.checked ? "#FFF7D6" : null })} />
                Fond coloré
              </label>
              {selectedEl.backgroundColor && (
                <input type="color" value={selectedEl.backgroundColor} onChange={e => updateElement(selectedEl.id, { backgroundColor: e.target.value })} className="w-full h-8 rounded-md border border-border" />
              )}
              <p className="text-[11px] text-muted-foreground italic">Double-cliquez sur le texte dans la diapositive pour le modifier.</p>

              <div className="pt-3 border-t border-border/60 space-y-2">
                <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
                  <Sparkles className="h-3 w-3" />Modifier avec l'IA
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {AI_QUICK_ACTIONS.map(a => (
                    <button
                      key={a.label} disabled={aiEditing} onClick={() => applyAIEdit(a.instruction)}
                      className="text-[11px] px-2 py-1 rounded-full border border-border hover:border-primary/60 hover:text-primary transition-colors disabled:opacity-50"
                    >
                      {a.label}
                    </button>
                  ))}
                </div>
                <div className="flex gap-1.5">
                  <input
                    type="text" value={aiInstruction} onChange={e => setAiInstruction(e.target.value)}
                    placeholder="Instruction personnalisée…"
                    onKeyDown={e => { if (e.key === "Enter" && aiInstruction.trim()) applyAIEdit(aiInstruction); }}
                    className="flex-1 h-8 rounded-md border border-border px-2 text-xs"
                  />
                  <button
                    onClick={() => applyAIEdit(aiInstruction)} disabled={aiEditing || !aiInstruction.trim()}
                    className="btn-c btn-c-primary btn-c-sm shrink-0 px-2.5"
                  >
                    {aiEditing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                  </button>
                </div>
              </div>
            </div>
          ) : selectedEl.type === "image" ? (
            <div className="space-y-2">
              <img src={selectedEl.src} alt="" className="w-full rounded-md border border-border" />
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Opacité — {Math.round((selectedEl.opacity ?? 1) * 100)} %</span>
                <input type="range" min={0} max={100} value={Math.round((selectedEl.opacity ?? 1) * 100)}
                  onChange={e => updateElement(selectedEl.id, { opacity: Number(e.target.value) / 100 })}
                  className="w-full" />
              </label>
              <p className="text-[11px] text-muted-foreground">Glissez pour déplacer, tirez les poignées pour redimensionner (proportions conservées).</p>
            </div>
          ) : selectedEl.type === "motif" ? (
            /* Trame de points — un seul élément, entièrement paramétrable
               (le gabarit M101 en pose sur la couverture). */
            <div className="space-y-3">
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Couleur des points</span>
                <input type="color" value={selectedEl.color} onChange={e => updateElement(selectedEl.id, { color: e.target.value })} className="w-full h-8 rounded-md border border-border" />
              </label>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Taille des points</span>
                <input type="number" min={1} max={20} step={0.5} value={selectedEl.dotSize}
                  onChange={e => updateElement(selectedEl.id, { dotSize: Number(e.target.value) || 1 })}
                  className="w-full h-8 rounded-md border border-border px-2 text-xs" />
              </label>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Espacement</span>
                <input type="number" min={4} max={80} value={selectedEl.gap}
                  onChange={e => updateElement(selectedEl.id, { gap: Number(e.target.value) || 4 })}
                  className="w-full h-8 rounded-md border border-border px-2 text-xs" />
              </label>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Opacité — {Math.round((selectedEl.opacity ?? 1) * 100)} %</span>
                <input type="range" min={0} max={100} value={Math.round((selectedEl.opacity ?? 1) * 100)}
                  onChange={e => updateElement(selectedEl.id, { opacity: Number(e.target.value) / 100 })}
                  className="w-full" />
              </label>
            </div>
          ) : (
            <div className="space-y-3">
              {selectedEl.shapeType !== "line" && (
                <label className="block text-xs text-muted-foreground space-y-1">
                  <span>Couleur de remplissage</span>
                  <input type="color" value={selectedEl.fill} onChange={e => updateElement(selectedEl.id, { fill: e.target.value })} className="w-full h-8 rounded-md border border-border" />
                </label>
              )}
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Couleur du contour</span>
                <input type="color" value={selectedEl.stroke} onChange={e => updateElement(selectedEl.id, { stroke: e.target.value })} className="w-full h-8 rounded-md border border-border" />
              </label>
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Épaisseur du contour</span>
                <input type="number" min={0} max={20} value={selectedEl.strokeWidth}
                  onChange={e => updateElement(selectedEl.id, { strokeWidth: Number(e.target.value) || 0 })}
                  className="w-full h-8 rounded-md border border-border px-2 text-xs" />
              </label>
              {selectedEl.shapeType === "rectangle" && (
                <label className="block text-xs text-muted-foreground space-y-1">
                  <span>Coins arrondis</span>
                  <input type="number" min={0} max={200} value={selectedEl.cornerRadius ?? 0}
                    onChange={e => updateElement(selectedEl.id, { cornerRadius: Number(e.target.value) || 0 })}
                    className="w-full h-8 rounded-md border border-border px-2 text-xs" />
                </label>
              )}
              <label className="block text-xs text-muted-foreground space-y-1">
                <span>Opacité — {Math.round((selectedEl.opacity ?? 1) * 100)} %</span>
                <input type="range" min={0} max={100} value={Math.round((selectedEl.opacity ?? 1) * 100)}
                  onChange={e => updateElement(selectedEl.id, { opacity: Number(e.target.value) / 100 })}
                  className="w-full" />
              </label>
            </div>
          )}

          {selectedEl && (
            <div className="pt-3 border-t border-border/60 space-y-1.5">
              <p className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wide">Calques</p>
              <div className="grid grid-cols-4 gap-1.5">
                <button onClick={() => reorderElement(selectedEl.id, "front")} className="btn-c btn-c-ghost btn-c-sm" title="Mettre au premier plan"><ChevronsUp className="h-3.5 w-3.5" /></button>
                <button onClick={() => reorderElement(selectedEl.id, "forward")} className="btn-c btn-c-ghost btn-c-sm" title="Avancer"><ChevronUp className="h-3.5 w-3.5" /></button>
                <button onClick={() => reorderElement(selectedEl.id, "backward")} className="btn-c btn-c-ghost btn-c-sm" title="Reculer"><ChevronDown className="h-3.5 w-3.5" /></button>
                <button onClick={() => reorderElement(selectedEl.id, "back")} className="btn-c btn-c-ghost btn-c-sm" title="Mettre à l'arrière-plan"><ChevronsDown className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
