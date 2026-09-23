import { useEffect, useRef, useState } from "react";

/**
 * Animated counter that preserves the original string formatting.
 * Accepts values like "1 200+", "94 %", "12", 42 — animates the numeric
 * core from 0 to its target once the element scrolls into view.
 * Respects prefers-reduced-motion (renders the final value immediately).
 */
export function CountUp({
  value,
  duration = 1100,
  className,
  style,
}: {
  value: string | number;
  duration?: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  const str = String(value);
  const ref = useRef<HTMLSpanElement>(null);
  const started = useRef(false);
  const [display, setDisplay] = useState(str);

  useEffect(() => {
    setDisplay(str);
    started.current = false;

    const match = str.match(/\d[\d\s  ]*\d|\d/);
    if (!match || typeof match.index !== "number") return;

    const numStr = match[0];
    const target = parseInt(numStr.replace(/[\s  ]/g, ""), 10);
    if (!Number.isFinite(target) || target === 0) return;

    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return; // keep final value, no animation
    }

    const prefix = str.slice(0, match.index);
    const suffix = str.slice(match.index + numStr.length);
    const grouped = /[\s  ]/.test(numStr);
    const el = ref.current;
    if (!el) return;

    const obs = new IntersectionObserver(
      ([e]) => {
        if (!e.isIntersecting || started.current) return;
        started.current = true;
        obs.disconnect();
        const t0 = performance.now();
        const tick = (now: number) => {
          const p = Math.min((now - t0) / duration, 1);
          const eased = 1 - Math.pow(1 - p, 3); // ease-out cubic
          const cur = Math.round(target * eased);
          const formatted = grouped ? cur.toLocaleString("fr-FR") : String(cur);
          setDisplay(prefix + formatted + suffix);
          if (p < 1) requestAnimationFrame(tick);
          else setDisplay(str); // snap to exact original formatting
        };
        setDisplay(prefix + (grouped ? "0" : "0") + suffix);
        requestAnimationFrame(tick);
      },
      { threshold: 0.4 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [str, duration]);

  return (
    <span ref={ref} className={className} style={style}>
      {display}
    </span>
  );
}
