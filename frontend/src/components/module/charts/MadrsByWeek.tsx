/**
 * MadrsByWeek (docs/visuals-spec.md, "madrs-by-week"): pooled, still-blinded mean MADRS per visit week.
 *
 * The means come from the postdose view. The view does not send n or spread, so they are recomputed in the
 * frontend from the record with the view's own filter (`postdose/module.py` `_charts`: outcomes with `madrs` and
 * `visit_week`, plus follow-ups with `madrs`). A week's SD whisker is drawn only when the recomputed mean matches
 * the view's mean, so both describe the same scores. A week with fewer than half the largest n gets a hollow
 * marker and a note saying why the visits are missing (from the follow-up statuses). No arm split: blinded.
 */
import type { Outcome } from "../../../types";
import { ChartFrame, chartTokens, useRecordSections } from "../../shared";
import type { DataTable } from "../../shared";
import { ChartTip, useTip, useWidth, type ModuleChartComponentProps } from "./EffectForest";
import "./postdose.css";

export type { ModuleChartComponentProps } from "./EffectForest";

interface Week {
  week: number;
  mean: number;
  n: number | null;
  sd: number | null;
  /** follow-ups for this week with no score yet, by status */
  pending: Record<string, number>;
  low: boolean;
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);
const f1 = (v: number) => v.toFixed(1);

