/**
 * ReportAccuracy (docs/visuals-spec.md, "report-rater-accuracy-site"): rater guess accuracy by site as the FDA
 * report uses it, i.e. CUMULATIVE since day 1, not the Dosing chart's last-3-batches window.
 *
 * Small multiples, one panel per site. Values, counts and 95% bounds come from the record's
 * `blinding_metrics` rows with the postdose view's own filter (who rater, by site, accuracy present, not
 * suppressed); each value is checked against the view's chart and a row that disagrees is left out. Bands use
 * the record's own `accuracy_lo/hi` and only where n >= 8 decisive guesses (stats.WILSON_MIN_N); smaller n gets a
 * hollow marker and no band. x runs from day 1 to today so it lines up with the Dosing chart. The line stops at
 * the last release: nothing is carried past the last measurement. Events come from the record's rater drift
 * alerts. "Coin flip 50%" is drawn because chance is 50% among decisive guesses under 1:1 block randomisation.
 */
import { useState } from "react";
import type { Alert, BlindingMetric } from "../../../types";
import { useTrial } from "../../../trial";
import { ChartFrame, chartTokens, useRecordSections } from "../../shared";
import type { ChartStatus, DataTable } from "../../shared";
import { ChartTip, useTip, useWidth, type ModuleChartComponentProps } from "./EffectForest";
import "./postdose.css";

export type { ModuleChartComponentProps } from "./EffectForest";

const WILSON_MIN = 8; // mirrors stats.WILSON_MIN_N (unblind/platform/dosing/stats.py)

interface Pt {
  day: number;
  acc: number;
  k: number | null;
  n: number | null;
  lo: number | null;
  hi: number | null;
}

interface Ev {
  day: number;
  label: string;
}

interface Panel {
  site: string;
  pts: Pt[];
  alert: Alert | null;
  events: Ev[];
}

const short = (s: string) => (s || "").split(" (")[0];
const pct = (v: number) => `${Math.round(v * 100)}%`;
const num = (v: unknown): number | null => (typeof v === "number" && Number.isFinite(v) ? v : null);

function eventsFor(a: Alert | null): Ev[] {
  if (!a) return [];
  const ev = (a.evidence ?? {}) as Record<string, unknown>;
  const raw: Ev[] = [];
  const onset = num(ev.onset_day_estimate);
  if (onset !== null) raw.push({ day: onset, label: "Onset est." });
  raw.push({ day: a.day, label: "Alert" });
  const act = num(a.action_day);
  if (act !== null) raw.push({ day: act, label: "Action" });
  const res = num(a.resolved_day);
  if (res !== null) raw.push({ day: res, label: "Resolved" });
  // Same-day events share one rule and one label.
  const by = new Map<number, string[]>();
  for (const e of raw) by.set(e.day, [...(by.get(e.day) ?? []), e.label]);
  return [...by.entries()].sort((x, y) => x[0] - y[0]).map(([day, ls]) => ({
    day, label: `${ls.map((l, i) => (i === 0 ? l : l.toLowerCase())).join(" and ")} D${day}`,
  }));
}

