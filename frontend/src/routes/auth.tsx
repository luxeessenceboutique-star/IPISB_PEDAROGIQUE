import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Wordmark } from "@/components/Wordmark";
import { Logo } from "@/components/Logo";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { useBreakpoint } from "@/lib/useBreakpoint";
import { toast } from "sonner";

const PAL = {
  ink:     "oklch(22% 0.025 175)",
  ink2:    "oklch(28% 0.04 175)",
  text:    "oklch(34% 0.03 180)",
  muted:   "oklch(48% 0.02 180)",
  primary: "oklch(48% 0.085 175)",
  mid:     "oklch(62% 0.085 170)",
  soft:    "oklch(82% 0.045 165)",
  pale:    "oklch(94% 0.025 165)",
  cream:   "oklch(97% 0.012 90)",
  paper:   "oklch(99% 0.005 160)",
  line:    "oklch(88% 0.015 170)",
};
const serif = '"Cormorant Garamond", Georgia, serif';
const sans  = '"Manrope", system-ui, sans-serif';
const mono  = '"JetBrains Mono", ui-monospace, monospace';

export const Route = createFileRoute("/auth")({
  validateSearch: (_s: Record<string, unknown>) => ({}),
  component: AuthPage,
});

function Field({ label, type = "text", placeholder, value, onChange, testId }: {
  label: string; type?: string; placeholder?: string; value: string; onChange?: (v: string) => void; testId?: string;
}) {
  return (
    <div style={{ marginBottom: 16 }}>
      <label style={{ fontFamily: sans, fontSize: 11, fontWeight: 600, color: PAL.muted, letterSpacing: ".1em", textTransform: "uppercase" as const }}>{label}</label>
      <input
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={e => onChange?.(e.target.value)}
        required
        className="u-input"
        data-testid={testId}
        style={{ marginTop: 8, width: "100%", padding: "12px 16px", background: PAL.paper, border: `1px solid ${PAL.line}`, borderRadius: 10, fontFamily: sans, fontSize: 14, color: PAL.ink, outline: "none", boxSizing: "border-box" as const }}
      />
    </div>
  );
}

const LANG_LABELS: Record<string, string> = { fr: "FR", en: "EN", ar: "ع" };

