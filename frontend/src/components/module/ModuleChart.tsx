/**
 * ModuleChart (design.md 8.16): one line chart from a module view model, on a taupe ChartFrame with the
 * SYNTHETIC tag and the caption "Synthetic data.". Series 0 violet solid, 1 ember dashed, then graphite and
 * ash patterns (seriesStyle). Reference lines (threshold, expected, alarm) are ember 1px dashed with a mono label;
 * markers are vertical ember lines (drift onset, alerts, actions). connectNulls on every series.
 * Props: chart (a normalised Chart from normalise.ts); height (default 260).
 */
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  ChartFrame, ChartTooltip, axisProps, chartColors, chartMargin, driftMarker, endpointDot, gridProps, refLabel,
  seriesStyle, thresholdLine,
} from "../shared";
import type { Chart, Marker } from "./normalise";

export interface ModuleChartProps {
  chart: Chart;
  height?: number;
}

/** Reference lines are drawn after the series so their labels sit on top. A taupe halo behind reference and marker labels, so they stay legible where they cross a data line. */
const HALO = { stroke: "var(--color-taupe)", strokeWidth: 4, paintOrder: "stroke", strokeLinejoin: "round" } as const;

/** Group markers on the same x so their labels do not print on top of each other. */
function groupMarkers(ms: Marker[]): Marker[] {
  const by = new Map<string, Marker>();
  for (const m of ms) {
    const k = String(m.x);
    const prev = by.get(k);
    if (!prev) by.set(k, { ...m });
    else if (m.label && !prev.label.split(" · ").includes(m.label)) prev.label = prev.label ? `${prev.label} · ${m.label}` : m.label;
  }
  return [...by.values()];
}

function lastIndexWithValue(data: Chart["data"], key: string): number {
  for (let i = data.length - 1; i >= 0; i--) {
    const v = data[i][key];
    if (typeof v === "number") return i;
  }
  return -1;
}

export function ModuleChart({ chart, height = 260 }: ModuleChartProps) {
  const { data, series, refs, x } = chart;
  const markers = groupMarkers(chart.markers);
  const numericX = data.length > 0 && data.every((r) => typeof r[x] === "number");
  const isDay = x === "day";
  const legend = series.map((s, i) => ({ label: s.label, index: i }));
  const hasLine = series.some((s) => lastIndexWithValue(data, s.key) >= 0);
  const empty = data.length === 0 || (!hasLine && refs.length === 0);
  // Markers in the right half put their label on the left of the line so it is not clipped.
  const xs = numericX ? data.map((r) => r[x] as number) : [];
  const mid = xs.length ? (Math.min(...xs) + Math.max(...xs)) / 2 : 0;

  return (
    <ChartFrame title={chart.title} legend={empty ? undefined : legend}>
      {empty ? (
        <p className="mchart__empty">No data yet. Advance the trial to collect it.</p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={chartMargin}>
            <CartesianGrid {...gridProps} />
            <XAxis
              {...axisProps}
              dataKey={x}
              type={numericX ? "number" : "category"}
              domain={numericX ? ["dataMin", "dataMax"] : undefined}
              allowDecimals={false}
              tickFormatter={isDay && numericX ? (d: number) => `D+${d}` : undefined}
            />
            <YAxis
              {...axisProps}
              domain={chart.yDomain ?? ["auto", "auto"]}
              allowDataOverflow={false}
              label={chart.yLabel ? { ...refLabel(chart.yLabel, "insideTopLeft"), angle: 0 } : undefined}
            />
            <Tooltip content={<ChartTooltip xLabel={isDay ? "D+" : `${x} `} />} cursor={{ stroke: chartColors.stone }} />
            {series.map((s, i) => (
              <Line key={s.key} {...seriesStyle(i)} dataKey={s.key} name={s.label} connectNulls
                dot={i === 0 ? endpointDot(lastIndexWithValue(data, s.key)) : false} />
            ))}
            {refs.map((r, i) => (
              <ReferenceLine key={`ref-${i}`} {...thresholdLine} y={r.y}
                label={{ ...refLabel(r.label.toUpperCase()), position: "insideBottomLeft", offset: 8 + i * 12, ...HALO }} />
            ))}
            {markers.map((m, i) => (
              <ReferenceLine key={`mk-${i}`} {...driftMarker} x={m.x} ifOverflow="extendDomain"
                label={m.label ? { ...refLabel(m.label.toUpperCase(), numericX && typeof m.x === "number" && m.x > mid ? "insideTopRight" : "insideTopLeft"), offset: 6 + (i % 3) * 14, ...HALO } : undefined} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartFrame>
  );
}
