/**
 * chartTheme (design.md 8.16). recharts props for the Lab Glass chart style. Colours are CSS var() references,
 * never hex, so Bench and Darkroom both work. Spread these onto recharts elements:
 *   <CartesianGrid {...gridProps} />  <XAxis {...axisProps} dataKey="day" />  <YAxis {...axisProps} />
 *   <Line {...seriesStyle(0)} dataKey="Site A" />   (0 = violet solid, 1 = ember dashed, 2+ = graphite patterns)
 *   <Area {...primaryArea} dataKey="Site A" />      <ReferenceLine {...thresholdLine} y={0.75} label={refLabel("THRESHOLD 0.75")} />
 *   <ReferenceLine {...driftMarker} x={28} label={refLabel("DRIFT ONSET D+28", "insideTopLeft")} />
 * The tooltip, legend, SYNTHETIC tag and endpoint dot are React parts in ChartParts.tsx.
 */

export const chartColors = {
  primary: "var(--color-spark-violet)",
  secondary: "var(--color-spark-ember)",
  threshold: "var(--color-spark-ember)",
  drift: "var(--color-spark-ember)",
  grid: "var(--chart-grid)",
  axis: "var(--color-ash)",
  legend: "var(--color-graphite)",
  label: "var(--color-graphite)",
  ink: "var(--color-ink)",
  graphite: "var(--color-graphite)",
  ash: "var(--color-ash)",
  eggshell: "var(--color-eggshell)",
  stone: "var(--color-stone)",
} as const;

export const chartFont = "var(--font-mono)";

export const gridProps = {
  stroke: chartColors.grid,
  strokeDasharray: "2 4",
  vertical: false,
} as const;

export const axisProps = {
  axisLine: false,
  tickLine: { stroke: chartColors.axis },
  tickSize: 4,
  tick: { fill: chartColors.axis, fontSize: 11, fontFamily: chartFont },
  stroke: chartColors.axis,
} as const;

export interface SeriesStyle {
  stroke: string;
  strokeWidth: number;
  strokeDasharray?: string;
  dot: false;
  activeDot: { r: number; stroke: string; strokeWidth: number };
  type: "monotone";
  isAnimationActive: boolean;
  /** legend swatch pattern */
  pattern: "solid" | "dashed" | "dotted";
}

const STYLES: Array<Pick<SeriesStyle, "stroke" | "strokeDasharray" | "pattern">> = [
  { stroke: chartColors.primary, pattern: "solid" },
  { stroke: chartColors.secondary, strokeDasharray: "6 4", pattern: "dashed" },
  { stroke: chartColors.graphite, strokeDasharray: "1 4", pattern: "dotted" },
  { stroke: chartColors.ash, strokeDasharray: "8 3 2 3", pattern: "dashed" },
  { stroke: chartColors.graphite, pattern: "solid" },
];

/** Line style for series i: 0 violet solid (primary), 1 ember dashed (secondary), then graphite and ash patterns. */
export function seriesStyle(i: number): SeriesStyle {
  const s = STYLES[i % STYLES.length];
  return {
    ...s,
    strokeWidth: 2,
    dot: false,
    activeDot: { r: 4, stroke: chartColors.eggshell, strokeWidth: 2 },
    type: "monotone",
    isAnimationActive: false,
  };
}

export const primaryLine = seriesStyle(0);
export const secondaryLine = seriesStyle(1);

/** Area under the primary series: violet at 8%. */
export const primaryArea = {
  fill: chartColors.primary,
  fillOpacity: 0.08,
  stroke: "none",
  type: "monotone",
  isAnimationActive: false,
} as const;

/** Threshold: ember 1px dashed. */
export const thresholdLine = {
  stroke: chartColors.threshold,
  strokeWidth: 1,
  strokeDasharray: "4 4",
  ifOverflow: "extendDomain",
} as const;

/** Drift onset: vertical ember 1px line. */
export const driftMarker = {
  stroke: chartColors.drift,
  strokeWidth: 1,
} as const;

/** Mono label for reference lines, e.g. refLabel("DRIFT ONSET D+28"). */
export function refLabel(value: string, position: "insideTopRight" | "insideTopLeft" | "insideBottomRight" | "top" | "right" = "insideTopRight") {
  return { value, position, fill: chartColors.label, fontSize: 10, fontFamily: chartFont, letterSpacing: "0.08em" };
}

export const chartMargin = { top: 8, right: 12, bottom: 0, left: -12 };
