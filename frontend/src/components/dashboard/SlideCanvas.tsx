/* ─── One read-only slide renderer, shared by every non-authoring surface.
   Three places used to draw a slide: the student viewer (faithfully), the
   editor's slide rail and the gabarit picker (each with its own rough
   approximation that ignored fill, radius and motifs). That was tolerable
   when a slide held four elements; the M101 gabarits run 20–45, and an
   approximation of one is unreadable. So the real element props render
   once, here, and the miniatures are the same component at a smaller size.

   Coordinates are the editor's fixed 800×450 design space, laid out in
   percentages with font sizes in container-query units, so one component
   serves a 176px thumbnail and a full-width viewer with no measurement and
   no canvas. ──────────────────────────────────────────────────────────── */
import type { CSSProperties } from "react";

export const STAGE_W = 800;
export const STAGE_H = 450;

export type ElementBase = { id: string; x: number; y: number; width: number; height: number; rotation: number };
export type TextEl = ElementBase & {
  type: "text"; content: string; fontSize: number; fontFamily: string;
  bold: boolean; italic: boolean; underline: boolean;
  align: "left" | "center" | "right"; color: string; backgroundColor: string | null;
};
export type ImageEl = ElementBase & { type: "image"; src: string; opacity?: number };
export type ShapeEl = ElementBase & {
  type: "shape"; shapeType: "rectangle" | "circle" | "line"; fill: string; stroke: string; strokeWidth: number;
  cornerRadius?: number; opacity?: number;
};
/** A repeating dot grid as a single element — see the backend's
 *  slide_elements.motif() for why this isn't N circles. */
export type MotifEl = ElementBase & {
  type: "motif"; motifType: "dots"; color: string; dotSize: number; gap: number; opacity?: number;
};
export type SlideElement = TextEl | ImageEl | ShapeEl | MotifEl;
export type ViewerSlide = { id: string; title: string; elements: SlideElement[]; background?: string | null };

const pct = (v: number, of: number) => `${(v / of) * 100}%`;
/** Design-space px → container-query width units: scales with the box. */
export const cqw = (v: number) => `${(v / STAGE_W) * 100}cqw`;

export function SlideElementView({ el }: { el: SlideElement }) {
  const box: CSSProperties = {
    position: "absolute",
    left: pct(el.x, STAGE_W), top: pct(el.y, STAGE_H),
    width: pct(el.width, STAGE_W), height: pct(el.height, STAGE_H),
    // Konva rotates about a node's top-left by default, so the DOM has to
    // as well — with CSS's default centre origin, any rotated element (the
    // vertical CHAPITRE tab, the cover's diamonds) lands somewhere the
    // teacher never put it.
    transform: el.rotation ? `rotate(${el.rotation}deg)` : undefined,
    transformOrigin: "top left",
    opacity: el.type === "text" ? undefined : el.opacity ?? 1,
  };

  if (el.type === "motif") {
    const r = cqw(el.dotSize / 2);
    return (
      <div
        key={el.id}
        style={{
          ...box,
          backgroundImage: `radial-gradient(${el.color} ${r}, transparent ${r})`,
          backgroundSize: `${cqw(el.gap)} ${cqw(el.gap)}`,
        }}
      />
    );
  }

  if (el.type === "image") {
    return <img key={el.id} src={el.src} alt="" style={{ ...box, objectFit: "fill" }} />;
  }

  if (el.type === "shape") {
    if (el.shapeType === "line") {
      /* Drawn against a full-slide viewBox rather than one sized to the
         line's own bounding box. A line whose delta is zero or negative —
         a vertical clock hand, a star-diagram connector pointing up or
         left — yields a degenerate "0 0 W H" viewBox that browsers refuse
         to render, which silently dropped most connectors while leaving
         the down-right ones visible. Sizing the viewBox 800×450 also
         matches the container's aspect ratio, so stroke width scales
         uniformly instead of being stretched by a flat box. */
      return (
        <svg
          key={el.id}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", overflow: "visible", opacity: el.opacity ?? 1 }}
          viewBox={`0 0 ${STAGE_W} ${STAGE_H}`}
          preserveAspectRatio="none"
        >
          <line
            x1={el.x} y1={el.y} x2={el.x + el.width} y2={el.y + el.height}
            stroke={el.stroke} strokeWidth={el.strokeWidth}
            transform={el.rotation ? `rotate(${el.rotation} ${el.x} ${el.y})` : undefined}
          />
        </svg>
      );
    }
    return (
      <div
        key={el.id}
        style={{
          ...box,
          background: el.fill || "transparent",
          border: el.strokeWidth ? `${cqw(el.strokeWidth)} solid ${el.stroke}` : undefined,
          boxSizing: "border-box",
          borderRadius: el.shapeType === "circle" ? "50%" : el.cornerRadius ? cqw(el.cornerRadius) : undefined,
        }}
      />
    );
  }

  return (
    <div
      key={el.id}
      style={{
        ...box,
        fontSize: cqw(el.fontSize), fontFamily: el.fontFamily,
        fontWeight: el.bold ? 700 : 400, fontStyle: el.italic ? "italic" : "normal",
        textDecoration: el.underline ? "underline" : "none",
        textAlign: el.align, color: el.color, background: el.backgroundColor || "transparent",
        // "visible" on purpose: some existing/generated slides pair a long
        // heading with a box sized for one line — clipping would silently
        // drop the second line. Overflowing text is recoverable (still
        // readable); losing it isn't.
        lineHeight: 1.25, whiteSpace: "pre-wrap", overflow: "visible", padding: "0.25cqw",
      }}
    >
      {el.content}
    </div>
  );
}

/** One slide, rendered read-only at whatever width the caller gives it. */
export function SlideStatic({
  slide, className = "", style,
}: {
  slide: Pick<ViewerSlide, "elements" | "background">;
  className?: string;
  style?: CSSProperties;
}) {
  return (
    <div
      className={className}
      style={{
        position: "relative", aspectRatio: "16/9", overflow: "hidden",
        background: slide.background || "#ffffff",
        containerType: "inline-size",
        ...style,
      } as CSSProperties}
    >
      {slide.elements.map(el => <SlideElementView key={el.id} el={el} />)}
    </div>
  );
}
