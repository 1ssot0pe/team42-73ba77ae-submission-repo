/**
 * EffectChart (effect-forest): reported vs bias-adjusted Hedges' g on one axis, as a two-row forest plot.
 * Hand-written SVG; the viewBox follows the rendered width so text stays at its real size on a phone.
 * Every number comes from the report: the reported interval is g ± 1.96·se_g (report.ts effect()), the adjusted
 * interval is the backend's correction lo/hi. Nothing else is drawn (no reference effect, no sensitivity row).
 * Violet and orange are allowed here because this is a chart; marker shape and row labels carry the same meaning.
 */
import type { Effect } from "./report";
import { fmt } from "./report";
import { TipBubble, usePointTip, useWidth } from "./PointTip";

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

export function decimals(step: number): number {
  for (let d = 0; d <= 4; d++) if (Math.abs(Math.round(step * 10 ** d) - step * 10 ** d) < 1e-9) return d;
  return 2;
}

const has = (v: number | null): v is number => v !== null;
const bracket = (m: number | null, a: number | null, b: number | null) =>
  m === null ? "Not available" : has(a) && has(b) ? `${fmt(m)} [${fmt(a)}, ${fmt(b)}]` : fmt(m);

export interface EffectFlags { reportedImputed: boolean; uImputed: boolean; signOff: string }

export function effectFlags(e: Effect, signOff: string): EffectFlags {
  return { reportedImputed: e.reportedStatus === "imputed", uImputed: e.uStatus === "imputed", signOff };
}

/** Takeaway title from the data; falls back to a neutral sentence when an input is missing. */
export function effectTitle(e: Effect): string {
  if (!has(e.reported) || !has(e.adjusted)) return "Reported and bias-adjusted effect (Hedges' g)";
  const base = `Reported g ${fmt(e.reported)}; adjusted ${fmt(e.adjusted)}`;
  if (!has(e.adjustedLo) || !has(e.adjustedHi)) return base;
  const crosses = e.adjustedLo <= 0 && e.adjustedHi >= 0;
  return `${base}, interval ${crosses ? "crosses" : "does not cross"} 0`;
}

export function effectAria(e: Effect, f: EffectFlags): string {
  const iv = (a: number | null, b: number | null, pre = "") => (has(a) && b !== null ? ` (${pre}${fmt(a)} to ${fmt(b)}` : "");
  const rep = has(e.reported)
    ? `Reported ${fmt(e.reported)}${iv(e.reportedLo, e.reportedHi, "95% CI ")}${has(e.reportedLo) ? (f.reportedImputed ? ", imputed)" : ")") : ""}`
    : "Reported not available";
  const adj = has(e.adjusted)
    ? `Bias-adjusted ${fmt(e.adjusted)}${iv(e.adjustedLo, e.adjustedHi)}${has(e.adjustedLo) ? (f.uImputed ? ", u imputed)" : ")") : ""}`
    : "Bias-adjusted not available";
  return `Forest plot, Hedges' g. ${rep}. ${adj}. Positive favours the drug.${f.signOff ? ` ${f.signOff}.` : ""}`;
}

export function effectTable(e: Effect, f: EffectFlags) {
  return {
    columns: [
      { key: "row", label: "Row" },
      { key: "est", label: "Estimate (g)", align: "right" as const },
      { key: "lo", label: "95% low (g)", align: "right" as const, derived: true },
      { key: "hi", label: "95% high (g)", align: "right" as const, derived: true },
      { key: "source", label: "Source" },
      { key: "note", label: "Note" },
    ],
    rows: [
      {
        row: "Reported", est: e.reported, lo: e.reportedLo, hi: e.reportedHi,
        source: f.reportedImputed ? "imputed" : e.reportedStatus || "observed",
        note: has(e.se) ? `Interval is g ± 1.96 × SE, SE ${fmt(e.se, 3)}${e.seStatus === "imputed" ? " (imputed from estimated arm sizes)" : ""}` : "No SE in the report, so no interval",
      },
      {
        row: "Bias-adjusted", est: e.adjusted, lo: e.adjustedLo, hi: e.adjustedHi,
        source: "model",
        note: `Reported g minus bias ${has(e.bias) ? fmt(e.bias) : "n/a"}; interval from the correction model${f.uImputed ? ", u imputed from design" : ""}${e.extrapolated ? ", extrapolated" : ""}`,
      },
    ],
    note: "Reported interval is computed in the browser as g ± 1.96 × se_g from the report. Bias-adjusted estimate and interval are the report's correction values. Values rounded to 3 decimals in the report.",
  };
}

