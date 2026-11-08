/**
 * EffectChart: two horizontal intervals (reported and bias-adjusted) on a shared axis with a zero line.
 * Inline SVG keeps it cheap. Violet and orange are allowed here because this is a chart.
 */
import type { Effect } from "./report";
import { fmt } from "./report";

const VIOLET = "#0447ff";
const ORANGE = "#ff4704";

export function EffectChart({ e, note }: { e: Effect; note: string }) {
  const vals = [e.reported, e.reportedLo, e.reportedHi, e.adjusted, e.adjustedLo, e.adjustedHi, 0]
    .filter((v): v is number => v !== null);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.1 || 0.5;
  lo -= pad; hi += pad;
  const W = 560, H = 112, L = 12, R = 12;
  const x = (v: number) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const rows: Array<{ label: string; c: string; mid: number | null; a: number | null; b: number | null; y: number }> = [
    { label: "Reported", c: VIOLET, mid: e.reported, a: e.reportedLo, b: e.reportedHi, y: 30 },
    { label: "Bias-adjusted", c: ORANGE, mid: e.adjusted, a: e.adjustedLo, b: e.adjustedHi, y: 70 },
  ];
  const summary = `Reported ${fmt(e.reported)}, bias-adjusted ${fmt(e.adjusted)} (${fmt(e.adjustedLo)} to ${fmt(e.adjustedHi)}).`;
  return (
    <figure className="studio-chart">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={summary}>
        <line x1={x(0)} x2={x(0)} y1={8} y2={H - 20} className="studio-chart__zero" />
        <text x={x(0)} y={H - 6} textAnchor="middle" className="studio-chart__tick">0</text>
        {rows.map((r) =>
          r.mid === null ? null : (
            <g key={r.label}>
              {r.a !== null && r.b !== null ? (
                <line x1={x(r.a)} x2={x(r.b)} y1={r.y} y2={r.y} stroke={r.c} strokeWidth={2} strokeLinecap="round" />
              ) : null}
              <circle cx={x(r.mid)} cy={r.y} r={5} fill={r.c} />
            </g>
          ),
        )}
      </svg>
      <figcaption className="studio-chart__caption">
        <span><span className="studio-key" style={{ background: VIOLET }} /> Reported</span>
        <span><span className="studio-key" style={{ background: ORANGE }} /> Bias-adjusted</span>
        <span className="studio-muted">{note}</span>
      </figcaption>
    </figure>
  );
}
