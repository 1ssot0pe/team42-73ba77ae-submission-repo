/**
 * Chart parts (docs/visuals-spec.md 4.4), used with chartTheme.ts and ChartFrame.tsx.
 *
 * ChartTooltip: <Tooltip content={<ChartTooltip render={(row) => "Day 47, Site B: ..."} />} />
 *   One sentence in words, built by `render` from the hovered data row. Without `render` it falls back to
 *   "label: name value" pairs (legacy). Flat eggshell surface, tabular figures.
 * EndLabel: a direct label with a halo, for line ends and panel titles (replaces legends).
 *   Use inside an SVG (for example a recharts <Customized> or a LabelList content renderer).
 * EventMarkers: vertical event rules with labels "Alert D47" set in rows above the plot area, stacked so labels never
 *   overlap and never sit on data. Reserve top margin for them: eventsTopMargin(events.length).
 *   Use as <Customized component={(p) => <EventMarkers events={...} {...p} />} /> inside a recharts chart, or
 *   pass xScale/top/bottom yourself in hand-written SVG.
 * endpointDot(lastIndex): a recharts `dot` renderer that draws only the emphasised last point.
 * ChartFrame and its types are re-exported from ChartFrame.tsx so old imports keep working.
 */
import type { ReactNode } from "react";
import { chartTokens } from "./chartTheme";
import { formatDayTick } from "./chartFormat";
import { formatNumber } from "./format";

export { ChartFrame, ChartLegend, ChartDataTable } from "./ChartFrame";
export type { ChartFrameProps, ChartEmpty, ChartStatus, DataColumn, DataTable, Cell, LegendItem } from "./ChartFrame";

interface TooltipPayloadItem {
  name?: string | number;
  value?: unknown;
  color?: string;
  stroke?: string;
  dataKey?: unknown;
  payload?: unknown;
}

export interface ChartTooltipProps {
  active?: boolean;
  payload?: unknown[];
  label?: unknown;
  /** One sentence in words from the hovered row. Return "" to show nothing. */
  render?: (row: Record<string, unknown>) => string;
  /** legacy fallback: prefix for the label, e.g. "Day " */
  xLabel?: string;
  /** legacy fallback: digits for numbers */
  digits?: number;
}

export function ChartTooltip({ active, payload, label, render, xLabel = "", digits = 3 }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const items = payload as TooltipPayloadItem[];
  if (render) {
    const first = items[0]?.payload;
    const row = (first && typeof first === "object" ? first : {}) as Record<string, unknown>;
    const text = render(row);
    if (!text) return null;
    return <div className="chart-tooltip" role="status"><p className="chart-tooltip__text">{text}</p></div>;
  }
  return (
    <div className="chart-tooltip" role="status">
      <div className="chart-tooltip__label">{xLabel}{String(label ?? "")}</div>
      {items.map((p, i) => (
        <div key={i} className="chart-tooltip__row">
          <span>{String(p.name ?? p.dataKey ?? "")}</span>
          <span>{typeof p.value === "number" ? formatNumber(p.value, digits).replace(/^-/, "−") : String(p.value ?? "")}</span>
        </div>
      ))}
    </div>
  );
}

export interface EndLabelProps {
  x: number;
  y: number;
  text: string;
  color: string;
  /** "start" draws to the right of x (line ends), "end" to the left. Default "start". */
  anchor?: "start" | "middle" | "end";
  /** bold for the group of interest */
  weight?: 400 | 600;
}

/** Direct label with a halo so it stays legible over grid and lines. */
export function EndLabel({ x, y, text, color, anchor = "start", weight = 600 }: EndLabelProps) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return (
    <text
      className="chart-endlabel"
      x={anchor === "start" ? x + 6 : anchor === "end" ? x - 6 : x}
      y={y}
      dy="0.32em"
      textAnchor={anchor}
      fill={color}
      fontWeight={weight}
      stroke={chartTokens.halo}
      strokeWidth={4}
      strokeLinejoin="round"
      paintOrder="stroke"
    >
      {text}
    </text>
  );
}

export interface ChartEvent {
  day: number;
  /** label without the day, e.g. "Alert"; the day is appended as "D47" */
  label: string;
  /** true for a detected event: adds an orange 4px tick on the axis */
  detected?: boolean;
}

export interface EventMarkersProps {
  events: ChartEvent[];
  /** legacy knob: labels closer than this are stacked; the default (56) means "only when they would touch" */
  minGapPx?: number;
  /** recharts Customized passes these; hand-written SVG passes its own */
  xAxisMap?: Record<string, { scale?: (v: number) => number }>;
  offset?: { top?: number; height?: number; left?: number; width?: number };
  xScale?: (v: number) => number;
  top?: number;
  bottom?: number;
  /** px between stacked label rows (default 13) */
  lineHeight?: number;
}