export function MadrsByWeek({ chart, trialId, height }: ModuleChartComponentProps): JSX.Element {
  const [boxRef, width] = useWidth<HTMLDivElement>();
  const { data: rec } = useRecordSections(trialId, ["outcomes", "followups"]);
  const { tip, show, hide, toggle } = useTip(boxRef, rec);

  const key = chart.series[0]?.key ?? "All participants";
  const xKey = chart.x || "week";

  // Recompute n and SD per week from the record, with the view's filter.
  const scores = new Map<number, number[]>();
  const pendingBy = new Map<number, Record<string, number>>();
  if (rec) {
    for (const o of (rec.outcomes ?? []) as Outcome[]) {
      const m = num(o.madrs);
      const w = num(o.visit_week);
      if (m !== null && w !== null) scores.set(w, [...(scores.get(w) ?? []), m]);
    }
    for (const f of (rec.followups ?? []) as Array<Record<string, unknown>>) {
      const w = num(f.visit_week);
      if (w === null) continue;
      const m = num(f.madrs);
      if (m !== null) scores.set(w, [...(scores.get(w) ?? []), m]);
      else {
        const st = String(f.status ?? "not done").replace(/_/g, " ");
        const p = pendingBy.get(w) ?? {};
        p[st] = (p[st] ?? 0) + 1;
        pendingBy.set(w, p);
      }
    }
  }

  const weeks: Week[] = chart.data
    .map((r) => ({ week: num(r[xKey]), mean: num(r[key]) }))
    .filter((r): r is { week: number; mean: number } => r.week !== null && r.mean !== null)
    .sort((a, b) => a.week - b.week)
    .map(({ week, mean }) => {
      const xs = scores.get(week);
      let n: number | null = null;
      let sd: number | null = null;
      if (xs && xs.length) {
        const mu = xs.reduce((s, x) => s + x, 0) / xs.length;
        // Same scores as the view only if the recomputed mean rounds to the view's mean.
        if (Math.abs(Math.round(mu * 10) / 10 - mean) < 0.051) {
          n = xs.length;
          if (xs.length >= 2) sd = Math.sqrt(xs.reduce((s, x) => s + (x - mu) ** 2, 0) / (xs.length - 1));
        }
      }
      return { week, mean, n, sd, pending: pendingBy.get(week) ?? {}, low: false };
    });
  const maxN = Math.max(0, ...weeks.map((w) => w.n ?? 0));
  for (const w of weeks) w.low = w.n !== null && maxN > 0 && w.n < maxN / 2;
  const hasSd = weeks.some((w) => w.sd !== null);

  const pendingText = (w: Week) => {
    const parts = Object.entries(w.pending).map(([k, c]) => `${c} ${k === "after close" ? `visit${c === 1 ? "" : "s"} due after the trial closed` : k}`);
    return parts.length ? parts.join(", ") : "fewer visits so far";
  };

  const first = weeks[0];
  const lastW = weeks[weeks.length - 1];
  const title = first && lastW && weeks.length > 1
    ? `Mean MADRS ${f1(first.mean)} at week ${first.week} and ${f1(lastW.mean)} at week ${lastW.week}${lastW.n !== null ? ` (n = ${lastW.n})` : ""}, both arms pooled`
    : first ? `Mean MADRS ${f1(first.mean)} at week ${first.week}, both arms pooled` : "Mean MADRS by visit week, both arms pooled";
  const subtitle = `MADRS total score (0 to 60), mean per visit week, both arms pooled because the trial is still blinded${hasSd ? ". Whiskers show ± 1 SD of individual scores, not an interval for the mean" : ""}.`;

  const lowWeeks = weeks.filter((w) => w.low);
  const footnotes = (
    <>
      {lowWeeks.map((w) => (
        <p key={w.week}>{`Week ${w.week}: n = ${w.n} against up to ${maxN} at other visits (${pendingText(w)}), so its mean is less certain. Hollow marker.`}</p>
      ))}
      {rec ? null : <p>Visit counts are loading.</p>}
    </>
  );

  const dataTable: DataTable = {
    columns: [
      { key: "week", label: "Visit week", align: "right" },
      { key: "n", label: "n (scores)", align: "right", derived: true },
      { key: "mean", label: "Mean MADRS", align: "right" },
      { key: "sd", label: "SD", align: "right", derived: true },
      { key: "pending", label: "Visits without a score", derived: true },
    ],
    rows: weeks.map((w) => ({
      week: w.week, n: w.n, mean: f1(w.mean), sd: w.sd !== null ? f1(w.sd) : null,
      pending: Object.keys(w.pending).length ? pendingText(w) : "none",
    })),
    note: "Mean from the postdose view. n, SD and visits without a score are counted in the browser from the trial record (outcomes and follow-ups with a MADRS score, the view's own filter); n and SD are shown only where the recomputed mean matches the view.",
  };

  const aria = `Mean MADRS by visit week, both arms pooled. ${weeks.map((w) => `Week ${w.week}: ${f1(w.mean)}${w.n !== null ? `, n = ${w.n}` : ""}${w.sd !== null ? `, SD ${f1(w.sd)}` : ""}`).join("; ")}.`;

  // Layout
  const narrow = width > 0 && width < 560;
  const padL = 44;
  const padR = narrow ? 42 : 52;
  const top = 30;
  const plotH = Math.max(150, (height ?? 240) - 60);
  const bottom = top + plotH;
  const H = bottom + 46;
  const [y0, y1] = chart.yDomain ?? [0, 60];
  const wMin = Math.min(...weeks.map((w) => w.week), first?.week ?? 0);
  const wMax = Math.max(...weeks.map((w) => w.week), wMin + 1);
  const span = Math.max(1, wMax - wMin);
  const plotX0 = padL + 14;
  const plotX1 = Math.max(plotX0 + 60, width - padR);
  const sx = (w: number) => plotX0 + ((w - wMin) / span) * (plotX1 - plotX0);
  const sy = (v: number) => bottom - ((v - y0) / (y1 - y0)) * plotH;
  const yTicks: number[] = [];
  const yStep = (y1 - y0) / 4;
  for (let v = y0; v <= y1 + 1e-9; v += yStep) yTicks.push(Math.round(v * 10) / 10);

  const tipFor = (w: Week) => ({
    key: String(w.week),
    x: sx(w.week),
    y: sy(w.mean) + 14,
    text: `Week ${w.week}: mean MADRS ${f1(w.mean)}${w.n !== null ? `, n = ${w.n}` : ""}${w.sd !== null ? `, SD ${f1(w.sd)}` : ""}${w.low ? `; fewer scores (${pendingText(w)})` : ""}.`,
  });

  return (
    <ChartFrame
      interactive
      id="madrs-by-week"
      title={title}
      subtitle={subtitle}
      ariaLabel={aria}
      dataTable={dataTable}
      dataTitle="Data: mean MADRS by visit week"
      footnotes={footnotes}
      empty={weeks.length === 0 ? { title: "No MADRS visits yet" } : null}
    >
      <div className="pd-chart" ref={boxRef} onPointerLeave={(e) => { if (e.pointerType === "mouse") hide(); }}>
        {width > 0 ? (
          <svg className="pd-svg" width={width} height={H} viewBox={`0 0 ${width} ${H}`} aria-hidden="true" focusable="false">
            {yTicks.map((t) => (
              <g key={`y${t}`}>
                <line x1={plotX0 - 8} x2={plotX1 + 8} y1={sy(t)} y2={sy(t)} stroke={chartTokens.grid} />
                <text className="pd-tick" x={plotX0 - 14} y={sy(t) + 4} textAnchor="end">{t}</text>
              </g>
            ))}
            <text className="pd-axis-title" x={4} y={top - 16} textAnchor="start">MADRS total (0 to 60)</text>

            {/* straight segments between visits; the one into a low-n visit is dashed */}
            {weeks.slice(1).map((w, i) => {
              const p = weeks[i];
              return (
                <line key={`s${w.week}`} x1={sx(p.week)} y1={sy(p.mean)} x2={sx(w.week)} y2={sy(w.mean)}
                  stroke={chartTokens.primary} strokeWidth={1.5} strokeDasharray={w.low || p.low ? "4 3" : undefined} />
              );
            })}

            {weeks.map((w) => {
              const cx = sx(w.week);
              const cy = sy(w.mean);
              const t = tipFor(w);
              return (
                <g key={`p${w.week}`}
                  className="pd-point"
                  tabIndex={0}
                  role="button"
                  aria-label={t.text}
                  onPointerEnter={(e) => { if (e.pointerType === "mouse") show(t); }}
                  onClick={() => toggle(t)}
                  onFocus={(e) => { if (e.currentTarget.matches(":focus-visible")) show(t); }}
                  onBlur={hide}
                >
                  <rect x={cx - 16} y={top} width={32} height={plotH} fill="transparent" />
                  {w.sd !== null ? (
                    <g stroke={chartTokens.primary} strokeOpacity={0.8} strokeWidth={1.25}>
                      <line x1={cx} x2={cx} y1={sy(Math.min(y1, w.mean + w.sd))} y2={sy(Math.max(y0, w.mean - w.sd))} />
                      <line x1={cx - 4} x2={cx + 4} y1={sy(Math.min(y1, w.mean + w.sd))} y2={sy(Math.min(y1, w.mean + w.sd))} />
                      <line x1={cx - 4} x2={cx + 4} y1={sy(Math.max(y0, w.mean - w.sd))} y2={sy(Math.max(y0, w.mean - w.sd))} />
                    </g>
                  ) : null}
                  <circle className="pd-ring" cx={cx} cy={cy} r={9} />
                  <circle cx={cx} cy={cy} r={5} fill={w.low ? chartTokens.halo : chartTokens.primary}
                    stroke={w.low ? chartTokens.primary : chartTokens.halo} strokeWidth={2} />
                  <text className="pd-val" x={cx + 9} y={cy - 7} textAnchor="start">{f1(w.mean)}</text>
                </g>
              );
            })}

            {/* x axis: ticks exactly at the visit weeks, n under each */}
            <line x1={plotX0 - 8} x2={plotX1 + 8} y1={bottom} y2={bottom} stroke={chartTokens.axis} />
            {weeks.map((w) => (
              <g key={`x${w.week}`}>
                <line x1={sx(w.week)} x2={sx(w.week)} y1={bottom} y2={bottom + 4} stroke={chartTokens.axis} />
                <text className="pd-tick" x={sx(w.week)} y={bottom + 17} textAnchor="middle">{narrow ? `W${w.week}` : `Week ${w.week}`}</text>
                <text className={`pd-n${w.low ? " pd-n--low" : ""}`} x={sx(w.week)} y={bottom + 33} textAnchor="middle">
                  {w.n !== null ? `n = ${w.n}` : ""}
                </text>
              </g>
            ))}
          </svg>
        ) : null}
        <ChartTip tip={tip} width={width} />
      </div>
    </ChartFrame>
  );
}
