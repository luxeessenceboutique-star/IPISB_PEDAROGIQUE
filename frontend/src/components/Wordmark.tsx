import { Logo } from "@/components/Logo";

interface WordmarkProps {
  size?: number;
  dark?: boolean;
}

export function Wordmark({ size = 36, dark = false }: WordmarkProps) {
  const inkColor = dark ? "oklch(99% 0.005 160)" : "oklch(22% 0.025 175)";
  const subColor = dark ? "oklch(82% 0.045 165)" : "oklch(48% 0.085 175)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <Logo size={size} mono={dark} onDark={dark} />
      <div style={{ display: "flex", flexDirection: "column", lineHeight: 1 }}>
        <span style={{
          fontFamily: '"Cormorant Garamond", Georgia, serif',
          fontWeight: 600,
          fontSize: size * 0.52,
          color: inkColor,
          letterSpacing: ".005em",
        }}>IPISB</span>
        <span style={{
          fontFamily: '"Manrope", system-ui, sans-serif',
          fontSize: size * 0.24,
          fontWeight: 600,
          letterSpacing: ".24em",
          textTransform: "uppercase" as const,
          color: subColor,
          marginTop: 3,
        }}>Connect</span>
      </div>
    </div>
  );
}