export function EffectChart({ e, flags }: { e: Effect; flags: EffectFlags }) {
  const { ref, w: W } = useWidth(620);
  const { tip, markProps } = usePointTip();

  const vals = [e.reported, e.reportedLo, e.reportedHi, e.adjusted, e.adjustedLo, e.adjustedHi, 0].filter(has);
  const { ticks, step } = niceTicks(Math.min(...vals), Math.max(...vals), 4);
  const lo = ticks[0], hi = ticks[ticks.length - 1];
  const dp = Math.max(1, decimals(step));
  const tickText = (v: number) => fmt(Math.abs(v) < 1e-9 ? 0 : v, dp);

  // Wide: label column left, estimate column right. Narrow: label above each bar, estimate under it.
  const narrow = W < 520;
  const L = narrow ? 8 : 150;
  const R = narrow ? 8 : 168;
  const top = 26; // room for the "No effect" label
  const rowY = narrow ? [top + 30, top + 128] : [top + 22, top + 104];
  const axisY = rowY[1] + (narrow ? 44 : 30);
  const H = axisY + 58;
  const x = (v: number) => L + ((v - lo) / (hi - lo)) * (W - L - R);
  const x0 = x(0);

  const rows = [
    {
      key: "rep", label: "Reported", flag: flags.reportedImputed ? "imputed" : "",
      color: VIOLET, shape: "square" as const, hollow: flags.reportedImputed,
      mid: e.reported, a: e.reportedLo, b: e.reportedHi, y: rowY[0],
      sub: has(e.reportedLo) ? (e.seStatus === "imputed" ? "95% CI from imputed SE" : "95% CI") : "No interval reported",
      tip: has(e.reported)
        ? `Reported: ${fmt(e.reported)}${has(e.reportedLo) && has(e.reportedHi) ? `, 95% interval ${fmt(e.reportedLo)} to ${fmt(e.reportedHi)}` : ""}, standardised mean difference${flags.reportedImputed ? ", imputed from estimated arm sizes" : ""}`
        : "",
    },
    {
      key: "adj", label: "Bias-adjusted", flag: flags.uImputed ? "u imputed" : "",
      color: ORANGE, shape: "circle" as const, hollow: false,
      mid: e.adjusted, a: e.adjustedLo, b: e.adjustedHi, y: rowY[1],
      sub: has(e.adjustedLo) ? "95% CI from the correction model" : "No interval",
      tip: has(e.adjusted)
        ? `Bias-adjusted: ${fmt(e.adjusted)}${has(e.adjustedLo) && has(e.adjustedHi) ? `, 95% interval ${fmt(e.adjustedLo)} to ${fmt(e.adjustedHi)}` : ""}, standardised mean difference${flags.uImputed ? ", unblinding u imputed" : ""}`
        : "",
    },
  ];

  // Connector: down from the reported point, across by the estimated bias, down into the adjusted point.
  const conn = has(e.reported) && has(e.adjusted) ? { x1: x(e.reported), x2: x(e.adjusted) } : null;
  const midY = narrow ? rowY[0] + 50 : (rowY[0] + rowY[1]) / 2;
  const biasText = has(e.bias) ? `Estimated bias ${fmt(e.bias)}` : "";
  // Label sits above the horizontal run, ending just short of the reported point's drop line (or starting after it).
  const leftward = conn ? conn.x2 <= conn.x1 : true;
  const biasX = conn ? (leftward ? conn.x1 - 6 : conn.x1 + 6) : 0;

  return (
    <div ref={ref} className="st-forest">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} focusable="false">
        <defs>
          <marker id="st-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L8 4 L0 8 z" className="st-arrowhead" />
          </marker>
        </defs>
        {ticks.map((t) => (
          <line key={`g${t}`} x1={x(t)} x2={x(t)} y1={top} y2={axisY} className="st-grid" />
        ))}
        <line x1={x0} x2={x0} y1={top - 6} y2={axisY} className="st-null" />
        <text x={x0} y={top - 12} textAnchor="middle" className="st-label st-label--ref">No effect</text>

        {conn ? (
          <g className="st-conn" aria-hidden="true">
            <polyline
              points={`${conn.x1},${rowY[0] + 8} ${conn.x1},${midY} ${conn.x2},${midY} ${conn.x2},${rowY[1] - 9}`}
              fill="none"
              markerEnd="url(#st-arrow)"
            />
            {biasText ? (
              <text x={biasX} y={midY - 6} textAnchor={leftward ? "end" : "start"} className="st-label st-label--conn st-halo">{biasText}</text>
            ) : null}
          </g>
        ) : null}

        {rows.map((r) => {
          const labelX = narrow ? L : 0;
          const labelY = narrow ? r.y - 16 : r.y - 2;
          return (
            <g key={r.key}>
              <text x={labelX} y={labelY} className="st-row st-halo">
                {r.label}
                {r.flag && !narrow ? <tspan className="st-flag">{` (${r.flag})`}</tspan> : null}
              </text>
              {!narrow ? (
                <text x={labelX} y={labelY + 16} className="st-sub">{r.sub}</text>
              ) : null}
              {has(r.a) && has(r.b) ? (
                <g>
                  <line x1={x(r.a)} x2={x(r.b)} y1={r.y} y2={r.y} strokeWidth={2} style={{ stroke: r.color }} />
                  <line x1={x(r.a)} x2={x(r.a)} y1={r.y - 5} y2={r.y + 5} strokeWidth={2} style={{ stroke: r.color }} />
                  <line x1={x(r.b)} x2={x(r.b)} y1={r.y - 5} y2={r.y + 5} strokeWidth={2} style={{ stroke: r.color }} />
                </g>
              ) : null}
              {has(r.mid) ? (
                <g {...markProps(x(r.mid), r.y, r.tip)}>
                  <title>{r.tip}</title>
                  <circle cx={x(r.mid)} cy={r.y} r={14} className="st-hit" />
                  {r.shape === "square" ? (
                    <rect
                      x={x(r.mid) - 6} y={r.y - 6} width={12} height={12}
                      style={r.hollow ? { fill: "var(--color-eggshell)", stroke: r.color, strokeWidth: 2 } : { fill: r.color }}
                    />
                  ) : (
                    <circle cx={x(r.mid)} cy={r.y} r={6.5} style={{ fill: r.color, stroke: "var(--color-eggshell)", strokeWidth: 1.5 }} />
                  )}
                </g>
              ) : null}
              {narrow ? (
                <text x={L} y={r.y + 24} className="st-value st-halo">
                  {bracket(r.mid, r.a, r.b)}
                  {r.flag ? <tspan className="st-flag">{`, ${r.flag}`}</tspan> : null}
                </text>
              ) : (
                <>
                  <text x={W} y={r.y - 2} textAnchor="end" className="st-value">{bracket(r.mid, r.a, r.b)}</text>
                </>
              )}
            </g>
          );
        })}
        {!narrow ? (
          <text x={W} y={top - 12} textAnchor="end" className="st-label">g [95% CI]</text>
        ) : null}

        <line x1={L} x2={W - R} y1={axisY} y2={axisY} className="st-axis" />
        {ticks.map((t) => (
          <g key={`t${t}`}>
            <line x1={x(t)} x2={x(t)} y1={axisY} y2={axisY + 4} className="st-axis" />
            <text x={x(t)} y={axisY + 18} textAnchor="middle" className="st-tick">{tickText(t)}</text>
          </g>
        ))}
        <text x={L} y={axisY + 38} textAnchor="start" className="st-label st-label--dir">&larr; Favours control</text>
        <text x={W - R} y={axisY + 38} textAnchor="end" className="st-label st-label--dir">Favours drug &rarr;</text>
        <text x={L + (W - L - R) / 2} y={axisY + 56} textAnchor="middle" className="st-label">
          Hedges&rsquo; g (standardised mean difference)
        </text>
      </svg>
      <TipBubble tip={tip} width={W} />
    </div>
  );
}
