/**
 * FixesChart (design-fixes): expected bias before and after each proposed design change, one row per change,
 * in the order the pipeline ranks them (score = bias reduction × feasibility). Feasibility and score are shown,
 * so a change that cuts slightly more bias but ranks lower is explained, not hidden.
 */
import type { Fix } from "./report";
import { fmt } from "./report";
import { wrap } from "./BlindingMeter";
import { niceTicks } from "./EffectChart";
import { TipBubble, usePointTip, useWidth } from "./PointTip";

const VIOLET = "var(--color-spark-violet)";
const has = (v: number | null): v is number => v !== null;

const lower = (s: string) => (s ? s[0].toLowerCase() + s.slice(1) : s);

export function fixesTitle(fx: Fix[]): string {
  const top = fx[0];
  if (!top || !has(top.before) || !has(top.after)) return "Design changes, as ranked by the report";
  return `${top.change} ranks first once feasibility is weighed (expected bias ${fmt(top.before, 3)} to ${fmt(top.after, 3)} g)`;
}

export function fixesSubtitle(fx: Fix[]): string {
  const base = "Expected bias in g before and after each change. Ranked by bias reduction × feasibility (score)";
  const top = fx[0];
  const bigger = fx.slice(1).find((f) => has(f.reduction) && has(top?.reduction) && f.reduction > (top.reduction as number));
  if (!top || !bigger) return `${base}.`;
  return `${base}. ${bigger.change} cuts slightly more (${fmt(bigger.reduction, 3)}) but is less feasible (${fmt(bigger.feasibility, 1)}).`;
}

export function fixesAria(fx: Fix[]): string {
  return `Design changes ranked by bias reduction times feasibility: ${fx
    .map((f) => `${lower(f.change)} ${fmt(f.before, 3)} to ${fmt(f.after, 3)}, feasibility ${fmt(f.feasibility, 1)}`)
    .join("; ")}.`;
}

export function fixesTable(fx: Fix[]) {
  return {
    columns: [
      { key: "rank", label: "Rank", align: "right" as const },
      { key: "change", label: "Change" },
      { key: "before", label: "Before (g)", align: "right" as const },
      { key: "after", label: "After (g)", align: "right" as const },
      { key: "reduction", label: "Reduction (g)", align: "right" as const },
      { key: "feasibility", label: "Feasibility (0 to 1)", align: "right" as const },
      { key: "score", label: "Score", align: "right" as const },
    ],
    rows: fx.map((f, i) => ({
      rank: i + 1, change: f.change, before: f.before, after: f.after,
      reduction: f.reduction, feasibility: f.feasibility, score: f.score,
    })),
    note: "From the report's counterfactuals, in the report's order. Score = reduction × feasibility.",
  };
}

function tipText(f: Fix): string {
  return `${f.change}: expected bias ${fmt(f.before, 3)} to ${fmt(f.after, 3)} g, reduction ${fmt(f.reduction, 3)}, feasibility ${fmt(f.feasibility, 1)}, score ${fmt(f.score, 3)}`;
}

