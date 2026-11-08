/**
 * risk-scale: predicted unblinding on Design review (visuals spec, chart E).
 * One 0 to 1 line, "share who can tell the arm". The current value is a violet filled circle with its
 * ± 1 SD bar (the model gives an SD, not an interval). Earlier protocol versions form a short trail of
 * small hollow smoke circles on the same line, each labelled with the fix that moved it. Only versions
 * that moved u by at least 0.005 get a label; the rest are counted in a footnote. Band cut-offs are
 * those in ProtocolCoDesigner.risk (agents.py: low < 0.35, medium < 0.6, high otherwise).
 * The trail comes from the predose view's design_history (module.py), which rescores versions on the fly.
 * When the container is narrow (phone), trail labels become numbered dots with a list below.
 * Styles: styles/risk.css (classes rk-). The file keeps its old name so imports stay stable.
 */
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { ChartFrame, formatDay, formatNumber, toneForStatus } from "../shared";
import type { Risk } from "../../types";
import { versionChange, type DesignHistoryRow } from "./types";
import "../../styles/risk.css";

/** Band cut-offs exactly as in ProtocolCoDesigner.risk (unblind/platform/predose/agents.py). */
const CUT_MEDIUM = 0.35;
const CUT_HIGH = 0.6;
/** A version gets its own label only when it moved u by at least this much. */
const MOVE_MIN = 0.005;
/** Below this container width the trail labels become numbered dots. */
const COMPACT_PX = 440;

const clamp = (x: number) => Math.max(0, Math.min(1, x));
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);
const f2 = (v: number) => v.toFixed(2);
const f3 = (v: number) => v.toFixed(3);
/** Signed with a Unicode minus. */
const signed = (v: number, d = 2) => `${v < 0 ? "−" : v > 0 ? "+" : ""}${Math.abs(v).toFixed(d)}`;

function bandWord(b: string | null | undefined): string {
  if (!b) return "unknown";
  return b.toLowerCase();
}
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** One point on the line. */
interface Point {
  version: number;
  day: number | null;
  change: string;
  u: number;
  sd: number | null;
  g: number | null;
  band: string | null;
  source: string;
}

/** Normalise the history; fall back to the stored baseline and current values when the view has none. */
function buildPoints(history: DesignHistoryRow[] | null | undefined, risk: Risk, baseline: Risk | null | undefined,
  latestVersion: number | null): Point[] {
  const rows = (history ?? []).filter((r) => isNum(r.u));
  if (rows.length) {
    return rows.map((r) => ({
      version: r.version, day: r.day, change: versionChange(r), u: r.u as number,
      sd: isNum(r.u_sd) ? r.u_sd : null, g: isNum(r.expected_bias_g) ? r.expected_bias_g : null,
      band: r.band, source: r.source,
    }));
  }
  const now: Point = {
    version: latestVersion ?? 1, day: null, change: "current", u: risk.u, sd: isNum(risk.u_sd) ? risk.u_sd : null,
    g: isNum(risk.expected_bias_g) ? risk.expected_bias_g : null, band: risk.band, source: "stored",
  };
  if (baseline && isNum(baseline.u) && (latestVersion ?? 1) > 1) {
    return [{ version: 1, day: null, change: "initial draft", u: baseline.u, sd: isNum(baseline.u_sd) ? baseline.u_sd : null,
      g: isNum(baseline.expected_bias_g) ? baseline.expected_bias_g : null, band: baseline.band, source: "stored" }, now];
  }
  return [now];
}

function pointSentence(p: Point): string {
  const day = p.day !== null ? `, day ${formatDay(p.day).replace(/^D/, "")}` : "";
  const sd = p.sd !== null ? ` ± ${f2(p.sd)} (1 SD)` : "";
  const g = p.g !== null ? `, expected bias ${f3(p.g)} g` : "";
  return `Version ${p.version}${day}, ${p.change}: u ${f2(p.u)}${sd}${g}, ${bandWord(p.band)} band`;
}

/** Lanes below the line for trail labels, nearest first. */
const LANES = [0, 1, 2];
const LANE_STEP = 36;

function assignLanes(us: number[], gap: number): number[] {
  const placed: { u: number; lane: number }[] = [];
  return us.map((u) => {
    const lane = LANES.find((l) => placed.every((p) => p.lane !== l || Math.abs(p.u - u) >= gap)) ?? LANES[LANES.length - 1];
    placed.push({ u, lane });
    return lane;
  });
}

