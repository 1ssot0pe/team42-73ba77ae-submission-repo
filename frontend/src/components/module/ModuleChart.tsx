/**
 * ModuleChart (docs/visuals-spec.md 4.3): dispatches a normalised Chart to its dedicated component by chart.id.
 * Charts without a dedicated component fall back to GenericLineChart: today's line chart in ChartFrame, step-after
 * lines, direct labels at line ends instead of a legend, reference lines and event markers labelled in words,
 * a sentence tooltip, and a "View data" table of exactly what is plotted.
 * Props: chart (normalise.ts Chart); trialId (for components that read record sections); height (plot height).
 */
import { Customized, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  ChartFrame, ChartTooltip, EndLabel, EventMarkers, eventsTopMargin, axisProps, chartMargin, chartTokens, dayTicks, formatDayTick,
  gridProps, niceDomain, refLabel, seriesStyle, thresholdLine,
} from "../shared";
import type { DataColumn, DataTable } from "../shared";
import { CusumChart } from "./charts/CusumChart";
import { EffectForest } from "./charts/EffectForest";
import { MadrsByWeek } from "./charts/MadrsByWeek";
import { ReportAccuracy } from "./charts/ReportAccuracy";
import { SiteSmallMultiples } from "./charts/SiteSmallMultiples";
import type { Chart } from "./normalise";

export interface ModuleChartComponentProps {
  chart: Chart;
  trialId: string;
  /** plot height per chart (or per panel for small multiples) */
  height?: number;
}

export interface ModuleChartProps {
  chart: Chart;
  trialId: string;
  height?: number;
}

export function ModuleChart({ chart, trialId, height }: ModuleChartProps) {
  switch (chart.id) {
    case "rater-accuracy-site":
    case "rater-accuracy-by-rater":
    case "participant-accuracy-site": return <SiteSmallMultiples chart={chart} trialId={trialId} height={height} />;
    case "cusum-site": return <CusumChart chart={chart} trialId={trialId} height={height} />;
    case "effect-estimates": return <EffectForest chart={chart} trialId={trialId} height={height} />;
    case "madrs-by-week": return <MadrsByWeek chart={chart} trialId={trialId} height={height} />;
    case "report-rater-accuracy-site": return <ReportAccuracy chart={chart} trialId={trialId} height={height} />;
    default: return <GenericLineChart chart={chart} height={height} />;
  }
}

/* ------------------------------------------------------------------ generic path */

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function lastIndexWithValue(data: Chart["data"], key: string): number {
  for (let i = data.length - 1; i >= 0; i--) if (isNum(data[i][key])) return i;
  return -1;
}

function fmt(v: unknown): string {
  if (!isNum(v)) return "no value";
  const s = Number.isInteger(v) ? String(v) : String(Number(v.toFixed(3)));
  return s.startsWith("-") ? `−${s.slice(1)}` : s;
}

function xWords(x: string, v: unknown): string {
  if (x === "day" && isNum(v)) return `Day ${v}`;
  if (x === "week" && isNum(v)) return `Week ${v}`;
  return `${x.charAt(0).toUpperCase()}${x.slice(1)} ${String(v ?? "")}`.trim();
}

/** Parse a marker label for a leading day so EventMarkers does not print it twice ("Alert D47"). */
function markerEvents(chart: Chart): { day: number; label: string }[] {
  const out: { day: number; label: string }[] = [];
  const seen = new Set<string>();
  for (const m of chart.markers) {
    if (!isNum(m.x)) continue;
    const label = (m.label || "Event").replace(/\s*\(?\b(?:day|D\+?)\s*\d+\)?\s*$/i, "").trim() || "Event";
    const k = `${m.x}|${label}`;
    if (seen.has(k)) continue;
    seen.add(k);
    out.push({ day: m.x, label });
  }
  return out;
}

