/**
 * chartTheme (docs/visuals-spec.md 0 and 4.4). Recharts props for the Parallax chart style. Colours are CSS var()
 * references, never hex, so light and dark both work. Violet and orange are used only inside charts.
 *
 *   <CartesianGrid {...gridProps} />  <XAxis {...axisProps} dataKey="day" />  <YAxis {...axisProps} />
 *   <Line {...seriesStyle(0)} dataKey="Site A" />   (0 = violet solid, 1+ = smoke dashed / dotted patterns)
 *   <ReferenceLine {...chanceLine} y={0.5} />  <ReferenceLine {...thresholdLine} y={0.6} />
 *
 * Grammar: flag (orange) marks the group of interest, primary (violet) the main or single series, muted (smoke)
 * context series, reference (graphite) every rule. Colour is never alone: pair it with lineStyles or a label.
 * Time series are carry-forward vault data, so every line is stepAfter (stepType). No monotone curves.
 */

export const chartTokens = {
  primary: "var(--color-spark-violet)",
  flag: "var(--color-spark-ember)",
  muted: "var(--color-smoke)",
  reference: "var(--color-graphite)",
  grid: "var(--chart-grid)",
  axis: "var(--color-smoke)",
  halo: "var(--color-eggshell)",
  bandOpacity: 0.12,
  alarmFillOpacity: 0.06,
} as const;

/** strokeDasharray values. solid is undefined (no dash). */
export const lineStyles = {
  solid: undefined,
  dashed: "6 4",
  dotted: "1 4",
  reference: "4 4",
  threshold: "1 3",
  derived: "2 3",
} as const;

export const stepType = "stepAfter" as const;

/**
 * Legacy colour names, kept so older call sites compile. They now follow the v2 grammar: secondary, threshold and
 * drift are graphite (rules are never orange by default; orange is chartTokens.flag, chosen on purpose).
 */
export const chartColors = {
  primary: chartTokens.primary,
  secondary: chartTokens.muted,
  flag: chartTokens.flag,
  threshold: chartTokens.reference,
  drift: chartTokens.reference,
  grid: chartTokens.grid,
  axis: chartTokens.axis,
  legend: "var(--color-graphite)",
  label: "var(--color-graphite)",
  ink: "var(--color-ink)",
  graphite: "var(--color-graphite)",
  smoke: "var(--color-smoke)",
  ash: "var(--color-ash)",
  eggshell: "var(--color-eggshell)",
  stone: "var(--color-stone)",
} as const;

/** Charts use the body face (Open Sans) with tabular figures, never mono. */
export const chartFont = "var(--font-body)";

export const gridProps = {
  stroke: chartTokens.grid,
  strokeDasharray: "2 4",
  vertical: false,
} as const;

export const axisProps = {
  axisLine: false,
  tickLine: { stroke: chartTokens.grid },
  tickSize: 4,
  tick: { fill: chartTokens.axis, fontSize: 11, fontFamily: chartFont },
  stroke: chartTokens.axis,
} as const;

export interface SeriesStyle {
  stroke: string;
  strokeWidth: number;
  strokeDasharray?: string;
  dot: false;
  activeDot: { r: number; stroke: string; strokeWidth: number };
  type: typeof stepType;
  isAnimationActive: false;
  /** pattern name, for a direct label or a legend swatch */
  pattern: "solid" | "dashed" | "dotted";
}

const STYLES: Array<Pick<SeriesStyle, "stroke" | "strokeDasharray" | "pattern">> = [
  { stroke: chartTokens.primary, strokeDasharray: lineStyles.solid, pattern: "solid" },
  { stroke: chartTokens.muted, strokeDasharray: lineStyles.dashed, pattern: "dashed" },
  { stroke: chartTokens.muted, strokeDasharray: lineStyles.dotted, pattern: "dotted" },
  { stroke: chartTokens.reference, strokeDasharray: "8 3 2 3", pattern: "dashed" },
  { stroke: chartTokens.reference, strokeDasharray: lineStyles.dotted, pattern: "dotted" },
];

/**
 * Line style for series i: 0 violet solid (primary), then smoke and graphite dash patterns. Orange is no longer
 * automatic: a chart that flags a group uses flagStyle().
 */
export function seriesStyle(i: number): SeriesStyle {
  const s = STYLES[((i % STYLES.length) + STYLES.length) % STYLES.length];
  return {
    ...s,
    strokeWidth: 2,
    dot: false,
    activeDot: { r: 4, stroke: chartTokens.halo, strokeWidth: 2 },
    type: stepType,
    isAnimationActive: false,
  };
}

/** The group of interest: orange solid 2px. */
export function flagStyle(): SeriesStyle {
  return { ...seriesStyle(0), stroke: chartTokens.flag };
}

export const primaryLine = seriesStyle(0);
export const secondaryLine = seriesStyle(1);

/** Interval band under the primary series: violet at bandOpacity. Pass `fill` to match another line. */
export const primaryArea = {
  fill: chartTokens.primary,
  fillOpacity: chartTokens.bandOpacity,
  stroke: "none",
  type: stepType,
  isAnimationActive: false,
} as const;

/** Chance level (50%): graphite dashed 4 4. Use only where 50% is the real chance level. */
export const chanceLine = {
  stroke: chartTokens.reference,
  strokeWidth: 1,
  strokeDasharray: lineStyles.reference,
  ifOverflow: "extendDomain",
} as const;

/** Threshold or alarm reference from data: graphite dotted 1 3. */
export const thresholdLine = {
  stroke: chartTokens.reference,
  strokeWidth: 1,
  strokeDasharray: lineStyles.threshold,
  ifOverflow: "extendDomain",
} as const;

/** No effect (0): graphite solid 1px. */
export const zeroLine = {
  stroke: chartTokens.reference,
  strokeWidth: 1,
  ifOverflow: "extendDomain",
} as const;

/** Events (onset, alert, action): vertical graphite 1px rule. */
export const driftMarker = {
  stroke: chartTokens.reference,
  strokeWidth: 1,
} as const;
export const eventLine = driftMarker;

/** Label for reference lines, e.g. refLabel("Coin flip 50%"). Sentence case, 11px body face, halo behind. */
export function refLabel(
  value: string,
  position: "insideTopRight" | "insideTopLeft" | "insideBottomRight" | "insideBottomLeft" | "top" | "right" = "insideTopRight",
) {
  return {
    value, position, fill: chartTokens.reference, fontSize: 11, fontFamily: chartFont,
    stroke: chartTokens.halo, strokeWidth: 4, paintOrder: "stroke", strokeLinejoin: "round",
  } as const;
}

/** left >= 8 so tick labels never clip; right leaves room for end labels. */
export const chartMargin = { top: 12, right: 16, bottom: 4, left: 8 };
