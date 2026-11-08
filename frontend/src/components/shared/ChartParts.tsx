/**
 * Chart parts (design.md 8.16), used with chartTheme.ts.
 * ChartFrame props: title; children (the recharts chart); caption (default "Synthetic data.");
 *   legend (optional [{label, index}] using seriesStyle(index) swatches); tag (default "SYNTHETIC", top right).
 * ChartTooltip: pass as <Tooltip content={<ChartTooltip />} />; optional props xLabel (prefix such as "D+"), digits.
 * endpointDot(lastIndex): a recharts `dot` renderer that draws only the emphasised endpoint (5px, 2px eggshell ring).
 * ViewLineChart props: chart (a ViewChart from a module view model); height (default 240).
 *   Renders a LineChart per the contract: series keys, connectNulls, legend, glass tooltip, SYNTHETIC tag.
 */
import type { ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { ViewChart } from "../../types";
import { axisProps, chartColors, chartMargin, gridProps, refLabel, seriesStyle, thresholdLine } from "./chartTheme";
import { formatNumber } from "./format";
import { SpecimenTag } from "./Pills";

export interface LegendItem {
  label: string;
  index: number;
}

export function ChartLegend({ items }: { items: LegendItem[] }) {
  return (
    <div className="chart-legend">
      {items.map((it) => {
        const s = seriesStyle(it.index);
        return (
          <span key={it.label} className="chart-legend__item">
            <span className={`chart-legend__swatch chart-legend__swatch--${s.pattern}`} style={{ borderTopColor: s.stroke }} aria-hidden="true" />
            {it.label}
          </span>
        );
      })}
    </div>
  );
}

export interface ChartFrameProps {
  title: string;
  children: ReactNode;
  caption?: string;
  legend?: LegendItem[];
  tag?: string;
}

export function ChartFrame({ title, children, caption = "Synthetic data.", legend, tag = "SYNTHETIC" }: ChartFrameProps) {
  return (
    <figure className="chart">
      <div className="chart__head">
        <h3 className="chart__title">{title}</h3>
        <SpecimenTag label={tag} />
      </div>
      <div className="chart__body">{children}</div>
      {legend && legend.length > 0 ? <ChartLegend items={legend} /> : null}
      {caption ? <figcaption className="chart__caption">{caption}</figcaption> : null}
    </figure>
  );
}

interface TooltipPayloadItem {
  name?: string | number;
  value?: unknown;
  color?: string;
  stroke?: string;
  dataKey?: unknown;
}

export interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: unknown;
  xLabel?: string;
  digits?: number;
}

export function ChartTooltip({ active, payload, label, xLabel = "", digits = 3 }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="chart-tooltip glass glass--strong">
      <div className="chart-tooltip__label">{xLabel}{String(label ?? "")}</div>
      {payload.map((p, i) => (
        <div key={i} className="chart-tooltip__row">
          <span>
            <span className="chart-tooltip__swatch" style={{ background: p.stroke || p.color }} aria-hidden="true" />
            {String(p.name ?? p.dataKey ?? "")}
          </span>
          <span>{typeof p.value === "number" ? formatNumber(p.value, digits) : String(p.value ?? "")}</span>
        </div>
      ))}
    </div>
  );
}

interface DotProps { cx?: number; cy?: number; index?: number; stroke?: string }

/** Dot renderer that draws only the last point: 5px dot with a 2px eggshell ring. */
export function endpointDot(lastIndex: number) {
  return (p: DotProps) =>
    p.index === lastIndex && p.cx !== undefined && p.cy !== undefined ? (
      <circle key={`end-${p.index}`} cx={p.cx} cy={p.cy} r={5} fill={p.stroke} stroke={chartColors.eggshell} strokeWidth={2} />
    ) : (
      <g key={`dot-${p.index}`} />
    );
}

export interface ViewLineChartProps {
  chart: ViewChart;
  height?: number;
}

export function ViewLineChart({ chart, height = 240 }: ViewLineChartProps) {
  const data = chart.data ?? [];
  const legend = chart.series.map((s, i) => ({ label: s.label || s.key, index: i }));
  return (
    <ChartFrame title={chart.title} legend={legend}>
      {data.length === 0 ? (
        <p className="t-body-sm c-smoke">No data yet. Advance the trial to collect it.</p>
      ) : (
        <ResponsiveContainer width="100%" height={height}>
          <LineChart data={data} margin={chartMargin}>
            <CartesianGrid {...gridProps} />
            <XAxis {...axisProps} dataKey={chart.x} />
            <YAxis {...axisProps} label={chart.y_label ? { ...refLabel(chart.y_label, "insideTopLeft"), angle: 0 } : undefined} />
            <Tooltip content={<ChartTooltip xLabel={chart.x === "day" ? "D+" : `${chart.x} `} />} cursor={{ stroke: chartColors.stone }} />
            {typeof chart.threshold === "number" ? (
              <ReferenceLine {...thresholdLine} y={chart.threshold} label={refLabel(`THRESHOLD ${chart.threshold}`)} />
            ) : null}
            {chart.series.map((s, i) => (
              <Line key={s.key} {...seriesStyle(i)} dataKey={s.key} name={s.label || s.key} connectNulls
                dot={i === 0 ? endpointDot(data.length - 1) : false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
    </ChartFrame>
  );
}
