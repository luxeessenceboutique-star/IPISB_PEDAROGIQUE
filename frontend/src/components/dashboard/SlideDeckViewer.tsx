import { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { SlideStatic, type ViewerSlide } from "./SlideCanvas";

/* ─── Read-only slide deck — students see this, never the editor.
   The per-element rendering lives in SlideCanvas, which is deliberately the
   SAME component the editor's slide rail and gabarit picker use: whatever
   the teacher arranged on the authoring canvas reaches the student
   unchanged, including M101's rounded cards, motifs and rotated tabs. This
   file owns only navigation. No drag/select/edit affordances anywhere —
   that's the whole point of it being a separate, learner-only component
   (spec §19), and it stays DOM rather than Konva so it works on phones and
   tablets (spec §29). ─────────────────────────────────────────────────── */
export type { ViewerSlide };

export function SlideDeckViewer({
  slides,
  initialIndex = 0,
  onIndexChange,
}: {
  slides: ViewerSlide[];
  /** Slide to open on (e.g. resuming a teaching session at its last known position). */
  initialIndex?: number;
  /** Reports the currently-displayed slide — e.g. so a teaching session can
      track "where the professor is" without a second, duplicate nav state. */
  onIndexChange?: (index: number, slide: ViewerSlide) => void;
}) {
  const [active, setActive] = useState(initialIndex);

  // Reports the active slide whenever it changes (including on mount) — lets
  // a parent session wrapper persist position without owning navigation.
  useEffect(() => {
    if (!slides.length) return;
    const idx = Math.min(active, slides.length - 1);
    onIndexChange?.(idx, slides[idx]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, slides]);

  if (!slides.length) return null;
  const slide = slides[Math.min(active, slides.length - 1)];

  return (
    <div className="space-y-3">
      <SlideStatic slide={slide} className="w-full rounded-xl border border-border shadow-sm" />

      {slides.length > 1 && (
        <div className="flex items-center justify-between">
          <button
            className="btn-c btn-c-ghost btn-c-sm"
            disabled={active <= 0}
            onClick={() => setActive(a => Math.max(0, a - 1))}
            data-testid="slide-prev"
          >
            <ChevronLeft size={14} strokeWidth={1.7} />Précédent
          </button>
          <div className="flex items-center gap-1.5">
            {slides.map((s, i) => (
              <button
                key={s.id}
                onClick={() => setActive(i)}
                title={s.title}
                className="h-1.5 rounded-full transition-all"
                style={{ width: i === active ? 18 : 6, background: i === active ? "var(--pal-primary, #2F6F5E)" : "var(--pal-line, #d8d8d8)" }}
              />
            ))}
          </div>
          <button
            className="btn-c btn-c-ghost btn-c-sm"
            disabled={active >= slides.length - 1}
            onClick={() => setActive(a => Math.min(slides.length - 1, a + 1))}
            data-testid="slide-next"
          >
            Suivant<ChevronRight size={14} strokeWidth={1.7} />
          </button>
        </div>
      )}
    </div>
  );
}