function AuthPage() {
  const { lang, setLang, t } = useI18n();
  const { isMobile } = useBreakpoint();
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (user) navigate({ to: "/dashboard" }); }, [user, navigate]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await signIn(email, password);
      navigate({ to: "/dashboard" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("auth.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div dir="ltr" style={{
      minHeight: "100vh", background: PAL.cream,
      display: "grid",
      gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr",
    }}>

      {/* Left panel — hidden on mobile */}
      <div style={{ background: PAL.ink, padding: "60px 56px", position: "relative", display: isMobile ? "none" : "flex", flexDirection: "column", justifyContent: "space-between", overflow: "hidden" }}>
        <Wordmark size={44} dark />

        <div style={{ position: "relative", zIndex: 1 }}>
          <h2 style={{ fontFamily: serif, fontSize: 64, fontWeight: 500, color: PAL.paper, lineHeight: 1, letterSpacing: "-.02em", maxWidth: 460 }}>
            {t("auth.side_h2a")}{" "}
            <span style={{ fontStyle: "italic", color: PAL.soft }}>{t("auth.side_h2b")}</span>
          </h2>
          <p style={{ fontFamily: sans, fontSize: 14, color: "oklch(78% .03 180)", marginTop: 24, maxWidth: 420, lineHeight: 1.6 }}>
            {t("auth.platform_sub")}
          </p>
        </div>

        <div style={{ position: "absolute", right: -120, bottom: -120, opacity: .15 }}>
          <Logo size={520} mono onDark />
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", position: "relative", zIndex: 1 }}>
          <div style={{ display: "flex", gap: 20, fontFamily: mono, fontSize: 11, color: PAL.mid, letterSpacing: ".08em", textTransform: "uppercase" as const }}>
            <span>El Jadida</span><span>·</span><span>Maroc · Morocco</span>
          </div>
          {/* 3-way language switcher */}
          <div style={{ display: "flex", gap: 6 }}>
            {(["fr", "en", "ar"] as const).map(l => (
              <button key={l} type="button" onClick={() => setLang(l)} style={{
                fontFamily: sans, fontSize: 12, fontWeight: 700,
                padding: "6px 12px", borderRadius: 8, border: 0,
                background: lang === l ? PAL.paper : "oklch(35% 0.04 175)",
                color: lang === l ? PAL.ink : "oklch(78% .03 180)",
                cursor: "pointer", lineHeight: 1,
                transition: "background .2s, color .2s",
              }}>
                {LANG_LABELS[l]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right panel */}
      <div style={{ padding: isMobile ? "40px 24px" : "60px 56px", display: "flex", flexDirection: "column", justifyContent: "center" }}>
        {/* Top-right lang switcher (visible on mobile / when dark panel is hidden) */}
        <div style={{ display: "flex", gap: 6, justifyContent: "flex-end", marginBottom: 24 }}>
          {(["fr", "en", "ar"] as const).map(l => (
            <button key={l} type="button" onClick={() => setLang(l)} style={{
              fontFamily: sans, fontSize: 12, fontWeight: 700,
              padding: "5px 10px", borderRadius: 8, border: `1px solid ${PAL.line}`,
              background: lang === l ? PAL.ink : "transparent",
              color: lang === l ? PAL.paper : PAL.muted,
              cursor: "pointer", lineHeight: 1,
              transition: "background .2s, color .2s, border-color .2s",
            }}>
              {LANG_LABELS[l]}
            </button>
          ))}
        </div>
        <div className="anim-rise" style={{ maxWidth: 460, margin: "0 auto", width: "100%" }}>

          <div style={{ fontFamily: mono, fontSize: 11, color: PAL.primary, letterSpacing: ".14em", textTransform: "uppercase" as const, fontWeight: 600 }}>
            {t("auth.eyebrow")}
          </div>
          <h1 style={{ fontFamily: serif, fontSize: 48, fontWeight: 500, color: PAL.ink, margin: "16px 0 32px", letterSpacing: "-.02em" }}>
            {t("auth.login_ta")}{" "}
            <span style={{ fontStyle: "italic", color: PAL.primary }}>
              {t("auth.login_tb")}
            </span>
          </h1>

          <form onSubmit={handleSubmit}>
            <Field label={t("auth.email")} type="email" value={email} onChange={setEmail} placeholder="prenom.nom@ipisb.ma" testId="auth-email" />
            <Field label={t("auth.password")} type="password" value={password} onChange={setPassword} placeholder="••••••••" testId="auth-password" />

            <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", marginTop: 8 }}>
              <a href="#" style={{ fontFamily: sans, fontSize: 12, color: PAL.primary, fontWeight: 600 }}>{t("auth.forgot")}</a>
            </div>

            <button type="submit" disabled={busy} data-testid="auth-submit" className="u-hover-lift" style={{
              background: PAL.ink, color: PAL.paper, border: 0, fontFamily: sans, fontSize: 14, fontWeight: 600,
              padding: "14px 0", borderRadius: 999, cursor: busy ? "wait" : "pointer", letterSpacing: ".01em",
              width: "100%", marginTop: 28, opacity: busy ? 0.6 : 1,
            }}>
              {busy ? "…" : t("auth.btn_login")}
            </button>
          </form>

          <div style={{ display: "flex", alignItems: "center", gap: 16, margin: "28px 0", fontFamily: sans, fontSize: 11, color: PAL.muted, textTransform: "uppercase" as const, letterSpacing: ".14em" }}>
            <div style={{ flex: 1, height: 1, background: PAL.line }}></div>
            {t("auth.or")}
            <div style={{ flex: 1, height: 1, background: PAL.line }}></div>
          </div>

          <button className="u-ghost" style={{ background: "transparent", color: PAL.ink, border: `1px solid ${PAL.line}`, fontFamily: sans, fontSize: 14, fontWeight: 500, padding: "12px 0", borderRadius: 999, cursor: "pointer", width: "100%" }}>
            {t("auth.sso")}
          </button>

        </div>
      </div>
    </div>
  );
}
