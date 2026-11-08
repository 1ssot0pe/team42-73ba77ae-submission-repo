/**
 * EffectChart: a two-row forest plot (reported and bias-adjusted) on a shared Hedges' g axis.
 * Inline SVG keeps it cheap. The viewBox follows the rendered width, so text stays at its real size
 * on a phone instead of shrinking with the drawing. Violet and orange are allowed here because this is a chart.
 */
import { useLayoutEffect, useRef, useState } from "react";
import type { Effect } from "./report";
import { fmt } from "./report";

const VIOLET = "var(--color-spark-violet)";
const ORANGE = "var(--color-spark-ember)";
const NICE = [1, 2, 2.5, 5];

/** Rounded ticks that cover [lo, hi] with at least `min` ticks, choosing the widest nice step that does. */
export function niceTicks(lo: number, hi: number, min = 5): { ticks: number[]; step: number } {
  if (!(hi > lo)) { lo -= 0.5; hi += 0.5; }
  const steps: number[] = [];
  for (let p = -3; p <= 3; p++) for (const m of NICE) steps.push(m * 10 ** p);
  let pick = steps[0];
  for (const s of steps) {
    const n = Math.ceil(hi / s - 1e-9) - Math.floor(lo / s + 1e-9) + 1;
    if (n >= min) pick = s;
    else break;
  }
  const first = Math.floor(lo / pick + 1e-9), last = Math.ceil(hi / pick - 1e-9);
  const ticks: number[] = [];
  for (let i = first; i <= last; i++) ticks.push(Number((i * pick).toFixed(6)));
  return { ticks, step: pick };
}

function decimals(step: number): number {
  for (let d = 0; d <= 4; d++) if (Math.abs(Math.round(step * 10 ** d) - step * 10 ** d) < 1e-9) return d;
  return 2;
}

export function EffectChart({ e, note }: { e: Effect; note: string }) {
  const box = useRef<HTMLDivElement>(null);
  const [W, setW] = useState(560);
  useLayoutEffect(() => {
    const el = box.current;
    if (!el) return;
    const measure = () => setW(Math.max(240, Math.round(el.clientWidth)));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const vals = [e.reported, e.reportedLo, e.reportedHi, e.adjusted, e.adjustedLo, e.adjustedHi, 0]
    .filter((v): v is number => v !== null);
  const rawLo = Math.min(...vals), rawHi = Math.max(...vals);
  const pad = (rawHi - rawLo) * 0.04 || 0.1;
  const { ticks, step } = niceTicks(rawLo - pad, rawHi + pad);
  const lo = ticks[0], hi = ticks[ticks.length - 1];
  const dp = decimals(step);
  const tickText = (v: number) => (Math.abs(v) < 1e-9 ? "0" : fmt(v, dp));

  // Narrow: row labels sit above each interval so the plot keeps the full width.
  const narrow = W < 440;
  const L = narrow ? 18 : 116, R = 18;
  const rowY = narrow ? [34, 88] : [26, 66];
  const axisY = rowY[1] + (narrow ? 28 : 30);
  const H = axisY + 46;
  const x = (v: number) => L + ((v - lo) / (hi - lo)) * (W - L - R);

  const rows = [
    { label: "Reported", c: VIOLET, mid: e.reported, a: e.reportedLo, b: e.reportedHi, y: rowY[0] },
    { label: "Bias-adjusted", c: ORANGE, mid: e.adjusted, a: e.adjustedLo, b: e.adjustedHi, y: rowY[1] },
  ];
  const range = (a: number | null, b: number | null) => (a !== null && b !== null ? ` (${fmt(a)} to ${fmt(b)})` : "");
  const summary = `Forest plot of Hedges' g. Reported ${fmt(e.reported)}${range(e.reportedLo, e.reportedHi)}, bias-adjusted ${fmt(e.adjusted)}${range(e.adjustedLo, e.adjustedHi)}.`;

  return (
    <figure className="studio-chart">
      <div ref={box} className="studio-chart__box">
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label={summary}>
          {ticks.map((t) => (
            <line key={`g${t}`} x1={x(t)} x2={x(t)} y1={6} y2={axisY} className="studio-chart__grid" />
          ))}
          <line x1={x(0)} x2={x(0)} y1={4} y2={axisY} className="studio-chart__zero" />
          <line x1={L} x2={W - R} y1={axisY} y2={axisY} className="studio-chart__axis" />
          {ticks.map((t) => (
            <g key={`t${t}`}>
              <line x1={x(t)} x2={x(t)} y1={axisY} y2={axisY + 4} className="studio-chart__axis" />
              <text x={x(t)} y={axisY + 18} textAnchor="middle" className="studio-chart__tick">{tickText(t)}</text>
            </g>
          ))}
          <text x={L + (W - L - R) / 2} y={H - 4} textAnchor="middle" className="studio-chart__title">
            Effect size (Hedges&rsquo; g)
          </text>
          {rows.map((r) => (
            <g key={r.label}>
              <text
                x={narrow ? L : 0}
                y={narrow ? r.y - 14 : r.y}
                dominantBaseline={narrow ? "auto" : "middle"}
                className="studio-chart__row"
              >
                {r.label}
              </text>
              {r.a !== null && r.b !== null ? (
                <line x1={x(r.a)} x2={x(r.b)} y1={r.y} y2={r.y} strokeWidth={2} strokeLinecap="round" style={{ stroke: r.c }} />
              ) : null}
              {r.mid !== null ? <circle cx={x(r.mid)} cy={r.y} r={5} style={{ fill: r.c }} /> : null}
            </g>
          ))}
        </svg>
      </div>
      <figcaption className="studio-chart__caption">
        <span><span className="studio-key" style={{ background: VIOLET }} /> Reported</span>
        <span><span className="studio-key" style={{ background: ORANGE }} /> Bias-adjusted</span>
        <span className="studio-muted">Dot is the estimate, line the 95% range, dashed line no effect.</span>
        {note ? <span className="studio-muted">{note}</span> : null}
      </figcaption>
    </figure>
  );
}
