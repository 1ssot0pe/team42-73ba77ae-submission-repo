/**
 * CusumChart (docs/visuals-spec.md section 2, cusum-site, Builder DOSING): the drift score (batched Bernoulli CUSUM)
 * per site from the record's raw `cusum` on each released rater batch, step-after, with the alarm line taken from
 * the data and the region above it shaded. Events: "Drift began (simulated)" (only when the master state exposes the
 * simulator's planted onset), the estimated onset, "Detected" (first release at or above the alarm line) and
 * "Action approved". After an approved action the monitor restarts the score at 0; that is drawn as a dotted drop and
 * a dotted flat line until the next real release, so the reset never looks like a measurement.
 */
import {
  CartesianGrid, ComposedChart, Customized, Line, ReferenceArea, ReferenceDot, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { useTrial } from "../../../trial";
import {
  ChartFrame, axisProps, chartTokens, dayTicks, formatDayTick, gridProps, lineStyles, useRecordSections,
} from "../../shared";
import type { DataTable } from "../../shared";
import type { Chart } from "../normalise";
import { driftAlerts, resetDay, shortSite, stackRows, useWidth } from "./SiteSmallMultiples";
import type { DriftAlert, RecordBits } from "./SiteSmallMultiples";
import "./dosing.css";

export interface ModuleChartComponentProps {
  chart: Chart;
  trialId: string;
  height?: number;
}

interface SimTruth {
  synthetic?: boolean;
  label?: string;
  drift_site?: string;
  drift_onset_day?: number;
}

interface Release {
  day: number;
  score: number;
  threshold: number | null;
}

interface SiteLine {
  site: string;
  full: string;
  releases: Release[];
  reset: number | null;      // day of the last reset that has a later release or is still pending one
  resetFrom: number | null;  // score held at the reset day
  resetUntil: number | null; // next real release after the reset (or today)
}

const fmt = (v: number) => (Math.round(v * 100) / 100).toFixed(2);

function siteLines(rec: RecordBits, sites: string[], today: number): SiteLine[] {
  const rows = (rec.blinding_metrics ?? []).filter((m) => m.module === "dosing" && m.who === "rater" && m.by === "site"
    && !m.suppressed && typeof m.cusum === "number").sort((a, b) => a.day - b.day);
  return sites.map((site) => {
    const mine = rows.filter((r) => shortSite(r.group) === site);
    const full = mine[0]?.group ?? site;
    const releases = mine.map((r) => ({ day: r.day, score: r.cusum as number, threshold: typeof r.threshold === "number" ? r.threshold : null }));
    const rd = mine.length ? resetDay(rec, full) : null;
    let reset: number | null = null;
    let resetFrom: number | null = null;
    let resetUntil: number | null = null;
    if (rd !== null && rd <= today) {
      const before = releases.filter((r) => r.day <= rd).at(-1);
      const after = releases.find((r) => r.day > rd);
      if (before && before.score > 0) {
        reset = rd;
        resetFrom = before.score;
        resetUntil = after ? after.day : today;
      }
    }
    return { site, full, releases, reset, resetFrom, resetUntil };
  });
}

interface Row {
  day: number;
  [key: string]: number | null;
}

function TooltipBox({ active, label, lines, threshold }: { active?: boolean; label?: number; lines: SiteLine[]; threshold: number }) {
  if (!active || typeof label !== "number") return null;
  const parts = lines.map((l) => {
    if (l.reset !== null && l.resetUntil !== null && label >= l.reset && label < l.resetUntil) {
      return `${l.site}: reset to 0 after the action on day ${l.reset}, no new batch yet`;
    }
    const r = l.releases.filter((x) => x.day <= label).at(-1);
    if (!r) return `${l.site}: no released guesses yet`;
    const where = r.score >= threshold ? "above" : "below";
    return `${l.site}: drift score ${fmt(r.score)}, ${where} the alarm line ${threshold}${r.day !== label ? ` (from day ${r.day})` : ""}`;
  });
  return <div className="dchart-tip" role="status">Day {label}. {parts.join("; ")}.</div>;
}

interface Ev {
  day: number;
  label: string;
  short: string;
  kind: "sim" | "onset" | "detect" | "action" | "resolved" | "rejected";
}

function Overlay(props: Record<string, unknown>) {
  const { events, lines, compact, delay } = props as unknown as {
    events: Ev[]; lines: Array<{ site: string; day: number; y: number; flagged: boolean }>; compact: boolean;
    delay: { from: number; to: number; text: string } | null;
  };
  const xAxisMap = props.xAxisMap as Record<string, { scale: (v: number) => number }> | undefined;
  const yAxisMap = props.yAxisMap as Record<string, { scale: (v: number) => number }> | undefined;
  const offset = props.offset as { top: number; left: number; width: number; height: number } | undefined;
  const xs = xAxisMap ? Object.values(xAxisMap)[0]?.scale : undefined;
  const ys = yAxisMap ? Object.values(yAxisMap)[0]?.scale : undefined;
  if (!xs || !ys || !offset) return null;
  const stacked = stackRows(events, compact ? 40 : 4);
  // end labels: nudge apart so they never overlap
  const ends = lines.map((l) => ({ ...l, py: ys(l.y) })).sort((a, b) => a.py - b.py);
  for (let i = 1; i < ends.length; i++) if (ends[i].py - ends[i - 1].py < 13) ends[i].py = ends[i - 1].py + 13;
  const bottom = offset.top + offset.height;
  return (
    <g>
      {stacked.map((e) => {
        const x = xs(e.day);
        const right = x > offset.left + offset.width * 0.55;
        const y = offset.top - 6 - e.row * 14;
        const tx = compact ? offset.left + 2 : right ? x - 4 : x + 4;
        return (
          <text key={`${e.kind}-${e.day}`} x={tx} y={compact ? offset.top - 6 - (stacked.length - 1 - e.row) * 14 : y}
            textAnchor={compact ? "start" : right ? "end" : "start"}
            className={`dchart-evlabel${e.kind === "detect" ? " dchart-evlabel--alert" : ""}`}>
            {compact ? e.short : e.label}
          </text>
        );
      })}
      {ends.map((l) => (
        <text key={l.site} x={xs(l.day) + 6} y={l.py + 4} className={`dchart-endlabel${l.flagged ? " dchart-endlabel--flag" : ""}`}>{l.site}</text>
      ))}
      {delay && !compact && (() => {
        const x1 = xs(delay.from);
        const x2 = xs(delay.to);
        const y = bottom - 22;
        return (
          <g className="dchart-callout">
            <path d={`M${x1},${y - 5} V${y} H${x2} V${y - 5}`} fill="none" />
            <text x={(x1 + x2) / 2} y={y + 13} textAnchor="middle">{delay.text}</text>
          </g>
        );
      })()}
      {events.filter((e) => e.kind === "detect").map((e) => (
        <rect key="tick" x={xs(e.day) - 2} y={bottom - 2} width={4} height={8} className="dchart-detecttick" />
      ))}
    </g>
  );
}

export function CusumChart({ chart, trialId, height }: ModuleChartComponentProps): JSX.Element {
  const { data: rec, loading, error } = useRecordSections(trialId, ["blinding_metrics", "alerts", "actions"]);
  const { state } = useTrial();
  const truth = ((state as unknown as { simulated_truth?: SimTruth | null } | null)?.simulated_truth) ?? null;
  const [ref, width] = useWidth<HTMLDivElement>();
  const compact = width > 0 && width < 560;

  const today = chart.data.reduce((m, r) => Math.max(m, typeof r.day === "number" ? r.day : 0), 0);
  const sites = chart.series.map((s) => s.key);
  const lines = rec ? siteLines(rec, sites, today) : [];
  const alerts = rec ? driftAlerts(rec) : [];
  const alert: DriftAlert | null = alerts.at(-1) ?? null;

  // threshold from the data: the record's threshold on released rows, else the view's constant "Alarm line"
  const recH = lines.flatMap((l) => l.releases.map((r) => r.threshold)).find((t): t is number => t !== null);
  const refH = chart.refs.find((r) => /alarm/i.test(r.label))?.y;
  const H = recH ?? refH ?? null;

  const flaggedSite = alert?.site ?? null;
  const flagLine = lines.find((l) => l.site === flaggedSite) ?? null;
  const detect = flagLine && H !== null ? flagLine.releases.find((r) => r.score >= H && (alert ? r.day <= alert.day : true)) ?? null : null;
  const simDay = truth && typeof truth.drift_onset_day === "number" && shortSite(truth.drift_site) === flaggedSite
    && truth.drift_onset_day <= today ? truth.drift_onset_day : null;

  const events: Ev[] = [];
  if (simDay !== null) events.push({ day: simDay, label: `Drift began (simulated) ${formatDayTick(simDay)}`, short: `Drift began (sim.) ${formatDayTick(simDay)}`, kind: "sim" });
  if (alert?.onset != null) events.push({ day: alert.onset, label: `Onset est. ${formatDayTick(alert.onset)}`, short: `Onset ${formatDayTick(alert.onset)}`, kind: "onset" });
  if (detect) events.push({ day: detect.day, label: `Detected ${formatDayTick(detect.day)}`, short: `Alert ${formatDayTick(detect.day)}`, kind: "detect" });
  if (alert?.actionDay != null) events.push({ day: alert.actionDay, label: `Action approved ${formatDayTick(alert.actionDay)}`, short: `Action ${formatDayTick(alert.actionDay)}`, kind: "action" });
  if (alert?.resolvedDay != null) events.push({ day: alert.resolvedDay, label: `Drift stopped ${formatDayTick(alert.resolvedDay)}`, short: `Stopped ${formatDayTick(alert.resolvedDay)}`, kind: "resolved" });
  if (alert?.dismissedDay != null) events.push({ day: alert.dismissedDay, label: `Rejected ${formatDayTick(alert.dismissedDay)}`, short: `Rejected ${formatDayTick(alert.dismissedDay)}`, kind: "rejected" });

  const delayFrom = simDay ?? alert?.onset ?? null;
  const delay = detect && delayFrom !== null && detect.day > delayFrom ? {
    from: delayFrom, to: detect.day,
    text: `${detect.day - delayFrom} days from ${simDay !== null ? "simulated drift start" : "estimated onset"} to alert`,
  } : null;

  // ---- rows: real values carried forward; the reset is a separate dotted key
  const rows: Row[] = [];
  for (let d = 1; d <= Math.max(today, 1); d++) {
    const row: Row = { day: d };
    for (const l of lines) {
      const last = l.releases.filter((r) => r.day <= d).at(-1);
      // solid: real scores, held; it stops at the reset day and starts again at the next real release
      const resumed = l.resetUntil !== null && l.releases.some((r) => r.day === l.resetUntil) && d >= l.resetUntil;
      const hidden = l.reset !== null && d > l.reset && !resumed;
      row[l.site] = last && !hidden ? last.score : null;
      // dotted: 0 from the reset day to the next real release (or today), never a measurement
      row[`${l.site}__reset`] = l.reset !== null && l.resetUntil !== null && d >= l.reset && d <= l.resetUntil ? 0 : null;
    }
    rows.push(row);
  }

  const peak = Math.max(H ?? 0, ...lines.flatMap((l) => l.releases.map((r) => r.score)));
  const yTop = chart.yDomain?.[1] ?? Math.ceil(Math.max((H ?? 1) * 1.4, peak * 1.1));
  const styleFor = (l: SiteLine, i: number) => l.site === flaggedSite
    ? { stroke: chartTokens.flag, dash: undefined as string | undefined }
    : { stroke: chartTokens.muted, dash: [lineStyles.dashed, lineStyles.dotted][i % 2] as string | undefined };
  let others = 0;
  const styled = lines.map((l) => ({ l, s: l.site === flaggedSite ? styleFor(l, 0) : styleFor(l, others++) }));
  const endLabels = lines.filter((l) => l.releases.length).map((l) => {
    const row = rows.at(-1);
    const y = (row?.[l.site] ?? row?.[`${l.site}__reset`] ?? 0) as number;
    return { site: l.site, day: Math.max(today, 1), y, flagged: l.site === flaggedSite };
  });

  // ---- words
  const delayDays = detect && alert?.onset != null ? detect.day - alert.onset : null;
  const title = !rec ? chart.title
    : H === null ? "Drift score by site"
    : detect && flaggedSite
      ? `${flaggedSite} drift score crossed the alarm line on day ${detect.day}${delayDays !== null && delayDays > 0 ? `, ${delayDays} days after estimated onset` : ""}${alert?.actionDay != null ? `; action approved day ${alert.actionDay}` : ""}`
      : `No site's drift score has reached the alarm line (${H}) to day ${today}`;
  const subtitle = `Drift score (CUSUM, log-likelihood ratio) per site from released rater batches, to day ${today}. Higher means stronger evidence raters guess the arm too well`;
  const noData = lines.filter((l) => !l.releases.length).map((l) => l.site);
  const ruleBits = alert?.rule ? alert.rule.match(/p0=([\d.]+), p1=([\d.]+), H=([\d.]+)/) : null;
  const footnotes = (
    <>
      <p>Shaded: above the alarm line{H !== null ? ` ${H}` : ""}. Lines are the score at each released batch, held until the next one.{flagLine?.reset != null ? ` The dotted drop at day ${flagLine.reset} is the reset after the approved action, not a measurement; the line turns solid again at the next released batch.` : ""}</p>
      {ruleBits && <p>Batched Bernoulli CUSUM, p0 {ruleBits[1]}, p1 {ruleBits[2]}, alarm {ruleBits[3]} (from the alert evidence rule).</p>}
      {simDay !== null && <p>Drift began (simulated): the day the simulator planted the rater drift. It is synthetic ground truth that no agent sees; the estimated onset is what the monitor inferred.</p>}
      {noData.length > 0 && <p>No released guesses yet: {noData.join(", ")}.</p>}
    </>
  );
  const evWords = events.map((e) => e.label).join("; ");
  const ariaLabel = `Drift score by site. Alarm line ${H ?? "not available"}. ${detect && flaggedSite ? `${flaggedSite} crossed on day ${detect.day}` : "No site crossed"}${alert?.onset != null ? `; estimated onset day ${alert.onset}` : ""}${simDay !== null ? `; simulated drift start day ${simDay}` : ""}${alert?.actionDay != null ? `; action day ${alert.actionDay}` : ""}${flagLine?.reset != null ? "; reset after action" : ""}. ${lines.map((l) => `${l.site} latest ${l.releases.at(-1) ? fmt(l.releases.at(-1)!.score) : "none"}`).join(", ")}.${evWords ? ` Events: ${evWords}.` : ""}`;

  const tableRows: DataTable["rows"] = [];
  for (const l of lines) {
    for (const r of l.releases) {
      const ev = events.filter((e) => e.day === r.day && l.site === flaggedSite).map((e) => e.label).join("; ");
      tableRows.push({ day: r.day, site: l.site, score: Number(fmt(r.score)), kind: "Released batch", h: r.threshold, event: ev || null });
    }
    if (l.reset !== null) {
      tableRows.push({ day: l.reset, site: l.site, score: 0, kind: "Reset after action (display)", h: H,
        event: events.filter((e) => e.day === l.reset).map((e) => e.label).join("; ") || null });
    }
  }
  for (const e of events) {
    if (!tableRows.some((r) => r.day === e.day && r.site === flaggedSite)) tableRows.push({ day: e.day, site: flaggedSite, score: null, kind: null, h: H, event: e.label });
  }
  tableRows.sort((a, b) => (a.day as number) - (b.day as number));
  const dataTable: DataTable = {
    columns: [
      { key: "day", label: "Day", align: "right" },
      { key: "site", label: "Site" },
      { key: "score", label: "Drift score", align: "right" },
      { key: "kind", label: "Released or reset", derived: true },
      { key: "h", label: "Alarm line", align: "right" },
      { key: "event", label: "Event" },
    ],
    rows: tableRows,
    note: "Drift scores are the record's own cusum on each released rater batch (blinding_metrics, by site). \"Reset after action\" rows are derived: the monitor restarts the score at 0 after an approved action, so the chart draws a dotted drop at the action day, not a measurement. Drift began (simulated) comes from the master's simulated_truth; Detected is the first released batch at or above the alarm line.",
  };

  const empty = error ? { title: "Could not load the blinding record", body: error }
    : !loading && rec && lines.every((l) => !l.releases.length) ? { title: "Too few to show", body: "No site has released rater guesses yet." }
    : null;
  const ticks = dayTicks(Math.max(today, 1), 14);
  const plotH = height ?? (compact ? 240 : 300);
  const labelRows = stackRows(events, compact ? 40 : 4).reduce((m, e) => Math.max(m, e.row + 1), 0);

  return (
    <ChartFrame id={chart.id} title={title} subtitle={subtitle} ariaLabel={ariaLabel} dataTable={dataTable}
      footnotes={footnotes} empty={empty}>
      <div ref={ref} className="dchart-cusum" style={{ height: plotH + labelRows * 14 }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 12 + labelRows * 14, right: compact ? 52 : 64, bottom: 4, left: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis {...axisProps} dataKey="day" type="number" domain={[1, Math.max(today, 2)]} ticks={ticks}
              tickFormatter={(d: number) => formatDayTick(d)} allowDecimals={false} />
            <YAxis {...axisProps} domain={[0, yTop]} width={34} allowDecimals={false}
              label={compact ? undefined : { value: "Drift score", angle: -90, position: "insideLeft", offset: 10, className: "dchart-reflabel" }} />
            {H !== null && <ReferenceArea y1={H} y2={yTop} fill={chartTokens.flag} fillOpacity={chartTokens.alarmFillOpacity} stroke="none" ifOverflow="hidden" />}
            {H !== null && (
              <ReferenceLine y={H} stroke={chartTokens.reference} strokeDasharray={lineStyles.threshold} strokeWidth={1}
                label={{ value: `Alarm line ${H}`, position: "insideTopLeft", className: "dchart-reflabel" }} />
            )}
            {events.map((e) => (
              <ReferenceLine key={`${e.kind}-${e.day}`} x={e.day} stroke={chartTokens.reference} strokeWidth={1}
                strokeDasharray={e.kind === "sim" || e.kind === "onset" ? lineStyles.reference : undefined} ifOverflow="hidden" />
            ))}
            {styled.map(({ l, s }) => (
              <Line key={l.site} dataKey={l.site} type="stepAfter" stroke={s.stroke} strokeDasharray={s.dash}
                strokeWidth={l.site === flaggedSite ? 2.5 : 1.5} dot={false} isAnimationActive={false} connectNulls={false}
                activeDot={{ r: 3.5, stroke: chartTokens.halo, strokeWidth: 2, fill: s.stroke }} />
            ))}
            {styled.filter(({ l }) => l.reset !== null).map(({ l, s }) => (
              <Line key={`${l.site}-reset`} dataKey={`${l.site}__reset`} type="stepAfter" stroke={s.stroke}
                strokeDasharray={lineStyles.derived} strokeWidth={1.5} dot={false} activeDot={false} isAnimationActive={false}
                connectNulls={false} />
            ))}
            {styled.filter(({ l }) => l.reset !== null && l.resetFrom !== null).map(({ l, s }) => (
              <ReferenceLine key={`${l.site}-drop`} segment={[{ x: l.reset!, y: l.resetFrom! }, { x: l.reset!, y: 0 }]}
                stroke={s.stroke} strokeDasharray={lineStyles.derived} strokeWidth={1.5}
                label={compact ? undefined : { value: "Reset after action", position: "right", className: "dchart-reflabel" }} />
            ))}
            {detect && (
              <ReferenceDot x={detect.day} y={detect.score} r={5} fill={chartTokens.flag} stroke={chartTokens.halo} strokeWidth={2} />
            )}
            <Customized component={<Overlay events={events} lines={endLabels} compact={compact} delay={delay} />} />
            <Tooltip content={<TooltipBox lines={lines} threshold={H ?? Infinity} />} cursor={{ stroke: chartTokens.grid }} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {delay && compact && <p className="dchart-callout-text">{delay.text}</p>}
    </ChartFrame>
  );
}
