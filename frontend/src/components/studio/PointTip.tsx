/**
 * PointTip: one-sentence tooltip for the hand-written Studio SVG charts.
 * Marks are tabbable <g> elements; hover, focus or tap opens the sentence, tap outside, Escape or scroll closes it.
 * The sentence is also the mark's <title> and aria-label, so nothing depends on the tooltip being seen.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";

export interface Tip { x: number; y: number; text: string }

/** Measured width of a container, for SVGs whose viewBox follows the rendered width. */
export function useWidth(initial = 560) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(initial);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setW(Math.max(260, Math.round(el.clientWidth)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, w };
}

export function usePointTip() {
  const [tip, setTip] = useState<Tip | null>(null);
  const close = useCallback(() => setTip(null), []);
  useEffect(() => {
    if (!tip) return;
    const onDown = (e: PointerEvent) => {
      const t = e.target as Element | null;
      if (!t?.closest?.("[data-tip]")) setTip(null);
    };
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") setTip(null); };
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("scroll", close, { passive: true, capture: true });
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", close, { capture: true });
      window.removeEventListener("keydown", onKey);
    };
  }, [tip, close]);

  /** Props for a tabbable mark centred at (x, y) in SVG user units (= CSS px, the viewBox follows width). */
  const markProps = (x: number, y: number, text: string) => ({
    "data-tip": "",
    tabIndex: 0,
    role: "img",
    "aria-label": text,
    className: "st-mark",
    onMouseEnter: () => setTip({ x, y, text }),
    onMouseLeave: close,
    onFocus: () => setTip({ x, y, text }),
    onBlur: close,
    onClick: () => setTip((t) => (t && t.text === text ? null : { x, y, text })),
    onKeyDown: (e: KeyboardEvent) => { if (e.key === "Escape") close(); },
  });

  return { tip, markProps };
}

/** Absolutely positioned bubble over the chart box. `width` is the box width, to keep it inside. */
export function TipBubble({ tip, width }: { tip: Tip | null; width: number }): ReactNode {
  if (!tip) return null;
  const maxW = Math.min(280, width - 8);
  const left = Math.max(4, Math.min(tip.x - maxW / 2, width - maxW - 4));
  return (
    <div className="st-tip" role="status" style={{ left, top: tip.y + 14, maxWidth: maxW }}>
      {tip.text}
    </div>
  );
}
