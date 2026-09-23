interface LogoProps {
  size?: number;
  mono?: boolean;
  onDark?: boolean;
  className?: string;
}

const TEAL = {
  ink:     "oklch(38% 0.06 175)",
  primary: "oklch(52% 0.09 175)",
  mid:     "oklch(64% 0.10 170)",
  soft:    "oklch(78% 0.07 165)",
  pale:    "oklch(92% 0.04 165)",
  paper:   "oklch(98% 0.005 160)",
  dark:    "oklch(22% 0.03 175)",
};

export function Logo({ size = 120, mono = false, onDark = false, className = "" }: LogoProps) {
  const fg = mono ? (onDark ? TEAL.paper : TEAL.ink) : TEAL.primary;
  const fg2 = mono ? fg : TEAL.ink;
  const accent = mono ? fg : TEAL.mid;
  return (
    <svg width={size} height={size} viewBox="0 0 120 120" fill="none" className={className}>
      {/* Left hand arc */}
      <path d="M 18 70 Q 18 92 38 100 L 60 100" stroke={fg} strokeWidth="6" strokeLinecap="round" fill="none"/>
      <path d="M 26 64 Q 26 86 44 92" stroke={accent} strokeWidth="4" strokeLinecap="round" fill="none" opacity="0.7"/>
      {/* Right hand arc */}
      <path d="M 102 70 Q 102 92 82 100 L 60 100" stroke={fg} strokeWidth="6" strokeLinecap="round" fill="none"/>
      <path d="M 94 64 Q 94 86 76 92" stroke={accent} strokeWidth="4" strokeLinecap="round" fill="none" opacity="0.7"/>
      {/* Center emblem circle */}
      <circle cx="60" cy="50" r="26" stroke={fg2} strokeWidth="2.5" fill="none"/>
      {/* Book base */}
      <path d="M 44 58 L 60 56 L 76 58 L 76 62 L 60 60 L 44 62 Z" fill={fg2}/>
      <line x1="60" y1="56" x2="60" y2="60" stroke={mono ? (onDark ? TEAL.dark : TEAL.paper) : TEAL.paper} strokeWidth="0.8"/>
      {/* Caduceus rod */}
      <line x1="60" y1="28" x2="60" y2="56" stroke={fg2} strokeWidth="2"/>
      {/* Wings */}
      <path d="M 60 32 Q 52 30 50 36 Q 56 36 60 36" fill={fg2}/>
      <path d="M 60 32 Q 68 30 70 36 Q 64 36 60 36" fill={fg2}/>
      {/* Serpent */}
      <path d="M 56 38 Q 64 42 56 48 Q 48 52 56 56" stroke={fg2} strokeWidth="1.8" fill="none" strokeLinecap="round"/>
    </svg>
  );
}
