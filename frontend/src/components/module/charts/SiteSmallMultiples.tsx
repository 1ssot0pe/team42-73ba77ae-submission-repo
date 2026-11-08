/**
 * SiteSmallMultiples (docs/visuals-spec.md section 2, Builder DOSING): one small panel per site or rater with shared
 * axes, for the three guess-accuracy charts on the Dosing page, chosen by chart.id:
 *   rater-accuracy-site        rolling accuracy (last 3 vault batches), raters by site, alarm reference 60%
 *   rater-accuracy-by-rater    the same, one panel per rater at the focus site
 *   participant-accuracy-site  cumulative accuracy with the record's own Wilson bounds, information only
 *
 * Everything drawn comes from the record (`blinding_metrics`, `alerts`, `actions`). Rolling counts are rebuilt from
 * `window_correct` / `window_decisive` with the dosing monitor's rule (last 3 released batches of the group that
 * started after the site's last reset) and used only where they reproduce the record's `rolling_accuracy`.
 * Wilson bands only where n >= 8; released points with fewer are hollow with no band.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  Area, CartesianGrid, ComposedChart, Customized, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  ChartFrame, ROLLING_BATCHES, WILSON_MIN_N, axisProps, chartTokens, dayTicks, formatDayTick, formatPct, gridProps,
  lineStyles, useRecordSections, wilson,
} from "../../shared";
import type { DataTable } from "../../shared";
import type { Chart } from "../normalise";
import type { Alert, BlindingMetric } from "../../../types";
import "./dosing.css";

export interface ModuleChartComponentProps {
  chart: Chart;
  trialId: string;
  height?: number;
}

/* ------------------------------------------------------------------ data from the record (shared with CusumChart) */

export const shortSite = (s: string | null | undefined): string => (s ? String(s).split(" (")[0] : "");
const n0 = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

export interface RecordBits {
  blinding_metrics?: BlindingMetric[];
  alerts?: Alert[];
  actions?: Array<Record<string, unknown>>;
}

/** The last day the drift window for a site was reset (approved remote raters, or a rejected alert), as monitor.py.
 * With `before`, only resets that had happened before that day count (what the monitor saw when it wrote the row). */
export function resetDay(rec: RecordBits, site: string, before = Infinity): number | null {
  const days: number[] = [];
  for (const a of rec.actions ?? []) {
    if (a.module === "dosing" && a.type === "remote_raters" && a.site === site && typeof a.day === "number") days.push(a.day);
  }
  for (const a of rec.alerts ?? []) {
    if (a.kind === "rater_drift" && a.site === site && a.status === "dismissed") {
      const d = n0(a.decided_day) ?? n0(a.day);
      if (d !== null) days.push(d);
    }
  }
  const seen = days.filter((d) => d < before);
  return seen.length ? Math.max(...seen) : null;
}

export interface DriftAlert {
  site: string;          // short name, e.g. "Site B"
  fullSite: string;
  day: number;
  onset: number | null;
  actionDay: number | null;
  resolvedDay: number | null;
  dismissedDay: number | null;
  status: string;
  perRater: Array<{ rater: string; correct: number; n: number }>;
  rule: string;
  correctSinceOnset: number | null;
  nSinceOnset: number | null;
}

export function driftAlerts(rec: RecordBits): DriftAlert[] {
  return (rec.alerts ?? []).filter((a) => a.kind === "rater_drift").map((a) => {
    const ev = (a.evidence ?? {}) as Record<string, unknown>;
    const pr = (ev.per_rater ?? {}) as Record<string, { correct?: number; n?: number }>;
    return {
      site: shortSite(String(a.site ?? "")),
      fullSite: String(a.site ?? ""),
      day: a.day,
      onset: n0(ev.onset_day_estimate),
      actionDay: n0(a.action_day),
      resolvedDay: n0(a.resolved_day),
      dismissedDay: a.status === "dismissed" ? n0(a.decided_day) ?? a.day : null,
      status: String(a.status ?? ""),
      perRater: Object.entries(pr).map(([rater, v]) => ({ rater, correct: n0(v?.correct) ?? 0, n: n0(v?.n) ?? 0 })),
      rule: typeof ev.rule === "string" ? ev.rule : "",
      correctSinceOnset: n0(ev.correct_since_onset),
      nSinceOnset: n0(ev.n_since_onset),
    };
  }).sort((a, b) => a.day - b.day);
}

