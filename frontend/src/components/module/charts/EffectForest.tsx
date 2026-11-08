/**
 * EffectForest (docs/visuals-spec.md, "effect-estimates"): the Follow-up key chart as a forest plot.
 *
 * One row per estimate the postdose view sends (`estimate`, `md`, `lo`, `hi`; rows with no estimate are not
 * sent). x = mean difference in MADRS points, drug minus control, so a negative value favours the drug. The axis
 * always includes 0 ("No effect", solid) and the planted truth (dotted) when the payload carries it; the planted
 * truth is a simulator constant and is labelled "simulated". The record's `report.effect` is read only for
 * footnotes (arm sizes, the primary week, why a method has no estimate), never for the plotted values.
 *
 * Also exports the small SVG helpers shared by the other POSTDOSE charts (useWidth, useTip, ChartTip), so the
 * three files stay inside POSTDOSE's ownership.
 */
import { useCallback, useEffect, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";
import { ChartFrame, chartTokens, formatSigned, useRecordSections } from "../../shared";
import type { DataTable } from "../../shared";
import type { Chart } from "../normalise";
import "./postdose.css";

export interface ModuleChartComponentProps {
  chart: Chart;
  trialId: string;
  height?: number;
}

/* ------------------------------------------------------------------ shared SVG helpers (POSTDOSE) */

/** Width of a container in px, tracked with a ResizeObserver. */
export function useWidth<T extends HTMLElement>(): [RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.clientWidth);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setW(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

export interface Tip {
  x: number;
  y: number;
  text: string;
  key: string;
}

/**
 * Tooltip state for a hand-drawn chart. Hover and focus open it; a tap toggles it; a tap outside the chart or
 * a scroll closes it, so it never sticks on a phone.
 */
export function useTip(boxRef: RefObject<HTMLElement>, data?: unknown) {
  const [tip, setTip] = useState<Tip | null>(null);
  // New data: close the tooltip so it never shows text from the previous fetch.
  useEffect(() => setTip(null), [data]);
  const show = useCallback((t: Tip) => setTip(t), []);
  const hide = useCallback(() => setTip(null), []);
  const toggle = useCallback((t: Tip) => setTip((cur) => (cur && cur.key === t.key ? null : t)), []);
  useEffect(() => {
    if (!tip) return;
    const outside = (e: PointerEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setTip(null);
    };
    const scroll = () => setTip(null);
    document.addEventListener("pointerdown", outside);
    window.addEventListener("scroll", scroll, { passive: true, capture: true });
    return () => {
      document.removeEventListener("pointerdown", outside);
      window.removeEventListener("scroll", scroll, { capture: true });
    };
  }, [tip, boxRef]);
  return { tip, show, hide, toggle };
}

/** The tooltip box: one sentence in words, kept inside the chart's width. */
export function ChartTip({ tip, width }: { tip: Tip | null; width: number }) {
  if (!tip) return null;
  const maxW = Math.min(280, Math.max(160, width - 16));
  const left = Math.max(4, Math.min(tip.x - maxW / 2, width - maxW - 4));
  return (
    <div className="pd-tip" role="status" style={{ left, top: tip.y, maxWidth: maxW }}>
      {tip.text}
    </div>
  );
}

/** Round a step to 1, 2 or 5 times a power of ten. */
export function niceStep(span: number, target: number): number {
  const raw = span / Math.max(1, target);
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const m = raw / p;
  return (m <= 1 ? 1 : m <= 2 ? 2 : m <= 5 ? 5 : 10) * p;
}

/** Nice-rounded domain with ticks; includes 0 when asked. */
export function niceTicks(values: number[], includeZero: boolean, target: number): { domain: [number, number]; ticks: number[] } {
  const vs = includeZero ? [...values, 0] : values;
  let lo = Math.min(...vs);
  let hi = Math.max(...vs);
  if (!(hi > lo)) { lo -= 1; hi += 1; }
  const step = niceStep(hi - lo, target);
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const ticks: number[] = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(Math.round(v / step) * step);
  return { domain: [lo, hi], ticks };
}

/** Number with Unicode minus and fixed digits ("−6.41"). */
export function fmt(v: number, digits = 2): string {
  return formatSigned(v, digits).replace(/^\+/, "");
}

/* ------------------------------------------------------------------ data */

interface Row {
  name: string;
  md: number;
  lo: number;
  hi: number;
  reported: boolean;
}

interface EffectPart {
  md?: number | null;
  n_drug?: number;
  n_control?: number;
  why_missing?: string;
  method?: string;
}

const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

function readRows(chart: Chart): Row[] {
  const out: Row[] = [];
  for (const r of chart.data) {
    const md = num(r.md);
    const lo = num(r.lo);
    const hi = num(r.hi);
    if (md === null || lo === null || hi === null) continue;
    const name = String(r[chart.x] ?? r.estimate ?? "Estimate");
    out.push({ name, md, lo, hi, reported: /^reported/i.test(name) });
  }
  return out;
}

/** The planted truth, only when the payload carries it (as a ref, or as a constant column on every row). */
function readTruth(chart: Chart): number | null {
  const ref = chart.refs.find((r) => /truth/i.test(r.label));
  if (ref) return ref.y;
  const key = Object.keys(chart.data[0] ?? {}).find((k) => /truth/i.test(k));
  if (!key) return null;
  const vals = chart.data.map((r) => num(r[key]));
  if (vals.some((v) => v === null)) return null;
  return vals.every((v) => Math.abs((v as number) - (vals[0] as number)) < 1e-9) ? vals[0] : null;
}

/** Sign convention from the payload's own title. The postdose view says "negative favours the drug". */
function negativeFavoursDrug(chart: Chart): boolean {
  const t = `${chart.title} ${chart.titleNote ?? ""}`;
  if (/positive favours the drug/i.test(t)) return false;
  return true;
}

const crosses = (r: Row) => r.lo <= 0 && r.hi >= 0;
const lower = (s: string) => s.charAt(0).toLowerCase() + s.slice(1);

/* ------------------------------------------------------------------ component */

export function EffectForest({ chart, trialId }: ModuleChartComponentProps): JSX.Element {
  const [boxRef, width] = useWidth<HTMLDivElement>();
  const { data: rec } = useRecordSections(trialId, ["report"]);
  const { tip, show, hide, toggle } = useTip(boxRef, rec);
  const effect = ((rec?.report as Record<string, unknown> | null | undefined)?.effect ?? null) as Record<string, unknown> | null;

  const rows = readRows(chart);
  const truth = readTruth(chart);
  const negDrug = negativeFavoursDrug(chart);
  const adjusted = rows.filter((r) => !r.reported);
  const rep = rows.find((r) => r.reported) ?? null;
  const last = adjusted[adjusted.length - 1] ?? null;

  // Title: computed from the data, falls back to neutral wording if a piece is missing.
  let title = "Effect on MADRS under each analysis";
  if (rep && last) {
    title = `Reported ${fmt(rep.md)} MADRS points; after ${lower(last.name)} ${fmt(last.md)}, interval ${crosses(last) ? "crosses" : "does not cross"} 0`;
  } else if (rep) {
    title = `Reported ${fmt(rep.md)} MADRS points, interval ${crosses(rep) ? "crosses" : "does not cross"} 0`;
  }
  const week = num(effect?.primary_week);
  const subtitle = `Mean difference in MADRS points${week !== null ? ` at week ${week}` : ""}, drug minus control, with 95% intervals. ${negDrug ? "Negative" : "Positive"} favours the drug.`;

  // Footnotes from the record (only what is there).
  const notes: ReactNode[] = [];
  const reported = (effect?.reported ?? null) as EffectPart | null;
  if (reported && typeof reported.n_drug === "number" && typeof reported.n_control === "number") {
    notes.push(`Reported estimate: ${reported.n_drug} on drug, ${reported.n_control} on control.`);
  }
  const missingNames: Record<string, string> = {
    within_trial: "Within-trial (patient guess)",
    within_trial_rater: "Within-trial (patient and rater guess)",
    cross_trial: "Cross-trial calibration",
  };
  // Methods with no estimate, grouped by the record's own reason.
  const byWhy = new Map<string, string[]>();
  for (const [k, label] of Object.entries(missingNames)) {
    const e = (effect?.[k] ?? null) as EffectPart | null;
    if (e && (e.md === null || e.md === undefined) && !rows.some((r) => r.name === label)) {
      const why = e.why_missing ?? "";
      byWhy.set(why, [...(byWhy.get(why) ?? []), label]);
    }
  }
  for (const [why, labels] of byWhy) {
    const names = labels.map(lower).join(" and ");
    notes.push(`Not drawn: ${names}, not estimable${why ? ` because ${why}` : ""}.`);
  }
  if (truth !== null) {
    notes.push(`Planted truth ${fmt(truth, 1)} is the effect the simulator was given. A real trial has no such line.`);
  }

  const dataTable: DataTable = {
    columns: [
      { key: "estimate", label: "Estimate" },
      { key: "md", label: "Mean difference (MADRS points)", align: "right" },
      { key: "lo", label: "95% low", align: "right" },
      { key: "hi", label: "95% high", align: "right" },
      { key: "crosses", label: "Interval crosses 0", align: "left", derived: true },
      ...(truth !== null ? [{ key: "truth", label: "Planted truth (simulated)", align: "right" as const }] : []),
    ],
    rows: rows.map((r) => ({
      estimate: r.name, md: fmt(r.md), lo: fmt(r.lo), hi: fmt(r.hi), crosses: crosses(r) ? "Yes" : "No",
      ...(truth !== null ? { truth: fmt(truth, 1) } : {}),
    })),
    note: "From the postdose view's effect estimates, drug minus control. \"Interval crosses 0\" is read off the interval.",
  };

  const aria = `Forest plot of the effect on MADRS, ${negDrug ? "negative" : "positive"} favours the drug. `
    + rows.map((r) => `${r.name}: ${fmt(r.md)} (95% interval ${fmt(r.lo)} to ${fmt(r.hi)}, ${crosses(r) ? "crosses" : "does not cross"} 0)`).join("; ")
    + "." + (truth !== null ? ` Planted truth (simulated) ${fmt(truth, 1)}.` : "");

  // Layout. Wide: label column, plot, estimate column. Narrow: label and estimate above each bar.
  const narrow = width > 0 && width < 560;
  const labelW = narrow ? 0 : Math.min(230, Math.max(150, width * 0.24));
  const estW = narrow ? 0 : 168;
  const padL = narrow ? 12 : 12;
  const padR = narrow ? 12 : 16;
  const plotX0 = labelW + padL;
  const plotX1 = Math.max(plotX0 + 80, width - estW - padR);
  const rowH = narrow ? 64 : 48;
  const top = 30;
  const plotH = rows.length * rowH;
  const axisY = top + plotH + 6;
  const H = axisY + 62;

  const vals = rows.flatMap((r) => [r.lo, r.hi]).concat(truth !== null ? [truth] : []);
  const { domain, ticks } = niceTicks(vals.length ? vals : [0], true, narrow ? 5 : 8);
  const sx = (v: number) => plotX0 + ((v - domain[0]) / (domain[1] - domain[0])) * (plotX1 - plotX0);
  const x0 = sx(0);

  const leftWord = negDrug ? "Favours drug" : "Favours control";
  const rightWord = negDrug ? "Favours control" : "Favours drug";

  const tipFor = (r: Row, cy: number) => ({
    key: r.name,
    x: sx(r.md),
    y: cy + 14,
    text: `${r.name}: ${fmt(r.md)} MADRS points, 95% interval ${fmt(r.lo)} to ${fmt(r.hi)}, ${crosses(r) ? "crosses" : "does not cross"} 0.`,
  });

  return (
    <ChartFrame
      interactive
      id="effect-estimates"
      title={title}
      subtitle={subtitle}
      ariaLabel={aria}
      dataTable={dataTable}
      dataTitle="Data: effect estimates"
      footnotes={notes.length ? <>{notes.map((n, i) => <p key={i}>{n}</p>)}</> : undefined}
      empty={rows.length === 0 ? { title: "No effect estimates yet", body: "Effect estimates appear once the primary endpoint is locked." } : null}
    >
      <div className="pd-chart" ref={boxRef} onPointerLeave={(e) => { if (e.pointerType === "mouse") hide(); }}>
        {width > 0 ? (
          <svg className="pd-svg" width={width} height={H} viewBox={`0 0 ${width} ${H}`} aria-hidden="true" focusable="false">
            {/* gridlines at ticks */}
            {ticks.map((t) => (
              <line key={`g${t}`} x1={sx(t)} x2={sx(t)} y1={top - 4} y2={axisY} stroke={chartTokens.grid} strokeWidth={1} />
            ))}
            {/* planted truth, dotted, labelled simulated */}
            {truth !== null ? (
              <g>
                <line x1={sx(truth)} x2={sx(truth)} y1={top - 6} y2={axisY} stroke={chartTokens.reference} strokeWidth={1.25} strokeDasharray="1 3" />
                <text className="pd-ref" x={truth < 0 ? sx(truth) - 5 : sx(truth) + 5} y={top - 12} textAnchor={truth < 0 ? "end" : "start"}>
                  {narrow ? `Truth (simulated) ${fmt(truth, 1)}` : `Planted truth (simulated) ${fmt(truth, 1)}`}
                </text>
              </g>
            ) : null}
            {/* no effect, solid */}
            <line x1={x0} x2={x0} y1={top - 6} y2={axisY} stroke={chartTokens.reference} strokeWidth={1} />
            <text className="pd-ref" x={truth !== null && truth > 0 ? x0 - 5 : x0 + 5} y={top - 12} textAnchor={truth !== null && truth > 0 ? "end" : "start"}>
              No effect
            </text>

            {!narrow ? (
              <text className="pd-axis-title" x={width - 4} y={top - 12} textAnchor="end">Mean difference [95% CI]</text>
            ) : null}
            {rows.map((r, i) => {
              const cy = top + i * rowH + (narrow ? rowH - 18 : rowH / 2);
              const color = r.reported ? chartTokens.primary : chartTokens.flag;
              const est = `${fmt(r.md)} [${fmt(r.lo)}, ${fmt(r.hi)}]`;
              const t = tipFor(r, cy);
              return (
                <g key={r.name}>
                  {narrow ? (
                    <>
                      <text className="pd-rowlabel pd-halo" x={plotX0 - padL + 12} y={cy - 18}>{r.name}</text>
                      <rect x={width - padR - est.length * 6.9 - 6} y={cy - 32} width={est.length * 6.9 + 10} height={19} fill="var(--color-taupe)" />
                      <text className="pd-est pd-halo" x={width - padR} y={cy - 18} textAnchor="end">{est}</text>
                    </>
                  ) : (
                    <>
                      <text className="pd-rowlabel" x={4} y={cy + 4}>{r.name}</text>
                      <text className="pd-est" x={width - 4} y={cy + 4} textAnchor="end">{est}</text>
                    </>
                  )}
                  <g
                    className="pd-point"
                    tabIndex={0}
                    role="button"
                    aria-label={t.text}
                    onPointerEnter={(e) => { if (e.pointerType === "mouse") show(t); }}
                    onClick={() => toggle(t)}
                    onFocus={(e) => { if (e.currentTarget.matches(":focus-visible")) show(t); }}
                    onBlur={hide}
                  >
                    <rect x={sx(r.lo) - 6} y={cy - 14} width={sx(r.hi) - sx(r.lo) + 12} height={28} fill="transparent" />
                    <line x1={sx(r.lo)} x2={sx(r.hi)} y1={cy} y2={cy} stroke={color} strokeWidth={2} />
                    <line x1={sx(r.lo)} x2={sx(r.lo)} y1={cy - 5} y2={cy + 5} stroke={color} strokeWidth={2} />
                    <line x1={sx(r.hi)} x2={sx(r.hi)} y1={cy - 5} y2={cy + 5} stroke={color} strokeWidth={2} />
                    <circle className="pd-ring" cx={sx(r.md)} cy={cy} r={10.5} />
                    {r.reported ? (
                      <rect x={sx(r.md) - 6} y={cy - 6} width={12} height={12} fill={color} stroke={chartTokens.halo} strokeWidth={2} />
                    ) : (
                      <circle cx={sx(r.md)} cy={cy} r={6.5} fill={color} stroke={chartTokens.halo} strokeWidth={2} />
                    )}
                  </g>
                </g>
              );
            })}

            {/* axis */}
            <line x1={plotX0} x2={plotX1} y1={axisY} y2={axisY} stroke={chartTokens.axis} strokeWidth={1} />
            {ticks.map((t) => (
              <g key={`t${t}`}>
                <line x1={sx(t)} x2={sx(t)} y1={axisY} y2={axisY + 4} stroke={chartTokens.axis} />
                <text className="pd-tick" x={sx(t)} y={axisY + 17} textAnchor="middle">{fmt(t, Number.isInteger(t) ? 0 : 1)}</text>
              </g>
            ))}
            <text className="pd-axis-title" x={(plotX0 + plotX1) / 2} y={axisY + 36} textAnchor="middle">
              {narrow ? "MADRS points, drug minus control" : "Mean difference in MADRS points (drug minus control)"}
            </text>
            <text className="pd-dir" x={plotX0} y={axisY + 54} textAnchor="start">{`← ${leftWord}`}</text>
            <text className="pd-dir" x={plotX1} y={axisY + 54} textAnchor="end">{`${rightWord} →`}</text>
          </svg>
        ) : null}
        <ChartTip tip={tip} width={width} />
      </div>
    </ChartFrame>
  );
}