export function ReportAccuracy({ chart, trialId, height }: ModuleChartComponentProps): JSX.Element {
  const [boxRef, width] = useWidth<HTMLDivElement>();
  const { tip, show, hide, toggle } = useTip(boxRef);
  const { state } = useTrial();
  const { data: rec } = useRecordSections(trialId, ["blinding_metrics", "alerts", "report"]);
  const [focusIdx, setFocusIdx] = useState<Record<string, number>>({});

  // Sites and values from the view's own chart; counts and bounds from the record.
  const sites = chart.series.map((s) => s.key);
  const viewVal = new Map<string, number>(); // `${site}|${day}` -> value as the view sent it
  for (const r of chart.data) {
    const d = num(r[chart.x || "day"]);
    if (d === null) continue;
    for (const s of sites) {
      const v = num(r[s]);
      if (v !== null) viewVal.set(`${s}|${d}`, v);
    }
  }
  const metrics = ((rec?.blinding_metrics ?? []) as BlindingMetric[]).filter((m) =>
    m.who === "rater" && m.by === "site" && m.accuracy !== null && !m.suppressed);
  const alerts = ((rec?.alerts ?? []) as Alert[]).filter((a) => (a as Record<string, unknown>).kind === "rater_drift");

  const panels: Panel[] = sites.map((site) => {
    let pts: Pt[];
    if (metrics.length) {
      pts = metrics.filter((m) => short(m.group) === site)
        .map((m) => ({
          day: m.day, acc: m.accuracy as number,
          k: num(m.n_correct), n: num(m.n_decisive), lo: m.accuracy_lo, hi: m.accuracy_hi,
        }))
        .filter((p) => {
          const v = viewVal.get(`${site}|${p.day}`);
          return v === undefined || Math.abs(v - p.acc) < 0.001;
        })
        .sort((a, b) => a.day - b.day);
    } else {
      // Record not loaded yet: the view's own release points (a release is a day where the value changes or starts).
      pts = [];
      let prev: number | null = null;
      for (const r of chart.data) {
        const d = num(r[chart.x || "day"]);
        const v = num(r[site]);
        if (d === null || v === null) continue;
        if (prev === null || v !== prev) pts.push({ day: d, acc: v, k: null, n: null, lo: null, hi: null });
        prev = v;
      }
    }
    const site_alerts = alerts.filter((a) => short(String((a as Record<string, unknown>).site ?? "")) === site);
    const alert = site_alerts[site_alerts.length - 1] ?? null;
    return { site, pts, alert, events: eventsFor(alert) };
  });

  const today = Math.max(1, state?.day ?? 0, ...panels.flatMap((p) => p.pts.map((x) => x.day)), ...panels.flatMap((p) => p.events.map((e) => e.day)));
  const lastRelease = Math.max(0, ...panels.flatMap((p) => p.pts.map((x) => x.day)));

  // Title: alerted site's cumulative peak in the report, else the latest range across sites.
  const alerted = panels.find((p) => p.alert && p.pts.length) ?? null;
  let title = "Rater guess accuracy by site, as the report records it";
  if (alerted) {
    // Peak among points with enough guesses for an interval, so an early 4 of 5 never sets the headline.
    const solid = alerted.pts.filter((x) => x.n === null || x.n >= WILSON_MIN);
    const peak = (solid.length ? solid : alerted.pts).reduce((a, b) => (b.acc > a.acc ? b : a));
    title = `In the report, ${alerted.site} raters reach ${pct(peak.acc)} correct (cumulative${peak.k !== null && peak.n !== null ? `, ${peak.k} of ${peak.n}` : ""}) by day ${peak.day}`;
  } else {
    const lasts = panels.filter((p) => p.pts.length).map((p) => p.pts[p.pts.length - 1].acc);
    if (lasts.length) title = `In the report, raters are right ${pct(Math.min(...lasts))} to ${pct(Math.max(...lasts))} of the time (cumulative, day ${lastRelease})`;
  }
  const subtitle = `Cumulative share of decisive rater guesses that were correct, day 1 to day ${today}, with 95% intervals. The Dosing chart shows the last 3 batches instead, so its peaks are higher and later.`;

  const report = (rec?.report ?? null) as Record<string, unknown> | null;
  const repStatus = typeof report?.status === "string" ? (report.status as string) : null;
  const status: ChartStatus | undefined = repStatus && repStatus !== "not_started"
    ? { label: `Report ${repStatus.replace(/_/g, " ")}`, tone: repStatus === "final" ? "good" : repStatus === "changes_requested" ? "alert" : "watch" }
    : undefined;

  const empty = panels.every((p) => p.pts.length === 0);

  const dataTable: DataTable = {
    columns: [
      { key: "day", label: "Day", align: "right" },
      { key: "site", label: "Site" },
      { key: "k", label: "Correct since day 1", align: "right" },
      { key: "n", label: "Decisive guesses since day 1", align: "right" },
      { key: "acc", label: "Cumulative accuracy", align: "right" },
      { key: "lo", label: "95% low", align: "right" },
      { key: "hi", label: "95% high", align: "right" },
      { key: "band", label: "Interval drawn", derived: true },
    ],
    rows: panels.flatMap((p) => p.pts.map((x) => ({
      day: x.day, site: p.site, k: x.k, n: x.n, acc: pct(x.acc),
      lo: x.lo !== null ? pct(x.lo) : null, hi: x.hi !== null ? pct(x.hi) : null,
      band: x.n !== null && x.n >= WILSON_MIN && x.lo !== null ? "Yes" : "No, fewer than 8 guesses",
    }))).sort((a, b) => (a.day as number) - (b.day as number)),
    note: "Rows and 95% Wilson bounds are the trial record's blinding metrics (rater, by site, released rows only), the same rows the report uses. An interval is drawn only from 8 decisive guesses. Events are the record's rater drift alerts.",
  };

  const evText = panels.flatMap((p) => p.events.map((e) => `${p.site} ${e.label}`)).join(", ");
  const aria = `Rater guess accuracy by site, cumulative since day 1, as the report records it. `
    + panels.map((p) => {
      const l = p.pts[p.pts.length - 1];
      if (!l) return `${p.site}: too few to show`;
      return `${p.site}: ${pct(l.acc)} on day ${l.day}${l.k !== null && l.n !== null ? ` (${l.k} of ${l.n})` : ""}${l.lo !== null && l.hi !== null ? `, 95% interval ${pct(l.lo)} to ${pct(l.hi)}` : ""}`;
    }).join("; ")
    + `. Coin flip 50%.${evText ? ` Events: ${evText}.` : ""}`;

  // Layout: panels in a row on wide screens, stacked on narrow ones.
  const narrow = width > 0 && width < 640;
  const cols = narrow ? 1 : Math.max(1, panels.length);
  const gap = 18;
  const panelW = cols > 0 && width > 0 ? (width - gap * (cols - 1)) / cols : 0;
  const plotH = narrow ? 140 : Math.max(150, (height ?? 220) - 40);
  const padL = 36;
  const padR = 10;
  const headH = 22;
  const evRowH = 13;
  const maxEvRows = Math.max(0, ...panels.map((p) => p.events.length));
  const evH = maxEvRows ? maxEvRows * evRowH + 4 : 0;
  const axisH = 22;
  const panelH = headH + evH + plotH + axisH;
  const rowsN = Math.ceil(panels.length / cols);
  const H = rowsN * panelH + (rowsN - 1) * 12;

  const dayTicks = (() => {
    const out = [1];
    const step = narrow ? 14 : today > 60 ? 14 : 7;
    for (let d = step; d < today; d += step) if (today - d >= step / 2) out.push(d);
    if (today > 1) out.push(today);
    return out;
  })();

  return (
    <ChartFrame
      id="report-rater-accuracy-site"
      title={title}
      subtitle={subtitle}
      status={status}
      ariaLabel={aria}
      dataTable={dataTable}
      dataTitle="Data: rater accuracy by site in the report"
      footnotes={
        <>
          <p>Cumulative: each point counts every decisive rater guess at that site since day 1. Hollow markers have fewer than 8 guesses, so no interval is drawn.</p>
          {lastRelease > 0 && lastRelease < today ? <p>{`The last rater guesses were released on day ${lastRelease}; nothing is drawn after that.`}</p> : null}
        </>
      }
      empty={empty ? { title: "Too few to show", body: "Fewer than 5 rater guesses released at any site so far." } : null}
    >
      <div className="pd-chart" ref={boxRef} onPointerLeave={(e) => { if (e.pointerType === "mouse") hide(); }}>
        {width > 0 ? (
          <svg className="pd-svg" width={width} height={H} viewBox={`0 0 ${width} ${H}`} aria-hidden="true" focusable="false">
            {panels.map((p, pi) => {
              const col = pi % cols;
              const row = Math.floor(pi / cols);
              const ox = col * (panelW + gap);
              const oy = row * (panelH + 12);
              const x0 = ox + padL;
              const x1 = ox + panelW - padR;
              const yTop = oy + headH + evH;
              const yBot = yTop + plotH;
              const sx = (d: number) => x0 + ((d - 1) / Math.max(1, today - 1)) * (x1 - x0);
              const sy = (v: number) => yBot - v * plotH;
              const color = p.alert ? chartTokens.flag : chartTokens.primary;
              const pts = p.pts;
              const lastDay = pts.length ? pts[pts.length - 1].day : 0;
              // step-after path ending at the last release (a short tick so the last value is visible)
              const stepEnd = (i: number) => (i + 1 < pts.length ? pts[i + 1].day : Math.min(today, lastDay + 1));
              let line = "";
              pts.forEach((pt, i) => {
                line += `${i === 0 ? "M" : "L"}${sx(pt.day)},${sy(pt.acc)} L${sx(stepEnd(i))},${sy(pt.acc)} `;
              });
              let band = "";
              const bandPts = pts.map((pt, i) => ({ ...pt, end: stepEnd(i) }));
              const runs: typeof bandPts[] = [];
              let cur: typeof bandPts = [];
              for (const b of bandPts) {
                if (b.n !== null && b.n >= WILSON_MIN && b.lo !== null && b.hi !== null) cur.push(b);
                else if (cur.length) { runs.push(cur); cur = []; }
              }
              if (cur.length) runs.push(cur);
              for (const r of runs) {
                const upper = r.map((b) => `L${sx(b.day)},${sy(b.hi as number)} L${sx(b.end)},${sy(b.hi as number)}`).join(" ");
                const lowerPath = [...r].reverse().map((b) => `L${sx(b.end)},${sy(b.lo as number)} L${sx(b.day)},${sy(b.lo as number)}`).join(" ");
                band += `M${upper.slice(1)} ${lowerPath} Z `;
              }
              const fi = focusIdx[p.site];
              const tipAt = (i: number) => {
                const pt = pts[i];
                const counts = pt.k !== null && pt.n !== null ? `${pt.k} of ${pt.n} decisive guesses correct since day 1 (${pct(pt.acc)})` : `${pct(pt.acc)} correct since day 1`;
                const ci = pt.n !== null && pt.n < WILSON_MIN ? `, n = ${pt.n}, too few for an interval`
                  : pt.lo !== null && pt.hi !== null ? `, 95% interval ${pct(pt.lo)} to ${pct(pt.hi)}` : "";
                return { key: `${p.site}|${pt.day}`, x: sx(pt.day), y: sy(pt.acc) + 14, text: `Day ${pt.day}, ${p.site}: ${counts}${ci}.` };
              };
              const pick = (clientX: number, target: SVGElement) => {
                const svg = target.ownerSVGElement ?? (target as unknown as SVGSVGElement);
                const r = svg.getBoundingClientRect();
                const day = 1 + ((clientX - r.left - x0) / (x1 - x0)) * (today - 1);
                let idx = -1;
                for (let i = 0; i < pts.length; i++) if (pts[i].day <= day + 0.5) idx = i;
                if (idx < 0 || day > stepEnd(idx) + 2) return null;
                return idx;
              };
              const titleText = p.alert ? `${p.site}: drift alert day ${p.alert.day}` : p.site;
              // stack event labels: one row each, in day order
              return (
                <g key={p.site}>
                  <text className={`pd-panel-title${p.alert ? " pd-panel-title--flag" : ""}`} x={ox + 2} y={oy + 15}>{titleText}</text>
                  {/* grid and axes */}
                  {[0, 0.5, 1].map((v) => (
                    <g key={v}>
                      <line x1={x0} x2={x1} y1={sy(v)} y2={sy(v)} stroke={chartTokens.grid} />
                      <text className="pd-tick" x={x0 - 6} y={sy(v) + 4} textAnchor="end">{`${v * 100}%`}</text>
                    </g>
                  ))}
                  <line x1={x0} x2={x1} y1={yBot} y2={yBot} stroke={chartTokens.axis} />
                  {dayTicks.map((d, i) => (
                    <text key={d} className="pd-tick" x={sx(d)} y={yBot + 15}
                      textAnchor={i === 0 ? "start" : i === dayTicks.length - 1 ? "end" : "middle"}>{`D${d}`}</text>
                  ))}
                  {/* events */}
                  {p.events.map((e, ei) => (
                    <g key={e.day}>
                      <line x1={sx(e.day)} x2={sx(e.day)} y1={oy + headH + ei * evRowH + 6} y2={yBot} stroke={chartTokens.reference} strokeWidth={1} strokeOpacity={0.7} />
                      <text className="pd-ev" x={sx(e.day) + (sx(e.day) > (x0 + x1) / 2 ? -4 : 4)} y={oy + headH + ei * evRowH + 10}
                        textAnchor={sx(e.day) > (x0 + x1) / 2 ? "end" : "start"}>{e.label}</text>
                    </g>
                  ))}
                  {/* coin flip */}
                  <line x1={x0} x2={x1} y1={sy(0.5)} y2={sy(0.5)} stroke={chartTokens.reference} strokeWidth={1} strokeDasharray="4 4" />
                  {pi === 0 || narrow ? (
                    <text className="pd-ref" x={x1 - 2} y={sy(0.5) + 13} textAnchor="end">Coin flip 50%</text>
                  ) : null}
                  {band ? <path d={band} fill={color} fillOpacity={0.12} stroke="none" /> : null}
                  {line ? <path d={line} fill="none" stroke={color} strokeWidth={2} /> : null}
                  {pts.map((pt) => (pt.n !== null && pt.n < WILSON_MIN ? (
                    <circle key={pt.day} cx={sx(pt.day)} cy={sy(pt.acc)} r={3.5} fill={chartTokens.halo} stroke={color} strokeWidth={1.5} />
                  ) : null))}
                  {pts.length ? (
                    <text className="pd-val" x={Math.min(x1, sx(stepEnd(pts.length - 1)) + 4)} y={sy(pts[pts.length - 1].acc) - 6}
                      textAnchor={sx(stepEnd(pts.length - 1)) + 40 > x1 ? "end" : "start"}>{pct(pts[pts.length - 1].acc)}</text>
                  ) : (
                    <text className="pd-too-few" x={(x0 + x1) / 2} y={sy(0.75)} textAnchor="middle">Too few to show</text>
                  )}
                  {fi !== undefined && pts[fi] ? (
                    <circle cx={sx(pts[fi].day)} cy={sy(pts[fi].acc)} r={5} fill={color} stroke={chartTokens.halo} strokeWidth={2} />
                  ) : null}
                  {/* hit area: hover, tap and arrow keys move through releases */}
                  {pts.length ? (
                    <rect
                      className="pd-hit"
                      x={x0} y={yTop} width={Math.max(0, x1 - x0)} height={plotH} fill="transparent"
                      tabIndex={0}
                      role="button"
                      aria-label={`${p.site} panel. Use left and right arrow keys to read each release.`}
                      onPointerMove={(e) => {
                        if (e.pointerType !== "mouse") return;
                        const i = pick(e.clientX, e.currentTarget);
                        if (i === null) { hide(); setFocusIdx((s) => { const n = { ...s }; delete n[p.site]; return n; }); return; }
                        setFocusIdx((s) => ({ ...s, [p.site]: i }));
                        show(tipAt(i));
                      }}
                      onPointerLeave={() => setFocusIdx((s) => { const n = { ...s }; delete n[p.site]; return n; })}
                      onClick={(e) => {
                        const i = pick(e.clientX, e.currentTarget);
                        if (i === null) { hide(); return; }
                        setFocusIdx((s) => ({ ...s, [p.site]: i }));
                        toggle(tipAt(i));
                      }}
                      onFocus={() => { const i = fi ?? pts.length - 1; setFocusIdx((s) => ({ ...s, [p.site]: i })); show(tipAt(i)); }}
                      onBlur={() => { hide(); setFocusIdx((s) => { const n = { ...s }; delete n[p.site]; return n; }); }}
                      onKeyDown={(e) => {
                        if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
                        e.preventDefault();
                        const cur = fi ?? pts.length - 1;
                        const i = Math.max(0, Math.min(pts.length - 1, cur + (e.key === "ArrowRight" ? 1 : -1)));
                        setFocusIdx((s) => ({ ...s, [p.site]: i }));
                        show(tipAt(i));
                      }}
                    />
                  ) : null}
                </g>
              );
            })}
          </svg>
        ) : null}
        <ChartTip tip={tip} width={width} />
      </div>
    </ChartFrame>
  );
}