/** One released vault batch, as plotted. */
export interface Point {
  day: number;
  group: string;         // panel key (short site or rater id)
  site: string;          // short site
  value: number | null;  // plotted proportion
  k: number | null;      // correct (rolling or cumulative)
  n: number | null;      // decisive (rolling or cumulative)
  lo: number | null;
  hi: number | null;
  batches: number;       // batches in the rolling window
  sinceReset: number | null; // the window was cut by a reset on this day
  cumK: number | null;
  cumN: number | null;
  cumLo: number | null;
  cumHi: number | null;
  raw: BlindingMetric;
}

type Mode = "rolling" | "cumulative";

export function buildPoints(rec: RecordBits, who: string, by: string, mode: Mode): Map<string, Point[]> {
  const rows = (rec.blinding_metrics ?? [])
    .filter((m) => m.module === "dosing" && m.who === who && m.by === by && !m.suppressed)
    .sort((a, b) => a.day - b.day);
  const out = new Map<string, Point[]>();
  const prevRows = new Map<string, BlindingMetric[]>();
  for (const r of rows) {
    const group = by === "site" ? shortSite(r.group) : r.group;
    const fullSite = String(r.site ?? (by === "site" ? r.group : ""));
    const prev = prevRows.get(group) ?? [];
    const cumK = n0(r.n_correct);
    const cumN = n0(r.n_decisive);
    let value: number | null;
    let k: number | null = null;
    let n: number | null = null;
    let lo: number | null = null;
    let hi: number | null = null;
    let batches = 1;
    let sinceReset: number | null = null;
    if (mode === "rolling") {
      value = n0(r.rolling_accuracy);
      const rd = fullSite ? resetDay(rec, fullSite, r.day) : null;
      const eligible = rd === null ? prev : prev.filter((b) => (n0(b.window_from) ?? -Infinity) > rd);
      const tail = [...eligible.slice(-(ROLLING_BATCHES - 1)), r];
      const tk = tail.reduce((s, b) => s + (n0(b.window_correct) ?? NaN), 0);
      const tn = tail.reduce((s, b) => s + (n0(b.window_decisive) ?? NaN), 0);
      // use the derived counts only if they reproduce the record's own rolling value
      if (value !== null && Number.isFinite(tk) && Number.isFinite(tn) && tn > 0 && Math.abs(tk / tn - value) <= 0.001) {
        k = tk;
        n = tn;
        batches = tail.length;
        if (rd !== null && tail.length < ROLLING_BATCHES && prev.length >= tail.length) sinceReset = rd;
        const w = n >= WILSON_MIN_N ? wilson(k, n) : null;
        if (w) [lo, hi] = w;
      }
    } else {
      value = n0(r.accuracy);
      k = cumK;
      n = cumN;
      if (n !== null && n >= WILSON_MIN_N) {
        lo = n0(r.accuracy_lo);
        hi = n0(r.accuracy_hi);
      }
    }
    const p: Point = {
      day: r.day, group, site: shortSite(fullSite), value, k, n, lo, hi, batches, sinceReset,
      cumK, cumN, cumLo: n0(r.accuracy_lo), cumHi: n0(r.accuracy_hi), raw: r,
    };
    if (!out.has(group)) out.set(group, []);
    out.get(group)!.push(p);
    prevRows.set(group, [...prev, r]);
  }
  return out;
}

/** Container width, for the 390 px layout decisions that CSS cannot make inside an SVG. */
export function useWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    setW(el.getBoundingClientRect().width);
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((es) => setW(es[0]?.contentRect.width ?? 0));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w];
}

/** Touch rule (spec 0.10): a tooltip opens on tap and closes on scroll or a tap outside the chart, never sticks.
 * Returns a ref for the chart wrapper and whether tooltips should be forced closed. */
export function useTooltipDismiss<T extends HTMLElement>(): [React.RefObject<T>, boolean] {
  const ref = useRef<T>(null);
  const [closed, setClosed] = useState(false);
  useEffect(() => {
    const onScroll = () => setClosed(true);
    const inside = (e: PointerEvent) => !!(ref.current && e.target instanceof Node && ref.current.contains(e.target));
    const onDown = (e: PointerEvent) => setClosed(!inside(e));
    const onMove = (e: PointerEvent) => { if (e.pointerType === "mouse" && inside(e)) setClosed(false); };
    window.addEventListener("scroll", onScroll, { capture: true, passive: true });
    document.addEventListener("pointerdown", onDown, { capture: true });
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll, { capture: true });
      document.removeEventListener("pointerdown", onDown, { capture: true });
      document.removeEventListener("pointermove", onMove);
    };
  }, []);
  return [ref, closed];
}