/** Event rules plus labels "Onset est. D28", stacked when closer than minGapPx so labels never overlap. */
export function EventMarkers({
  events, minGapPx = 56, xAxisMap, offset, xScale, top, bottom, lineHeight = 13,
}: EventMarkersProps) {
  const scale = xScale ?? (xAxisMap ? Object.values(xAxisMap)[0]?.scale : undefined);
  if (!scale || events.length === 0) return null;
  const y0 = top ?? offset?.top ?? 0;
  const y1 = bottom ?? (offset ? (offset.top ?? 0) + (offset.height ?? 0) : y0 + 100);
  const left = offset?.left ?? -Infinity;
  const right = offset ? (offset.left ?? 0) + (offset.width ?? 0) : Infinity;

  const placed = [...events]
    .filter((e) => Number.isFinite(e.day))
    .sort((a, b) => a.day - b.day)
    .map((e) => ({ ...e, px: scale(e.day), text: `${e.label} ${formatDayTick(e.day)}` }))
    .filter((e) => Number.isFinite(e.px));
  const mid = Number.isFinite(left) && Number.isFinite(right) ? (left + right) / 2 : Infinity;

  // Each label's horizontal extent (11px Open Sans is about 6.1px a character). A label sits right of its rule in
  // the left half and left of it in the right half. Labels go in the first row where they overlap nothing, so
  // same-day and near-day events stack instead of printing on top of each other.
  const rows: Array<Array<[number, number]>> = [];
  const pad = Math.max(4, minGapPx > 56 ? minGapPx - 56 : 4);
  const withRow = placed.map((e) => {
    const w = e.text.length * 6.1;
    const anchor: "start" | "end" = e.px > mid ? "end" : "start";
    let x0 = anchor === "end" ? e.px - 4 - w : e.px + 4;
    if (Number.isFinite(left)) x0 = Math.max(x0, left);
    if (Number.isFinite(right)) x0 = Math.min(x0, right - w);
    const span: [number, number] = [x0 - pad, x0 + w + pad];
    let row = rows.findIndex((r) => r.every(([a, b]) => span[1] <= a || span[0] >= b));
    if (row === -1) { row = rows.length; rows.push([]); }
    rows[row].push(span);
    return { ...e, row, x0 };
  });
  const rules = [...new Map(withRow.map((e) => [Math.round(e.px), e])).values()];

  return (
    <g className="chart-events" aria-hidden="true">
      {rules.map((e, i) => (
        <g key={`rule-${e.day}-${i}`}>
          <line x1={e.px} x2={e.px} y1={y0} y2={y1} stroke={chartTokens.reference} strokeWidth={1} />
          {withRow.some((o) => o.detected && Math.round(o.px) === Math.round(e.px)) ? (
            <line x1={e.px} x2={e.px} y1={y1 - 4} y2={y1 + 4} stroke={chartTokens.flag} strokeWidth={4} />
          ) : null}
        </g>
      ))}
      {withRow.map((e, i) => (
        <text
          key={`lbl-${e.day}-${i}`}
          x={e.x0}
          y={y0 - 5 - e.row * lineHeight}
          textAnchor="start"
          className="chart-events__label"
          fill={chartTokens.reference}
          stroke={chartTokens.halo}
          strokeWidth={4}
          strokeLinejoin="round"
          paintOrder="stroke"
        >
          {e.text}
        </text>
      ))}
    </g>
  );
}

/** Top margin (px) that leaves room for up to n stacked event label rows above the plot. */
export function eventsTopMargin(n: number, lineHeight = 13): number {
  return n > 0 ? 8 + Math.min(n, 4) * lineHeight : 0;
}

interface DotProps { cx?: number; cy?: number; index?: number; stroke?: string }

/** Dot renderer that draws only the last point: 4px dot with a 2px halo ring. */
export function endpointDot(lastIndex: number) {
  return (p: DotProps) =>
    p.index === lastIndex && p.cx !== undefined && p.cy !== undefined ? (
      <circle key={`end-${p.index}`} cx={p.cx} cy={p.cy} r={4} fill={p.stroke} stroke={chartTokens.halo} strokeWidth={2} />
    ) : (
      <g key={`dot-${p.index}`} />
    );
}

/** Small inline text block for footnotes: one sentence per item. */
export function ChartNotes({ items }: { items: ReactNode[] }) {
  const list = items.filter(Boolean);
  if (list.length === 0) return null;
  return <ul className="chart__notes">{list.map((n, i) => <li key={i}>{n}</li>)}</ul>;
}
