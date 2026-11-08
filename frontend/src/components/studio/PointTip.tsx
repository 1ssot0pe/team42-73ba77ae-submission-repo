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
  const [tip, setTipState] = useState<Tip | null>(null);
  const openedAt = useRef(0);
  const focusOpenedAt = useRef(0);
  const setTip = useCallback((next: Tip | null | ((t: Tip | null) => Tip | null)) => {
    openedAt.current = Date.now();
    setTipState(next);
  }, []);
  const close = useCallback(() => setTipState(null), []);
  useEffect(() => {
    if (!tip) return;
    // Focusing a mark can scroll it into view; only a later, deliberate scroll closes the tooltip.
    const onScroll = () => { if (Date.now() - openedAt.current > 400) close(); };
    const onDown = (e: PointerEvent) => {
      const t = e.target as Element | null;
      if (!t?.closest?.("[data-tip]")) close();
    };
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") setTip(null); };
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("scroll", onScroll, { passive: true, capture: true });
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", onScroll, { capture: true });
      window.removeEventListener("keydown", onKey);
    };
  }, [tip, close, setTip]);

  /** Props for a tabbable mark centred at (x, y) in SVG user units (= CSS px, the viewBox follows width). */
  const markProps = (x: number, y: number, text: string) => ({
    "data-tip": "",
    tabIndex: 0,
    role: "img",
    "aria-label": text,
    className: "st-mark",
    onMouseEnter: () => setTip({ x, y, text }),
    onMouseLeave: close,
    onFocus: () => { focusOpenedAt.current = Date.now(); setTip({ x, y, text }); },
    onBlur: close,
    // A tap fires focus then click: within ~300 ms of a focus-open the click only keeps it open, never toggles it shut.
    onClick: () => {
      const justFocused = Date.now() - focusOpenedAt.current < 300;
      setTip((t) => (t && t.text === text && !justFocused ? null : { x, y, text }));
    },
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
    <div className="chart-tooltip st-tip" role="status" style={{ left, top: tip.y + 14, maxWidth: maxW }}>
      {tip.text}
    </div>
  );
}