export const pct = (v: number | null): string => formatPct(v, 0);
const pctNum = (v: number | null): string | null => (v === null ? null : String(Math.round(v * 100)));

/** Event labels within `gap` days of each other stack onto separate rows. */
export function stackRows<T extends { day: number }>(events: T[], gap = 3): Array<T & { row: number }> {
  const sorted = [...events].sort((a, b) => a.day - b.day);
  const out: Array<T & { row: number }> = [];
  for (const e of sorted) {
    const near = out.filter((o) => Math.abs(o.day - e.day) <= gap).map((o) => o.row);
    let row = 0;
    while (near.includes(row)) row++;
    out.push({ ...e, row });
  }
  return out;
}

/* ------------------------------------------------------------------ the chart */

interface PanelEvent {
  day: number;
  label: string;
  short: string;
  kind: "onset" | "alert" | "action" | "resolved" | "rejected";
}

interface Config {
  who: string;
  by: string;
  mode: Mode;
  alarm: boolean;
}

const CONFIG: Record<string, Config> = {
  "rater-accuracy-site": { who: "rater", by: "site", mode: "rolling", alarm: true },
  "rater-accuracy-by-rater": { who: "rater", by: "rater", mode: "rolling", alarm: true },
  "participant-accuracy-site": { who: "participant", by: "site", mode: "cumulative", alarm: false },
};

function eventsFor(alert: DriftAlert): PanelEvent[] {
  const ev: PanelEvent[] = [];
  if (alert.onset !== null) ev.push({ day: alert.onset, label: `Onset est. ${formatDayTick(alert.onset)}`, short: `Onset ${formatDayTick(alert.onset)}`, kind: "onset" });
  ev.push({ day: alert.day, label: `Alert ${formatDayTick(alert.day)}`, short: `Alert ${formatDayTick(alert.day)}`, kind: "alert" });
  if (alert.actionDay !== null) ev.push({ day: alert.actionDay, label: `Remote raters ${formatDayTick(alert.actionDay)}`, short: `Action ${formatDayTick(alert.actionDay)}`, kind: "action" });
  if (alert.resolvedDay !== null) ev.push({ day: alert.resolvedDay, label: `Drift stopped ${formatDayTick(alert.resolvedDay)}`, short: `Stopped ${formatDayTick(alert.resolvedDay)}`, kind: "resolved" });
  if (alert.dismissedDay !== null) ev.push({ day: alert.dismissedDay, label: `Rejected ${formatDayTick(alert.dismissedDay)}`, short: `Rejected ${formatDayTick(alert.dismissedDay)}`, kind: "rejected" });
  return ev;
}

function windowWords(p: Point): string {
  if (p.sinceReset !== null) return `in ${p.batches === 1 ? "the batch" : `the ${p.batches} batches`} since the reset on day ${p.sinceReset}`;
  return p.batches >= ROLLING_BATCHES ? `in the last ${ROLLING_BATCHES} batches` : `in the first ${p.batches === 1 ? "batch" : `${p.batches} batches`}`;
}

function sentence(p: Point, mode: Mode): string {
  const who = `Day ${p.day}, ${p.group}${p.group !== p.site && p.site ? ` (${p.site})` : ""}`;
  if (p.value === null) return `${who}: no released value`;
  if (p.k === null || p.n === null) return `${who}: ${pct(p.value)} correct (counts not available)`;
  const iv = p.lo !== null && p.hi !== null ? `95% interval ${pct(p.lo)} to ${pct(p.hi)}` : `n = ${p.n}, too few for an interval`;
  if (mode === "rolling") return `${who}: ${p.k} of ${p.n} decisive guesses correct ${windowWords(p)} (${pct(p.value)}), ${iv}`;
  return `${who}: ${p.k} of ${p.n} correct (${pct(p.value)}), ${iv}, cumulative`;
}

interface Row {
  day: number;
  v: number | null;
  band: [number, number] | null;
  release: Point | null;
  current: Point | null;
}

