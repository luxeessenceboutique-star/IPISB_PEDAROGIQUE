/**
 * IPISB Connect — shared dashboard primitives (design handoff, June 2026).
 * PageHead, SectionLabel, ProgressBar, DashAvatar, EmptyHint.
 * Visual spec: design_handoff_ipisb_dashboard README — serif page titles,
 * eyebrow labels, pale-track progress bars, initials avatars.
 */
import type { CSSProperties, ReactNode } from "react";

/** Eyebrow + 34px serif title + optional sub + right-aligned actions. */
export function PageHead({
  eyebrow,
  title,
  sub,
  actions,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: 16,
        marginBottom: 26,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h1 className="h-serif" style={{ fontSize: 34, lineHeight: 1.05, letterSpacing: ".005em" }}>
          {title}
        </h1>
        {sub ? (
          <p style={{ color: "var(--pal-muted)", fontSize: 13.5, marginTop: 2 }}>{sub}</p>
        ) : null}
      </div>
      {actions ? (
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>{actions}</div>
      ) : null}
    </div>
  );
}

/** Deep-green eyebrow section label with optional trailing action. */
export function SectionLabel({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div
      style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}
    >
      <span className="eyebrow" style={{ color: "var(--pal-primary-deep)" }}>
        {children}
      </span>
      {action ?? null}
    </div>
  );
}

/** 5px progress bar — pale track, animated brand-green fill. */
export function ProgressBar({
  value,
  tone = "primary",
  height = 5,
}: {
  value: number;
  tone?: "primary" | "accent" | "good" | "warn";
  height?: number;
}) {
  const tones: Record<string, string> = {
    primary: "var(--pal-primary)",
    accent: "var(--pal-accent)",
    good: "var(--pal-good)",
    warn: "var(--pal-warn)",
  };
  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(Math.min(100, Math.max(0, value)))}
      aria-valuemin={0}
      aria-valuemax={100}
      style={{ height, borderRadius: 99, background: "var(--pal-pale)", overflow: "hidden", width: "100%" }}
    >
      <div
        style={{
          height: "100%",
          width: `${Math.min(100, Math.max(0, value))}%`,
          borderRadius: 99,
          background: tones[tone],
          transition: "width .5s cubic-bezier(.22,1,.36,1)",
        }}
      />
    </div>
  );
}

/** Initials avatar circle. */
export function DashAvatar({
  name,
  size = 34,
  tone = "mid",
  style,
}: {
  name: string;
  size?: number;
  tone?: "mid" | "primary" | "soft" | "accent" | "ink";
  style?: CSSProperties;
}) {
  const initials =
    name
      .split(" ")
      .map((w) => w[0])
      .filter(Boolean)
      .slice(0, 2)
      .join("")
      .toUpperCase() || "?";
  const bgs: Record<string, string> = {
    mid: "var(--pal-mid)",
    primary: "var(--pal-primary)",
    soft: "var(--pal-soft)",
    accent: "var(--pal-accent)",
    ink: "var(--pal-ink2)",
  };
  const fg = tone === "soft" ? "var(--pal-primary-deep)" : "var(--pal-paper)";
  return (
    <div
      aria-hidden
      style={{
        width: size,
        height: size,
        borderRadius: 999,
        background: bgs[tone] ?? bgs.mid,
        color: fg,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontWeight: 700,
        fontSize: size * 0.36,
        flexShrink: 0,
        letterSpacing: ".02em",
        ...style,
      }}
    >
      {initials}
    </div>
  );
}

/** Full-page "coming soon" placeholder — PageHead + a centered EmptyHint,
    for sidebar entries that exist in the nav ahead of the feature itself. */
export function ComingSoonPage({
  eyebrow,
  title,
  sub,
  icon,
  note = "Cette section arrive bientôt.",
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  sub?: ReactNode;
  icon?: ReactNode;
  note?: ReactNode;
}) {
  return (
    <div>
      <PageHead eyebrow={eyebrow} title={title} sub={sub} />
      <div className="dash-card" style={{ padding: 0 }}>
        <EmptyHint icon={icon} text={note} />
      </div>
    </div>
  );
}

/** Centered muted empty-state hint (icon + message). */
export function EmptyHint({ icon, text }: { icon?: ReactNode; text: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 10,
        padding: "40px 20px",
        color: "var(--pal-muted)",
      }}
    >
      {icon ? <span style={{ opacity: 0.5, display: "flex" }}>{icon}</span> : null}
      <span style={{ fontSize: 13 }}>{text}</span>
    </div>
  );
}