function edge(u: number): string {
  if (u < 0.15) return " rk-l--start";
  if (u > 0.85) return " rk-l--end";
  return "";
}

/** Closes an open tooltip on scroll or a tap outside (touch has no hover-out). */
function useDismiss(ref: React.RefObject<HTMLElement>) {
  useEffect(() => {
    const blur = () => {
      const a = document.activeElement as HTMLElement | null;
      if (a && ref.current?.contains(a)) a.blur();
    };
    window.addEventListener("scroll", blur, { passive: true });
    return () => window.removeEventListener("scroll", blur);
  }, [ref]);
}

function useWidth(ref: React.RefObject<HTMLElement>): number {
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    setW(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

function RiskLine({ points, nowLabel, compact }: { points: Point[]; nowLabel: string; compact: boolean }) {
  const now = points[points.length - 1];
  // Trail: earlier versions that moved u, plus the first version. Same-value versions are footnoted.
  const trail = points.slice(0, -1).filter((p, i) => i === 0 || Math.abs(p.u - points[i - 1].u) >= MOVE_MIN);
  const trailShown = trail.filter((p) => Math.abs(p.u - now.u) >= MOVE_MIN);
  const lanes = assignLanes(trailShown.map((p) => p.u), compact ? 0.08 : 0.32);
  const maxLane = Math.max(-1, ...lanes);
  const lo = now.sd !== null ? clamp(now.u - now.sd) : null;
  const hi = now.sd !== null ? clamp(now.u + now.sd) : null;
  const below = trailShown.length ? (maxLane + 1) * LANE_STEP + (compact ? 0 : 16) : 0;
  const style = { "--rk-below": `${below}px` } as CSSProperties;
  const pct = (u: number) => `${clamp(u) * 100}%`;
  const sdLabelLeft = hi !== null && hi > 0.85;

  return (
    <div className="rk-line" style={style}>
      {/* bands: cut-off ticks and words above the line */}
      <div className="rk-bands" aria-hidden="true">
        <span className="rk-band" style={{ left: 0, width: pct(CUT_MEDIUM) }}>Low</span>
        <span className="rk-band" style={{ left: pct(CUT_MEDIUM), width: pct(CUT_HIGH - CUT_MEDIUM) }}>Medium</span>
        <span className="rk-band" style={{ left: pct(CUT_HIGH), width: pct(1 - CUT_HIGH) }}>High</span>
      </div>
      <div className="rk-track">
        <span className="rk-axis" />
        {[0, CUT_MEDIUM, CUT_HIGH, 1].map((c) => (
          <span key={c} className={`rk-cut${c === 0 || c === 1 ? " rk-cut--end" : ""}`} style={{ left: pct(c) }} aria-hidden="true">
            {c !== 0 && c !== 1 ? <span className="rk-cut__num num">{formatNumber(c)}</span> : null}
          </span>
        ))}
        {lo !== null && hi !== null ? (
          <>
            <span className="rk-sd" style={{ left: pct(lo), width: `${(hi - lo) * 100}%` }} aria-hidden="true" />
            <span className={`rk-sd__label${sdLabelLeft ? " rk-sd__label--left" : ""}`}
              style={{ left: sdLabelLeft ? pct(lo) : pct(hi) }} aria-hidden="true">± 1 SD</span>
          </>
        ) : null}
        {trailShown.map((p, i) => {
          const n = points.indexOf(p) + 1;
          return (
            <span key={p.version} className="rk-pt" style={{ left: pct(p.u) }} tabIndex={0}
              aria-label={pointSentence(p)}>
              <span className="rk-pt__dot" />
              {lanes[i] > 0 && !compact ? (
                <span className="rk-pt__stem" style={{ height: `${lanes[i] * LANE_STEP + 2}px` }} />
              ) : null}
              <span className={`rk-l rk-l--trail${edge(p.u)}`} aria-hidden="true"
                style={{ "--rk-off": `${lanes[i] * LANE_STEP}px` } as CSSProperties}>
                {compact ? <span className="rk-l__num num">{n}</span> : (
                  <>
                    <span className="rk-l__text">v{p.version} {p.change}</span>
                    <span className="rk-l__val num">{f2(p.u)}</span>
                  </>
                )}
              </span>
              <span className="rk-tip" role="tooltip">{pointSentence(p)}</span>
            </span>
          );
        })}
        <span className="rk-pt rk-pt--now" style={{ left: pct(now.u) }} tabIndex={0} aria-label={pointSentence(now)}>
          <span className="rk-pt__dot" />
          <span className={`rk-l rk-l--now${edge(now.u)}`} aria-hidden="true">
            <span className="rk-l__text">{nowLabel}</span>
            <span className="rk-l__val num">{f2(now.u)}</span>
          </span>
          <span className="rk-tip" role="tooltip">{pointSentence(now)}</span>
        </span>
      </div>
      <div className="rk-ends" aria-hidden="true">
        <span><span className="num">0</span> no one can tell (guessing at chance)</span>
        <span><span className="num">1</span> everyone can tell</span>
      </div>
    </div>
  );
}

export interface RiskCardProps {
  risk: Risk | null | undefined;
  baseline: Risk | null | undefined;
  /** design_review.risk_at_enrolment: frozen when enrolment completed. Absent before then. */
  atEnrolment?: Risk | null;
  /** The predose view's design_history (per protocol version). Optional: falls back to baseline and now. */
  history?: DesignHistoryRow[] | null;
  /** Latest protocol version number, used when the history is missing. */
  latestVersion?: number | null;
}

export function RiskCard({ risk, baseline, atEnrolment, history, latestVersion = null }: RiskCardProps) {
  const ref = useRef<HTMLDivElement>(null);
  const width = useWidth(ref);
  useDismiss(ref);
  const compact = width > 0 && width < COMPACT_PX;

  const subtitle = "Share of participants who can tell their arm, 0 to 1, by protocol version. Model prediction before dosing.";
  if (!risk || !isNum(risk.u)) {
    return (
      <div ref={ref} className="rk">
        <ChartFrame id="risk-scale" title="Predicted unblinding" subtitle={subtitle} ariaLabel="Predicted unblinding: no risk yet."
          empty={{ title: "Risk appears after the first design review" }}>
          {null}
        </ChartFrame>
      </div>
    );
  }

  const points = buildPoints(history, risk, baseline, latestVersion);
  const now = points[points.length - 1];
  const first = points[0];
  const frozen = atEnrolment && isNum(atEnrolment.u) ? atEnrolment : null;
  const nowLabel = frozen && Math.abs(frozen.u - now.u) < MOVE_MIN ? `At enrolment (v${now.version})` : `Now (v${now.version})`;

  // Which version moved u most (largest single drop, or largest change when nothing dropped).
  let biggest: { p: Point; d: number } | null = null;
  for (let i = 1; i < points.length; i++) {
    const d = points[i].u - points[i - 1].u;
    if (Math.abs(d) >= MOVE_MIN && (!biggest || Math.abs(d) > Math.abs(biggest.d))) biggest = { p: points[i], d };
  }
  const band = bandWord(now.band);
  const title = points.length > 1 && biggest
    ? `Predicted unblinding ${f2(first.u)} to ${f2(now.u)}; ${biggest.p.change} moved it most (${signed(biggest.d)})`
    : points.length > 1
      ? `Predicted unblinding u ${f2(now.u)}, ${band}; no version has changed it yet`
      : `Predicted unblinding u ${f2(now.u)}, ${band}`;

  // Versions that did not move u, and whether they moved expected bias.
  const still = points.slice(1).filter((p, i) => Math.abs(p.u - points[i].u) < MOVE_MIN);
  const stillText = still.length ? (() => {
    const vs = still.map((p) => p.version);
    const range = vs.length === 1 ? `v${vs[0]}` : vs.every((v, i) => i === 0 || v === vs[i - 1] + 1)
      ? `v${vs[0]} to v${vs[vs.length - 1]}` : vs.map((v) => `v${v}`).join(", ");
    const gMoves = still.map((p) => {
      const prev = points[points.indexOf(p) - 1];
      return p.g !== null && prev.g !== null && Math.abs(p.g - prev.g) >= 0.0005
        ? `v${p.version} (${p.change}) moved expected bias ${f3(prev.g)} to ${f3(p.g)} g` : null;
    }).filter(Boolean);
    return `${range} did not change u${gMoves.length ? `; ${gMoves.join("; ")}` : ""}.`;
  })() : null;

  const trailForList = points.filter((p, i) => i === 0 || Math.abs(p.u - points[i - 1].u) >= MOVE_MIN || i === points.length - 1);
  const aria = `Predicted unblinding by protocol version: ${points.map((p) => `v${p.version} ${f2(p.u)}`).join(", ")}; `
    + `now ${f2(now.u)}${now.sd !== null ? ` plus or minus ${f2(now.sd)} (1 SD)` : ""}, ${band} band. `
    + (biggest ? `Largest change: ${biggest.p.change} (${signed(biggest.d)}).` : "No version changed it.");

  const synthetic = /synthetic/i.test(risk.calibration ?? "");
  const anyRescored = points.some((p) => p.source === "rescored");
  const dataTable = {
    columns: [
      { key: "version", label: "Version", align: "right" as const },
      { key: "day", label: "Day" },
      { key: "change", label: "Change" },
      { key: "u", label: "u", align: "right" as const },
      { key: "sd", label: "SD", align: "right" as const },
      { key: "g", label: "Expected bias (g)", align: "right" as const },
      { key: "band", label: "Band" },
      { key: "source", label: "Source", derived: anyRescored },
    ],
    rows: points.map((p) => ({
      version: p.version, day: p.day !== null ? formatDay(p.day) : "", change: p.change, u: f3(p.u),
      sd: p.sd !== null ? f3(p.sd) : "", g: p.g !== null ? f3(p.g) : "", band: bandWord(p.band),
      source: p.source === "rescored" ? "rescored, rule-based parse" : p.source,
    })),
    note: "First and current values are stored in the trial record. Versions in between are rescored when this page "
      + "loads, from each version's stored text, with the rule-based protocol parser and the same risk model; nothing "
      + `is saved. Bands: low below ${CUT_MEDIUM}, medium below ${CUT_HIGH}, high from ${CUT_HIGH} (as in the co-designer). `
      + (risk.calibration || ""),
  };

  return (
    <div ref={ref} className={`rk${compact ? " rk--compact" : ""}`}>
      <ChartFrame
        id="risk-scale"
        title={title}
        subtitle={subtitle}
        ariaLabel={aria}
        dataTable={dataTable}
        dataTitle="Data: predicted unblinding by protocol version"
        footnotes={
          <>
            {compact && trailForList.length > 1 ? (
              <ol className="rk-list">
                {trailForList.map((p) => (
                  <li key={p.version} value={points.indexOf(p) + 1}>
                    <span>v{p.version} {p.change}{p === now ? ` (${nowLabel.split(" (")[0].toLowerCase()})` : ""}</span>
                    <span className="num">{f2(p.u)}</span>
                  </li>
                ))}
              </ol>
            ) : null}
            {stillText ? <p>{stillText}</p> : null}
            <p>
              Model prediction{synthetic ? " from a synthetic calibration" : ""}, not a measured result. The bar is
              {" "}± 1 SD of the prediction, not a confidence interval.
            </p>
          </>
        }
      >
        <div className="rk-value">
          <span className="rk-value__u num">u {f2(now.u)}</span>
          {now.sd !== null ? <span className="rk-value__sd num">± {f2(now.sd)} SD</span> : null}
          <span className={`rk-value__band rk-value__band--${toneForStatus(now.band ?? "")}`}>
            <span className="rk-value__dot" aria-hidden="true" />{cap(band)} band
          </span>
          {now.g !== null ? (
            <span className="rk-value__g num">
              Expected bias {f3(now.g)} g{first !== now && first.g !== null ? `, from ${f3(first.g)} g in v${first.version}` : ""}
            </span>
          ) : null}
        </div>
        <RiskLine points={points} nowLabel={nowLabel} compact={compact} />
        {frozen && Math.abs(frozen.u - now.u) >= MOVE_MIN ? (
          <p className="rk-frozen num">
            At enrolment u was {f2(frozen.u)} ({bandWord(frozen.band)} band); later amendments do not change that value.
          </p>
        ) : null}
      </ChartFrame>
    </div>
  );
}

/** Kept for compatibility with the old export: a single-marker line. */
export function UnblindingSphere({ u }: { u: number; label?: string }) {
  const p: Point = { version: 1, day: null, change: "current", u, sd: null, g: null, band: null, source: "stored" };
  return <RiskLine points={[p]} nowLabel="Now" compact={false} />;
}