function panelRows(points: Point[], today: number): Row[] {
  const rows: Row[] = [];
  let i = 0;
  let cur: Point | null = null;
  for (let d = 1; d <= today; d++) {
    let release: Point | null = null;
    while (i < points.length && points[i].day <= d) {
      cur = points[i];
      if (points[i].day === d) release = points[i];
      i++;
    }
    rows.push({
      day: d,
      v: cur?.value ?? null,
      band: cur && cur.lo !== null && cur.hi !== null ? [cur.lo, cur.hi] : null,
      release,
      current: cur,
    });
  }
  return rows;
}

function TooltipBox({ active, payload, mode }: { active?: boolean; payload?: Array<{ payload?: Row }>; mode: Mode }) {
  const row = payload?.[0]?.payload;
  if (!active || !row?.current) return null;
  const p = row.current;
  const held = p.day !== row.day ? ` (value released on day ${p.day}, held until the next release)` : "";
  return <div className="dchart-tip" role="status">{sentence({ ...p, day: row.day === p.day ? p.day : p.day }, mode)}{held}</div>;
}

interface PanelProps {
  title: string;
  flagged: boolean;
  points: Point[];
  today: number;
  height: number;
  mode: Mode;
  alarm: boolean;
  events: PanelEvent[];
  compact: boolean;
  labelRows: number;
  labelRefs: boolean;
}