export function GenericLineChart({ chart, height = 260 }: { chart: Chart; height?: number }) {
  const { data, series, refs, x } = chart;
  const numericX = data.length > 0 && data.every((r) => isNum(r[x]));
  const isDay = x === "day" && numericX;
  const drawn = series.filter((s) => lastIndexWithValue(data, s.key) >= 0);
  const empty = data.length === 0 || drawn.length === 0;
  const events = numericX ? markerEvents(chart) : [];
  const maxX = numericX ? Math.max(...data.map((r) => r[x] as number)) : 0;
  const minX = numericX ? Math.min(...data.map((r) => r[x] as number)) : 0;
  const ticks = isDay ? dayTicks(maxX).filter((t) => t >= minX) : undefined;
  // Room on the right for direct labels at line ends.
  const longest = Math.max(0, ...drawn.map((s) => s.label.length));
  const margin = { ...chartMargin, right: Math.min(120, 16 + longest * 6.2), top: chartMargin.top + eventsTopMargin(events.length) };
  const styleFor = (i: number) => seriesStyle(i);
  // No y_domain in the payload: the axis always includes 0, so a fallback chart never truncates its baseline and
  // exaggerates change. Non-negative data runs from 0; data with negatives runs from its minimum to at least 0.
  const yValues = [
    ...drawn.flatMap((s) => data.map((r) => r[s.key]).filter(isNum)),
    ...refs.map((r) => r.y),
  ];
  const yMin = yValues.length && Math.min(...yValues) < 0 ? niceDomain(yValues, true)[0] : 0;
  const yMax = yValues.length ? Math.max(...yValues) : 1;
  const yDomainWithZero: [number, number | "auto"] = yMax <= 0 ? [yMin, 0] : [yMin, "auto"];

  const columns: DataColumn[] = [
    { key: x, label: x === "day" ? "Day" : x.charAt(0).toUpperCase() + x.slice(1), align: numericX ? "right" : "left" },
    ...drawn.map((s) => ({ key: s.key, label: s.label, align: "right" as const })),
  ];
  const dataTable: DataTable = {
    columns,
    // Only rows where something is plotted; days before the first release carry no value.
    rows: data.filter((r) => drawn.some((sr) => isNum(r[sr.key])))
      .map((r) => Object.fromEntries(columns.map((c) => [c.key, r[c.key] ?? null]))),
    note: refs.length ? `Reference lines: ${refs.map((r) => r.label).join("; ")}.` : undefined,
  };

  const latest = drawn.map((s) => {
    const i = lastIndexWithValue(data, s.key);
    return `${s.label} ${fmt(data[i][s.key])} at ${xWords(x, data[i][x]).toLowerCase()}`;
  });
  const ariaLabel = empty
    ? `${chart.title}: no data yet.`
    : `${chart.title}. Latest values: ${latest.join("; ")}.${refs.length ? ` ${refs.map((r) => r.label).join("; ")}.` : ""}${
      events.length ? ` Events: ${events.map((e) => `${e.label} day ${e.day}`).join("; ")}.` : ""}`;

  return (
    <ChartFrame
      id={chart.id}
      title={chart.title}
      subtitle={[chart.yLabel, chart.titleNote].filter(Boolean).join(", ") || undefined}
      synthetic={chart.synthetic}
      ariaLabel={ariaLabel}
      dataTable={empty ? undefined : dataTable}
      empty={empty ? { title: "No data yet", body: "Advance the trial to collect it." } : null}
    >
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={margin} accessibilityLayer={false}>
          <CartesianGrid {...gridProps} />
          <XAxis
            {...axisProps}
            dataKey={x}
            type={numericX ? "number" : "category"}
            domain={numericX ? ["dataMin", "dataMax"] : undefined}
            ticks={ticks}
            allowDecimals={false}
            tickFormatter={isDay ? (d: number) => formatDayTick(d) : undefined}
          />
          <YAxis
            {...axisProps}
            width={44}
            domain={chart.yDomain ?? yDomainWithZero}
            tickFormatter={(v: number) => fmt(v)}
          />
          <Tooltip
            cursor={{ stroke: chartTokens.grid }}
            isAnimationActive={false}
            content={<ChartTooltip render={(row) => {
              const parts = drawn.filter((s) => isNum(row[s.key])).map((s) => `${s.label} ${fmt(row[s.key])}`);
              return parts.length ? `${xWords(x, row[x])}: ${parts.join(", ")}` : "";
            }} />}
          />
          {refs.map((r, i) => (
            <ReferenceLine key={`ref-${i}`} {...thresholdLine} y={r.y}
              label={{ ...refLabel(r.label, "insideBottomLeft"), offset: 6 }} />
          ))}
          {series.map((s, i) => (
            <Line key={s.key} {...styleFor(i)} dataKey={s.key} name={s.label} connectNulls={false} />
          ))}
          {events.length ? (
            <Customized component={(p: Record<string, unknown>) => (
              <EventMarkers events={events} xAxisMap={p.xAxisMap as never} offset={p.offset as never} />
            )} />
          ) : null}
          <Customized component={(p: Record<string, unknown>) => {
            const xs = Object.values((p.xAxisMap ?? {}) as Record<string, { scale?: (v: unknown) => number }>)[0]?.scale;
            const ys = Object.values((p.yAxisMap ?? {}) as Record<string, { scale?: (v: number) => number }>)[0]?.scale;
            if (!xs || !ys) return null;
            // Direct labels at line ends; nudge apart so they never overlap.
            const ends = drawn.map((s) => {
              const i = lastIndexWithValue(data, s.key);
              const idx = series.indexOf(s);
              const bw = (xs as { bandwidth?: () => number }).bandwidth?.() ?? 0;
              return { s, idx, x: xs(data[i][x]) + bw / 2, y: ys(data[i][s.key] as number) };
            }).sort((a, b) => a.y - b.y);
            for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < 13) ends[k].y = ends[k - 1].y + 13;
            // Keep the stack inside the plot: if it runs past the bottom, shift it up.
            const off = p.offset as { top?: number; height?: number } | undefined;
            const bottom = off ? (off.top ?? 0) + (off.height ?? 0) - 4 : Infinity;
            const over = ends.length ? ends[ends.length - 1].y - bottom : 0;
            if (over > 0) for (const e of ends) e.y -= over;
            return (
              <g>
                {ends.map((e) => (
                  <EndLabel key={e.s.key} x={e.x} y={e.y} text={e.s.label} color={styleFor(e.idx).stroke}
                    weight={e.idx === 0 ? 600 : 400} />
                ))}
              </g>
            );
          }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
