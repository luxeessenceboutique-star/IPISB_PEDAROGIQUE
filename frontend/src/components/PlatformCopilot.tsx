import { useEffect, useRef, useState } from "react";
import { useBreakpoint } from "@/lib/useBreakpoint";
import { useAuth } from "@/lib/auth";
import { supabase } from "@/integrations/supabase/client";
import { Sparkles, X, Send, ChevronDown } from "lucide-react";

const API = import.meta.env.VITE_API_URL ?? "http://localhost:9000";
const sans = '"Manrope", system-ui, sans-serif';

type Lang = "fr" | "ar" | "en" | "darija";
interface Msg { role: "user" | "assistant"; content: string }

const LANGS: { code: Lang; flag: string; label: string; rtl: boolean }[] = [
  { code: "fr", flag: "🇫🇷", label: "Français", rtl: false },
  { code: "ar", flag: "🇸🇦", label: "العربية", rtl: true },
  { code: "en", flag: "🇬🇧", label: "English", rtl: false },
  { code: "darija", flag: "🇲🇦", label: "الدارجة", rtl: true },
];

const WELCOME: Record<Lang, string> = {
  fr: "Bonjour ! Je suis le **Copilote IPISB Connect**. Je peux vous aider à naviguer et utiliser la plateforme — posez-moi une question sur un module ou une action précise.",
  ar: "مرحباً! أنا **مساعد منصة IPISB Connect**. يمكنني مساعدتك في التنقل واستخدام المنصة — اطرح علي سؤالاً حول أي وحدة أو إجراء.",
  en: "Hello! I'm the **IPISB Connect Copilot**. I can help you navigate and use the platform — ask me about any module or specific task.",
  darija: "Salam! Ana **Copilote dyal IPISB Connect**. Nqder n3awnek bach tsta3mel la plateforme — sowlni 3la ay module wla action.",
};

const PLACEHOLDER: Record<Lang, string> = {
  fr: "Posez votre question…", ar: "اكتب سؤالك…", en: "Ask your question…", darija: "Kteb so2alek…",
};

const SUGGESTIONS_BY_ROLE: Record<string, Record<Lang, string[]>> = {
  admin: {
    fr: ["Comment approuver un congé ?", "C'est quoi le module RH ?", "Où générer la paie ?"],
    ar: ["كيف أوافق على طلب إجازة؟", "ما هي وحدة الموارد البشرية؟", "أين أولد كشف الرواتب؟"],
    en: ["How do I approve a leave request?", "What is the RH module?", "Where do I generate payroll?"],
    darija: ["Kifach nwafeq 3la conge?", "Shno houwa module RH?", "Fin ngenere paie?"],
  },
  professor: {
    fr: ["Comment créer un contrôle continu ?", "Où publier un examen ?", "Comment voir mes classes ?"],
    ar: ["كيف أنشئ مراقبة مستمرة؟", "أين أنشر امتحانًا؟", "كيف أرى أقسامي؟"],
    en: ["How do I create a continuous assessment?", "Where do I publish an exam?", "How do I see my classes?"],
    darija: ["Kifach nsawb controle continu?", "Fin npublier examen?", "Kifach nshouf classes dyali?"],
  },
  student: {
    fr: ["Où voir mon contrôle continu ?", "Comment rejoindre une réunion ?", "Où voir mes notes d'examen ?"],
    ar: ["أين أرى مراقبتي المستمرة؟", "كيف ألتحق باجتماع؟", "أين أرى نتائج امتحاناتي؟"],
    en: ["Where do I see my continuous assessment?", "How do I join a meeting?", "Where do I see my exam results?"],
    darija: ["Fin nshouf controle continu dyali?", "Kifach ndkhol l reunion?", "Fin nshouf notes dyal examen?"],
  },
};

function escapeHtml(text: string) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function renderMarkdown(text: string) {
  return escapeHtml(text).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>").replace(/\n/g, "<br/>");
}

async function authHeaders(): Promise<Record<string, string>> {
  const { data: { session } } = await supabase.auth.getSession();
  return {
    "Content-Type": "application/json",
    ...(session?.access_token ? { Authorization: `Bearer ${session.access_token}` } : {}),
  };
}

