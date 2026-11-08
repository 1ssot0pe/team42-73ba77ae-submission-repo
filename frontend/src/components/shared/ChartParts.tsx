/**
 * Chart parts (docs/visuals-spec.md 4.4), used with chartTheme.ts and ChartFrame.tsx.
 *
 * ChartTooltip: <Tooltip content={<ChartTooltip render={(row) => "Day 47, Site B: ..."} />} />
 *   One sentence in words, built by `render` from the hovered data row. Without `render` it falls back to
 *   "label: name value" pairs (legacy). Flat eggshell surface, tabular figures.
 * EndLabel: a direct label with a halo, for line ends and panel titles (replaces legends).
 *   Use inside an SVG (for example a recharts <Customized> or a LabelList content renderer).
 * EventMarkers: vertical event rules with labels "Alert D47", stacked so labels never overlap.
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
  /** horizontal px below which two labels are stacked rather than set side by side (default 56) */
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
    .map((e) => ({ ...e, px: scale(e.day) }))
    .filter((e) => Number.isFinite(e.px));

  // Row assignment: reuse the first row whose last label is at least minGapPx away.
  const rowsLast: number[] = [];
  const withRow = placed.map((e) => {
    let row = rowsLast.findIndex((last) => e.px - last >= minGapPx);
    if (row === -1) { row = rowsLast.length; rowsLast.push(e.px); } else rowsLast[row] = e.px;
    return { ...e, row };
  });
  const mid = Number.isFinite(left) && Number.isFinite(right) ? (left + right) / 2 : Infinity;

  return (
    <g className="chart-events" aria-hidden="true">
      {withRow.map((e, i) => {
        const anchor = e.px > mid ? "end" : "start";
        const ly = y0 + 10 + e.row * lineHeight;
        return (
          <g key={`${e.day}-${i}`}>
            <line x1={e.px} x2={e.px} y1={y0} y2={y1} stroke={chartTokens.reference} strokeWidth={1} />
            {e.detected ? (
              <line x1={e.px} x2={e.px} y1={y1 - 4} y2={y1 + 4} stroke={chartTokens.flag} strokeWidth={4} />
            ) : null}
            <text
              x={anchor === "end" ? e.px - 4 : e.px + 4}
              y={ly}
              textAnchor={anchor}
              className="chart-events__label"
              fill={chartTokens.reference}
              stroke={chartTokens.halo}
              strokeWidth={4}
              strokeLinejoin="round"
              paintOrder="stroke"
            >
              {`${e.label} ${formatDayTick(e.day)}`}
            </text>
          </g>
        );
      })}
    </g>
  );
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