/** Event labels above the plot, one row each (panels are narrow), drawn with a halo. */
function EventLabels({ events, compact, ...rest }: { events: PanelEvent[]; compact: boolean } & Record<string, unknown>) {
  const xAxisMap = rest.xAxisMap as Record<string, { scale: (v: number) => number }> | undefined;
  const offset = rest.offset as { top: number; left: number; width: number } | undefined;
  const xs = xAxisMap ? Object.values(xAxisMap)[0]?.scale : undefined;
  if (!xs || !offset) return null;
  const sorted = [...events].sort((a, b) => a.day - b.day);
  return (
    <g className="dchart-events">
      {sorted.map((e, i) => {
        const x = xs(e.day);
        const y = offset.top - 5 - (sorted.length - 1 - i) * 13;
        return <line key={`t-${e.kind}-${e.day}`} x1={x} x2={x} y1={y + 3} y2={offset.top} className="dchart-evtick" />;
      })}
      {sorted.map((e, i) => {
        const x = xs(e.day);
        const right = x > offset.left + offset.width * 0.5;
        const y = offset.top - 5 - (sorted.length - 1 - i) * 13;
        return (
          <g key={`${e.kind}-${e.day}`}>
            <text x={right ? x - 3 : x + 3} y={y} textAnchor={right ? "end" : "start"}
              className={`dchart-evlabel${e.kind === "alert" ? " dchart-evlabel--alert" : ""}`}>
              {compact ? e.short : e.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function Panel({ title, flagged, points, today, height, mode, alarm, events, compact, labelRows, labelRefs }: PanelProps) {
  const rows = panelRows(points, today);
  const colour = flagged ? chartTokens.flag : chartTokens.primary;
  const ticks = dayTicks(today, compact ? 14 : 14);
  const tooFew = points.length === 0;
  const topPad = 8 + 13 * labelRows;
  const [tipRef, tipClosed] = useTooltipDismiss<HTMLDivElement>();
  return (
    <div className={`dchart-panel${flagged ? " dchart-panel--flag" : ""}`}>
      <p className="dchart-panel__title">{title}</p>
      <div ref={tipRef} className="dchart-panel__plot" style={{ height: height + topPad }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: topPad, right: 10, bottom: 0, left: 0 }}>
            <CartesianGrid {...gridProps} />
            <XAxis {...axisProps} dataKey="day" type="number" domain={[1, Math.max(today, 2)]} ticks={ticks}
              tickFormatter={(d: number) => formatDayTick(d)} allowDecimals={false} />
            <YAxis {...axisProps} domain={[0, 1]} ticks={[0, 0.5, 1]} width={38}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`} />
            <ReferenceLine y={0.5} stroke={chartTokens.reference} strokeDasharray={lineStyles.reference} strokeWidth={1}
              label={labelRefs ? { value: "Coin flip 50%", position: "insideBottomRight", className: "dchart-reflabel" } : undefined} />
            {alarm && (
              <ReferenceLine y={0.6} stroke={chartTokens.reference} strokeDasharray={lineStyles.threshold} strokeWidth={1}
                label={labelRefs ? { value: "Alarm reference 60%", position: "insideTopRight", className: "dchart-reflabel" } : undefined} />
            )}
            {events.map((e) => (
              <ReferenceLine key={`${e.kind}-${e.day}`} x={e.day} stroke={chartTokens.reference} strokeWidth={1}
                ifOverflow="hidden" />
            ))}
            {!tooFew && (
              <Area dataKey="band" type="stepAfter" stroke="none" fill={colour} fillOpacity={chartTokens.bandOpacity}
                isAnimationActive={false} connectNulls={false} activeDot={false} />
            )}
            {!tooFew && (
              <Line dataKey="v" type="stepAfter" stroke={colour} strokeWidth={2} isAnimationActive={false}
                connectNulls={false}
                dot={(props: { cx?: number; cy?: number; payload?: Row; index?: number }) => {
                  const r = props.payload?.release;
                  if (!r || r.value === null || props.cx === undefined || props.cy === undefined) return <g key={props.index} />;
                  const solid = r.n !== null && r.n >= WILSON_MIN_N;
                  return flagged
                    ? <circle key={props.index} cx={props.cx} cy={props.cy} r={3.2} stroke={colour} strokeWidth={1.5}
                        fill={solid ? colour : chartTokens.halo} />
                    : <rect key={props.index} x={props.cx - 3} y={props.cy - 3} width={6} height={6} stroke={colour}
                        strokeWidth={1.5} fill={solid ? colour : chartTokens.halo} />;
                }}
                activeDot={tipClosed ? false : { r: 4, stroke: chartTokens.halo, strokeWidth: 2, fill: colour }} />
            )}
            {events.length > 0 && <Customized component={<EventLabels events={events} compact={compact} />} />}
            {!tooFew && <Tooltip content={<TooltipBox mode={mode} />} cursor={{ stroke: chartTokens.grid }}
              active={tipClosed ? false : undefined} />}
          </ComposedChart>
        </ResponsiveContainer>
        {tooFew && <p className="dchart-panel__few">Too few to show (fewer than 5 guesses so far)</p>}
      </div>
    </div>
  );
}

export function SiteSmallMultiples({ chart, trialId, height }: ModuleChartComponentProps): JSX.Element {
  const cfg = CONFIG[chart.id] ?? CONFIG["rater-accuracy-site"];
  const { data: rec, loading, error } = useRecordSections(trialId, ["blinding_metrics", "alerts", "actions"]);
  const [ref, width] = useWidth<HTMLDivElement>();
  const compact = width > 0 && width < 560;

  const today = chart.data.reduce((m, r) => Math.max(m, typeof r.day === "number" ? r.day : 0), 0);
  const groups = chart.series.map((s) => s.key);
  const points = rec ? buildPoints(rec, cfg.who, cfg.by, cfg.mode) : new Map<string, Point[]>();
  const alerts = rec ? driftAlerts(rec) : [];
  const alertBySite = new Map<string, DriftAlert>();
  for (const a of alerts) alertBySite.set(a.site, a); // latest per site
  const siteOf = (g: string): string => (cfg.by === "site" ? g : points.get(g)?.[0]?.site ?? "");
  const latest = (g: string): Point | null => points.get(g)?.at(-1) ?? null;
  const showEvents = cfg.who === "rater";
  const latestAlert = alerts.at(-1) ?? null;

  // ---- takeaway title, subtitle
  let title: string;
  let subtitle: string;
  const daysWord = `to day ${today}`;
  if (cfg.mode === "cumulative") {
    const vals = groups.map(latest).filter((p): p is Point => p !== null && p.value !== null);
    if (vals.length) {
      const lo = Math.min(...vals.map((p) => p.value as number));
      const hi = Math.max(...vals.map((p) => p.value as number));
      const d = Math.max(...vals.map((p) => p.day));
      title = lo === hi
        ? `Participants guess their arm correctly ${pctNum(lo)}% of the time (day ${d})`
        : `Participants guess their arm correctly ${pctNum(lo)}% to ${pctNum(hi)}% of the time (day ${d})`;
    } else title = "Participant guess accuracy by site";
    subtitle = "Correct among decisive drug or control guesses, cumulative since dosing. Information only, no alarm is set on participant guesses";
  } else if (cfg.by === "rater") {
    const site = siteOf(groups[0] ?? "") || latestAlert?.site || "";
    const a = site ? alertBySite.get(site) : undefined;
    // The alert is a site-level finding. Per-rater counts are partial (only batches that began after the estimated
    // onset are attributed) and small, so the title states the site evidence first and lists every named rater with n.
    const perRater = (a?.perRater ?? []).filter((r) => r.n > 0)
      .map((r) => `${r.rater} ${r.correct} of ${r.n}${r.n < WILSON_MIN_N ? " (too few for an interval)" : ""}`);
    const since = a && a.correctSinceOnset !== null && a.nSinceOnset !== null
      ? ` (${a.correctSinceOnset} of ${a.nSinceOnset} correct since estimated onset)` : "";
    title = a ? `${site} raters flagged for drift on day ${a.day}${since}${perRater.length ? `; per rater, ${perRater.join(", ")}` : ""}`
      : site ? `Rater accuracy at ${site}, by rater` : "Rater accuracy by rater";
    subtitle = a ? `Raters at ${site}, the site with the latest drift alert. Correct among decisive guesses, last ${ROLLING_BATCHES} vault batches, ${daysWord}`
      : site ? `Raters at ${site}, the site with the highest current drift score. Correct among decisive guesses, last ${ROLLING_BATCHES} vault batches, ${daysWord}`
      : `Correct among decisive guesses, last ${ROLLING_BATCHES} vault batches, ${daysWord}`;
  } else {
    title = latestAlert
      ? `${latestAlert.site} raters flagged for drift on day ${latestAlert.day}${latestAlert.actionDay !== null ? `; remote raters approved day ${latestAlert.actionDay}` : ""}`
      : `No rater drift alert at any site ${daysWord}`;
    subtitle = `Correct among decisive drug or control guesses by outcome raters, last ${ROLLING_BATCHES} vault batches per site, ${daysWord}`;
  }

  // ---- panels
  const panels = groups.map((g) => {
    const site = siteOf(g);
    const a = showEvents ? alertBySite.get(site) : undefined;
    // every rater at the alerted site is coloured the same way: the alert is about the site, not one rater
    const flagged = !!a && cfg.who === "rater";
    const named = a?.perRater.find((r) => r.rater === g && r.n > 0);
    const label = cfg.by === "site" && a && cfg.who === "rater" ? `${g}, drift alert day ${a.day}`
      : cfg.by === "rater" && named ? `${g}, named in alert evidence (n = ${named.n})` : g;
    return { g, site, flagged, label, events: a ? eventsFor(a) : [], pts: points.get(g) ?? [] };
  });

  // ---- aria and View data
  const ariaParts = panels.map(({ g, pts }) => {
    const p = pts.at(-1);
    if (!p || p.value === null) return `${g}: too few to show`;
    const iv = p.lo !== null && p.hi !== null ? ` (${pctNum(p.lo)} to ${pctNum(p.hi)})` : ", too few for an interval";
    return `${g}: ${pctNum(p.value)}%${p.n !== null ? ` of ${p.n}` : ""}${iv}`;
  });
  const evText = latestAlert && showEvents ? ` ${eventsFor(latestAlert).map((e) => `${e.label} at ${latestAlert.site}`).join(", ")}.` : "";
  const ariaLabel = `${cfg.who === "rater" ? "Rater" : "Participant"} guess accuracy by ${cfg.by}, ${cfg.mode === "rolling" ? `last ${ROLLING_BATCHES} vault batches` : "cumulative"}. ${ariaParts.join(". ")}. Coin flip 50%${cfg.alarm ? ", alarm reference 60%" : ""}.${evText}`;

  const tableRows: DataTable["rows"] = [];
  for (const { g, pts } of panels) {
    for (const p of pts) {
      tableRows.push({
        day: p.day, group: g, k: p.k, n: p.n, value: p.value === null ? null : Math.round(p.value * 1000) / 10,
        lo: p.lo === null ? null : Math.round(p.lo * 1000) / 10, hi: p.hi === null ? null : Math.round(p.hi * 1000) / 10,
        cum: p.cumK !== null && p.cumN !== null ? `${p.cumK} of ${p.cumN}` : null,
        cumci: p.cumLo !== null && p.cumHi !== null ? `${pctNum(p.cumLo)}% to ${pctNum(p.cumHi)}%` : null,
      });
    }
  }
  tableRows.sort((a, b) => (a.day as number) - (b.day as number));
  const rolling = cfg.mode === "rolling";
  const dataTable: DataTable = {
    columns: [
      { key: "day", label: "Day", align: "right" },
      { key: "group", label: cfg.by === "site" ? "Site" : "Rater" },
      { key: "k", label: rolling ? "Correct (window)" : "Correct", align: "right", derived: rolling },
      { key: "n", label: rolling ? "Decisive (window)" : "Decisive", align: "right", derived: rolling },
      { key: "value", label: rolling ? "Rolling accuracy (%)" : "Accuracy (%)", align: "right" },
      { key: "lo", label: "95% low (%)", align: "right", derived: rolling },
      { key: "hi", label: "95% high (%)", align: "right", derived: rolling },
      ...(rolling ? [
        { key: "cum", label: "Cumulative correct", align: "right" as const },
        { key: "cumci", label: "Cumulative 95% interval", align: "right" as const },
      ] : []),
    ],
    rows: tableRows,
    note: rolling
      ? `From the trial record (blinding_metrics, released vault batches only). Window counts are the sum of window_correct and window_decisive over the last ${ROLLING_BATCHES} released batches of the group that began after the site's last reset, the dosing monitor's rule; they are shown only where they reproduce the recorded rolling accuracy within 0.001. The 95% interval is Wilson's, computed here from those counts, and only where the window holds ${WILSON_MIN_N} or more decisive guesses.`
      : `From the trial record (blinding_metrics, released vault batches only). Accuracy and its 95% Wilson interval are the record's own cumulative values; the interval is shown only where ${WILSON_MIN_N} or more decisive guesses exist.`,
  };

  const footnotes = (
    <>
      <p>Points mark each released vault batch; the line holds that value until the next one. Groups with fewer than 5 guesses are hidden by the vault.</p>
      {cfg.alarm && <p>Alarm reference 60%: the upper end of what raters are expected to reach under working blinding (50% to 60%). The alarm itself is the drift score on the CUSUM chart.</p>}
      {cfg.by === "rater" && <p>Per-rater groups are small; intervals appear once a rater has {WILSON_MIN_N} or more guesses in the window.</p>}
      {panels.some((p) => p.flagged) && <p>{cfg.by === "rater" ? "Orange line with circles and a dot by the name: a rater at the site with the drift alert." : "Orange line with circles and a dot by the name: the site with a drift alert. Violet squares: no alert."}</p>}
      {cfg.by === "rater" && latestAlert && <p>The alert evidence attributes guesses to raters only from batches that began after the estimated onset, so a rater missing from it is not cleared.</p>}
    </>
  );

  const anyData = panels.some((p) => p.pts.length > 0);
  const empty = error ? { title: "Could not load the blinding record", body: error }
    : !loading && rec && groups.length === 0 ? { title: "Too few to show", body: "No sites with released guesses yet." }
    : null;
  const panelHeight = height ?? (compact ? 140 : 170);

  return (
    <ChartFrame id={chart.id} title={rec ? title : chart.title} subtitle={subtitle} ariaLabel={ariaLabel}
      dataTable={anyData ? dataTable : undefined} footnotes={footnotes} empty={empty}>
      <div ref={ref} className={`dchart-grid${compact ? " dchart-grid--stack" : ""}`}
        style={{ ["--dchart-cols" as string]: String(Math.max(1, panels.length)) }}>
        {panels.map((p, i) => (
          <Panel key={p.g} title={p.label} flagged={p.flagged} points={p.pts} today={Math.max(today, 1)} height={panelHeight}
            mode={cfg.mode} alarm={cfg.alarm} events={p.events} compact={compact}
            labelRows={Math.max(0, ...panels.map((x) => x.events.length))} labelRefs={i === panels.length - 1} />
        ))}
      </div>
      <div className="dchart-key" aria-hidden="true">
        <span><svg width="14" height="10"><rect x="2" y="2" width="6" height="6" className="dchart-key__band" /></svg>95% interval (8 or more guesses)</span>
        <span><svg width="12" height="10"><rect x="2" y="2" width="6" height="6" className="dchart-key__hollow" /></svg>Fewer than 8, no interval</span>
      </div>
    </ChartFrame>
  );
}