export function FixesChart({ fx }: { fx: Fix[] }) {
  const { ref, w: W } = useWidth(620);
  const { tip, markProps } = usePointTip();
  const narrow = W < 520;
  const L = 24, R = narrow ? 10 : 200;
  const maxBefore = Math.max(0.1, ...fx.flatMap((f) => [f.before, f.after]).filter(has));
  const { ticks } = niceTicks(0, maxBefore, 4);
  const hi = ticks[ticks.length - 1];
  const x = (v: number) => L + (v / hi) * (W - L - R);

  const rows = fx.map((f) => ({ f, lines: wrap(f.change, (narrow ? W - L - R : W - L - 8), 7.2) }));
  let y = 22;
  const laid = rows.map((r, i) => {
    const labelY = y;
    const trackY = labelY + (r.lines.length - 1) * 16 + 24;
    const valueY = trackY + 24;
    y = (narrow ? valueY + 16 : trackY + 20) + (i === 0 ? 14 : 8);
    return { ...r, labelY, trackY, valueY };
  });
  const axisY = y;
  const H = axisY + 40;

  return (
    <div ref={ref} className="st-fixes">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} focusable="false">
        <defs>
          <marker id="st-arrow-fix" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L8 4 L0 8 z" className="st-arrowhead" />
          </marker>
        </defs>
        {ticks.map((t) => (
          <line key={`g${t}`} x1={x(t)} x2={x(t)} y1={12} y2={axisY} className="st-grid" />
        ))}
        {laid.map(({ f, lines, labelY, trackY, valueY }, i) => {
          const text = tipText(f);
          const bx = has(f.before) ? x(f.before) : null;
          const ax = has(f.after) ? x(f.after) : null;
          return (
            <g key={`${f.change}-${i}`}>
              <text x={0} y={labelY} className="st-sub">{i + 1}</text>
              <text x={L} y={labelY} className="st-row">
                {lines.map((ln, k) => <tspan key={k} x={L} dy={k ? 16 : 0}>{ln}</tspan>)}
              </text>
              {bx !== null && ax !== null && Math.abs(bx - ax) > 14 ? (
                <line x1={bx - (ax < bx ? 6 : -6)} x2={ax + (ax < bx ? 9 : -9)} y1={trackY} y2={trackY} className="st-conn-line" markerEnd="url(#st-arrow-fix)" />
              ) : null}
              <g {...markProps(((bx ?? 0) + (ax ?? 0)) / 2, trackY, text)}>
                <title>{text}</title>
                {bx !== null ? <circle cx={bx} cy={trackY} r={6} className="st-before" /> : null}
                {ax !== null ? <circle cx={ax} cy={trackY} r={6} style={{ fill: VIOLET, stroke: "var(--color-eggshell)", strokeWidth: 1.5 }} /> : null}
              </g>
              {i === 0 && bx !== null && ax !== null ? (
                <>
                  <text x={bx + 2} y={trackY - 11} textAnchor="start" className="st-label st-label--small">Before</text>
                  <text x={ax - 2} y={trackY - 11} textAnchor="end" className="st-label st-label--small">After</text>
                </>
              ) : null}
              {narrow ? (
                <text x={L} y={valueY} className="st-sub">
                  <tspan className="st-value-inline">{fmt(f.before, 3)} to {fmt(f.after, 3)} ({fmt(has(f.reduction) ? -f.reduction : null, 3)})</tspan>
                  {`, feasibility ${fmt(f.feasibility, 1)}, score ${fmt(f.score, 3)}`}
                </text>
              ) : (
                <text x={W} y={trackY + 4} textAnchor="end" className="st-sub">
                  <tspan className="st-value-inline">{fmt(f.before, 3)} to {fmt(f.after, 3)} ({fmt(has(f.reduction) ? -f.reduction : null, 3)})</tspan>
                  <tspan x={W} dy={16}>{`feasibility ${fmt(f.feasibility, 1)}, score ${fmt(f.score, 3)}`}</tspan>
                </text>
              )}
            </g>
          );
        })}
        <line x1={L} x2={W - R} y1={axisY} y2={axisY} className="st-axis" />
        {ticks.map((t) => (
          <g key={`t${t}`}>
            <line x1={x(t)} x2={x(t)} y1={axisY} y2={axisY + 4} className="st-axis" />
            <text x={x(t)} y={axisY + 18} textAnchor="middle" className="st-tick">{t === 0 ? "0" : fmt(t, 1)}</text>
          </g>
        ))}
        <text x={L + (W - L - R) / 2} y={axisY + 36} textAnchor="middle" className="st-label">Expected bias (g)</text>
      </svg>
      <TipBubble tip={tip} width={W} />
    </div>
  );
}