export function PlatformCopilot() {
  const { roles } = useAuth();
  const { isMobile } = useBreakpoint();
  const roleKey = roles.includes("admin") ? "admin" : roles.includes("professor") ? "professor" : "student";

  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState<Lang | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const rtl = lang === "ar" || lang === "darija";

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, streaming]);
  useEffect(() => { if (open && lang) setTimeout(() => inputRef.current?.focus(), 50); }, [open, lang]);

  function selectLang(l: Lang) {
    setLang(l);
    setMessages([{ role: "assistant", content: WELCOME[l] }]);
    setTimeout(() => inputRef.current?.focus(), 100);
  }

  async function send(override?: string) {
    const text = (override ?? input).trim();
    if (!text || streaming || !lang) return;
    setInput("");
    if (inputRef.current) inputRef.current.style.height = "auto";

    const history = [...messages, { role: "user" as const, content: text }];
    setMessages([...history, { role: "assistant", content: "" }]);
    setStreaming(true);

    try {
      const res = await fetch(`${API}/api/copilot/stream`, {
        method: "POST",
        headers: await authHeaders(),
        body: JSON.stringify({ messages: history.map(m => ({ role: m.role, content: m.content })), language: lang }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "", full = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const payload = line.slice(6).trim();
          if (payload === "[DONE]") { await reader.cancel().catch(() => {}); return; }
          try {
            const parsed = JSON.parse(payload);
            if (parsed.text) {
              full += parsed.text;
              setMessages(prev => {
                const next = [...prev];
                next[next.length - 1] = { role: "assistant", content: full };
                return next;
              });
            }
          } catch { /* ignore parse errors */ }
        }
      }
    } catch (err) {
      console.error("Copilot error:", err);
      setMessages(prev => {
        const next = [...prev];
        next[next.length - 1] = { role: "assistant", content: "Désolé, une erreur est survenue. Réessayez dans un instant." };
        return next;
      });
    } finally {
      setStreaming(false);
    }
  }

  function handleKey(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  }

  useEffect(() => {
    if (!open) return;
    const onEsc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [open]);

  const suggestions = lang ? SUGGESTIONS_BY_ROLE[roleKey][lang] : [];

  return (
    <>
      <style>{`
        @keyframes pc-in{from{opacity:0;transform:translateY(16px) scale(.96)}to{opacity:1;transform:none}}
        .pc-focus:focus-visible{outline:2px solid var(--pal-primary);outline-offset:2px}
      `}</style>

      {open && (
        <div role="dialog" aria-label="Copilote IPISB Connect" style={{
          position: "fixed", zIndex: 1000,
          ...(isMobile
            ? { left: 8, right: 8, bottom: 84, top: 12, width: "auto", height: "auto" }
            : { bottom: 88, left: 24, width: 380, height: 540, maxHeight: "calc(100vh - 112px)" }),
          background: "var(--pal-paper)", border: "1px solid var(--pal-line)", borderRadius: 20,
          display: "flex", flexDirection: "column", overflow: "hidden",
          boxShadow: "0 24px 80px rgba(0,0,0,.22)", animation: "pc-in .22s cubic-bezier(.4,0,.2,1)",
          fontFamily: sans,
        }}>
          <div style={{ background: "var(--pal-cream)", borderBottom: "1px solid var(--pal-line)", padding: "14px 16px", display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 34, height: 34, borderRadius: 999, background: "var(--pal-primary)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}><Sparkles size={16} color="var(--pal-paper)" strokeWidth={1.9} /></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, fontWeight: 700, color: "var(--pal-ink)" }}>Copilote IPISB</div>
              <div style={{ fontSize: 11, color: "var(--pal-muted)" }}>Assistant d'utilisation de la plateforme</div>
            </div>
            {lang && (
              <button onClick={() => { setLang(null); setMessages([]); }} title="Changer de langue" className="pc-focus" style={{
                background: "var(--pal-pale)", border: "1px solid var(--pal-line)", borderRadius: 8,
                padding: "3px 8px", cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
              }}>
                <span>{LANGS.find(l => l.code === lang)?.flag}</span>
                <ChevronDown size={11} />
              </button>
            )}
            <button onClick={() => setOpen(false)} aria-label="Fermer" className="pc-focus" style={{ background: "none", border: 0, cursor: "pointer", color: "var(--pal-muted)", padding: 4 }}>
              <X size={16} strokeWidth={2} />
            </button>
          </div>

          {!lang ? (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 24, gap: 16 }}>
              <div style={{ fontSize: 13, color: "var(--pal-muted)", textAlign: "center" }}>Choisissez votre langue · اختر لغتك</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, width: "100%" }}>
                {LANGS.map(l => (
                  <button key={l.code} onClick={() => selectLang(l.code)} className="pc-focus" style={{
                    background: "var(--pal-pale)", border: "1px solid var(--pal-line)", borderRadius: 12,
                    padding: "14px 8px", cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
                  }}>
                    <span style={{ fontSize: 22 }}>{l.flag}</span>
                    <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--pal-ink)", direction: l.rtl ? "rtl" : "ltr" }}>{l.label}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <>
              <div style={{ flex: 1, overflowY: "auto", padding: "14px 12px" }}>
                {messages.map((m, i) => (
                  <div key={i} style={{ display: "flex", justifyContent: m.role === "assistant" ? "flex-start" : "flex-end", marginBottom: 10 }}>
                    <div style={{
                      maxWidth: "82%", padding: "9px 12px",
                      background: m.role === "assistant" ? "var(--pal-pale)" : "var(--pal-primary)",
                      color: m.role === "assistant" ? "var(--pal-ink)" : "var(--pal-paper)",
                      borderRadius: m.role === "assistant" ? "4px 14px 14px 14px" : "14px 4px 14px 14px",
                      fontSize: 13, lineHeight: 1.55, direction: rtl ? "rtl" : "ltr", textAlign: rtl ? "right" : "left",
                    }}>
                      {m.role === "assistant"
                        ? <span dangerouslySetInnerHTML={{ __html: renderMarkdown(m.content) || "…" }} />
                        : m.content}
                    </div>
                  </div>
                ))}
                <div ref={bottomRef} />
              </div>

              {messages.length <= 1 && (
                <div style={{ padding: "0 12px 10px", display: "flex", gap: 6, flexWrap: "wrap", justifyContent: rtl ? "flex-end" : "flex-start" }}>
                  {suggestions.map(s => (
                    <button key={s} onClick={() => send(s)} className="pc-focus" style={{
                      background: "var(--pal-pale)", border: "1px solid var(--pal-line)", color: "var(--pal-primary-deep)",
                      borderRadius: 999, padding: "5px 11px", fontSize: 11, fontWeight: 600, cursor: "pointer", direction: rtl ? "rtl" : "ltr",
                    }}>{s}</button>
                  ))}
                </div>
              )}

              <div style={{ padding: "10px 12px", borderTop: "1px solid var(--pal-line)", background: "var(--pal-cream)", display: "flex", gap: 8, alignItems: "flex-end" }}>
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={e => {
                    setInput(e.target.value);
                    e.target.style.height = "auto";
                    e.target.style.height = `${Math.min(e.target.scrollHeight, 90)}px`;
                  }}
                  onKeyDown={handleKey}
                  placeholder={PLACEHOLDER[lang]}
                  rows={1}
                  dir={rtl ? "rtl" : "ltr"}
                  style={{
                    flex: 1, background: "var(--pal-paper)", border: "1px solid var(--pal-line)", borderRadius: 12,
                    padding: "9px 12px", color: "var(--pal-ink)", fontFamily: sans, fontSize: 13, resize: "none",
                    outline: "none", lineHeight: 1.4, maxHeight: 90, textAlign: rtl ? "right" : "left",
                  }}
                />
                <button onClick={() => send()} disabled={!input.trim() || streaming} aria-label="Envoyer" className="pc-focus" style={{
                  width: 34, height: 34, borderRadius: 999, flexShrink: 0, border: 0,
                  background: input.trim() && !streaming ? "var(--pal-primary)" : "var(--pal-line)",
                  color: "var(--pal-paper)", cursor: input.trim() && !streaming ? "pointer" : "default",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}><Send size={14} strokeWidth={2} /></button>
              </div>
            </>
          )}
        </div>
      )}

      <button
        onClick={() => setOpen(o => !o)}
        aria-label={open ? "Fermer le copilote" : "Ouvrir le copilote IPISB"}
        aria-expanded={open}
        className="pc-focus"
        style={{
          position: "fixed", bottom: 24, left: 24, zIndex: open ? 1000 : 50,
          width: 52, height: 52, borderRadius: 999, border: 0, cursor: "pointer",
          background: "var(--pal-primary)", color: "var(--pal-paper)",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 4px 20px rgba(0,0,0,.25)", transition: "transform .2s",
        }}
        onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.transform = "scale(1.07)"; }}
        onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.transform = "scale(1)"; }}
        title="Copilote IPISB Connect"
      >
        {open ? <X size={19} strokeWidth={2} /> : <Sparkles size={20} strokeWidth={1.8} />}
      </button>
    </>
  );
}
