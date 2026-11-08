/**
 * Predicted unblinding on Design review: a quiet 0 to 1 scale, not a chart.
 * A 1px line from "coin flip" (0) to "everyone knows" (1), a solid ink marker at the current u, and hollow
 * graphite markers for comparison values (before fixes, and the value frozen at enrolment when it exists).
 * Marker labels sit in lanes above and below the line so they never overlap. The value reads "u = 0.79"
 * in tabular figures with the band word and a small status dot. Supporting facts are a flat list.
 * Styles live in styles/risk.css (classes prefixed rk-). The file keeps its old name so imports stay
 * stable; UnblindingSphere is kept as a single-marker alias.
 */
import type { CSSProperties } from "react";
import { SpecimenTag, formatNumber, toneForStatus } from "../shared";
import type { Risk } from "../../types";
import "../../styles/risk.css";

const clamp = (x: number) => Math.max(0, Math.min(1, x));
const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

function bandWord(b: string | undefined): string {
  if (!b) return "Unknown";
  return b.charAt(0).toUpperCase() + b.slice(1);
}

interface Marker {
  key: string;
  u: number;
  label: string;
  current: boolean;
}

/** Lanes, nearest the line first. Negative lanes sit above the line, positive below. */
const LANES = [-1, 1, -2, 2];
/** Minimum distance on the 0 to 1 scale between two labels sharing a lane. */
const LANE_GAP = 0.3;
const LANE_STEP = 40;

function assignLanes(markers: Marker[]): Map<string, number> {
  const out = new Map<string, number>();
  const placed: { u: number; lane: number }[] = [];
  const ordered = [...markers].sort((a, b) => Number(b.current) - Number(a.current));
  for (const m of ordered) {
    const lane = LANES.find((l) => placed.every((p) => p.lane !== l || Math.abs(p.u - m.u) >= LANE_GAP)) ?? LANES[LANES.length - 1];
    placed.push({ u: m.u, lane });
    out.set(m.key, lane);
  }
  return out;
}

function edgeClass(u: number): string {
  if (u < 0.12) return " rk-scale__label--start";
  if (u > 0.88) return " rk-scale__label--end";
  return "";
}

/** The scale itself. With a single marker no marker label is drawn; the large value above already says it. */
function UnblindingScale({ markers, ariaLabel }: { markers: Marker[]; ariaLabel: string }) {
  const labelled = markers.length > 1;
  const lanes = labelled ? assignLanes(markers) : new Map<string, number>();
  const used = [...lanes.values()];
  const above = Math.max(0, ...used.map((l) => (l < 0 ? -l : 0)));
  const below = Math.max(0, ...used.map((l) => (l > 0 ? l : 0)));
  const style = {
    "--rk-above": labelled ? `${above * LANE_STEP + 12}px` : "0px",
    "--rk-below": labelled ? `${below * LANE_STEP + 12}px` : "0px",
  } as CSSProperties;
  // Hollow markers first so the solid current one sits on top when values coincide.
  const drawOrder = [...markers].sort((a, b) => Number(a.current) - Number(b.current));
  return (
    <div className="rk-scale" role="img" aria-label={ariaLabel}>
      <div className="rk-scale__field" style={style}>
        <span className="rk-scale__line" />
        <span className="rk-scale__tick rk-scale__tick--start" />
        <span className="rk-scale__tick rk-scale__tick--end" />
        {drawOrder.map((m) => {
          const lane = lanes.get(m.key);
          const left = `${clamp(m.u) * 100}%`;
          const dir = lane !== undefined && lane < 0 ? "up" : "down";
          return (
            <span key={m.key}>
              {lane !== undefined && Math.abs(lane) > 1 ? (
                <span className={`rk-scale__stem rk-scale__stem--${dir}`}
                  style={{ left, "--rk-stem": `${(Math.abs(lane) - 1) * LANE_STEP + 4}px` } as CSSProperties} />
              ) : null}
              <span className={`rk-scale__marker${m.current ? " rk-scale__marker--current" : ""}`} style={{ left }} />
              {lane !== undefined ? (
                <span
                  className={`rk-scale__label rk-scale__label--${dir}${edgeClass(m.u)}${m.current ? " rk-scale__label--current" : ""}`}
                  style={{ left, "--rk-offset": `${(Math.abs(lane) - 1) * LANE_STEP + 12}px` } as CSSProperties}
                >
                  <span className="rk-scale__label-text">{m.label}</span>
                  <span className="rk-scale__label-num num">{formatNumber(m.u)}</span>
                </span>
              ) : null}
            </span>
          );
        })}
      </div>
      <div className="rk-scale__ends" aria-hidden="true">
        <span><span className="num">0</span> coin flip</span>
        <span><span className="num">1</span> everyone knows</span>
      </div>
    </div>
  );
}

/** Kept for compatibility with the old export: a single-marker scale. */
export function UnblindingSphere({ u, label }: { u: number; label?: string }) {
  return (
    <UnblindingScale
      markers={[{ key: "now", u, label: "Now", current: true }]}
      ariaLabel={label ?? `Predicted unblinding u ${formatNumber(u)}. Scale from 0, a coin flip, to 1, everyone knows.`}
    />
  );
}

function Delta({ before, now, unit }: { before: number; now: number; unit: string }) {
  if (formatNumber(now) === formatNumber(before)) return <span className="rk-delta rk-delta--neutral">no change</span>;
  const better = now < before;
  return (
    <span className={`rk-delta rk-delta--${better ? "good" : "alert"} num`}>
      <span aria-hidden="true">{better ? "↓" : "↑"}</span> {formatNumber(Math.abs(now - before))} {unit}
      <span className="visually-hidden"> {better ? "moved the right way" : "moved the wrong way"}</span>
    </span>
  );
}

export interface RiskCardProps {
  risk: Risk | null | undefined;
  baseline: Risk | null | undefined;
  /** design_review.risk_at_enrolment: frozen when enrolment completed. Absent before then and on older backends. */
  atEnrolment?: Risk | null;
}

export function RiskCard({ risk, baseline, atEnrolment }: RiskCardProps) {
  if (!risk) {
    return (
      <section className="st-block rk">
        <div className="st-label">Predicted unblinding</div>
        <p className="t-body-sm c-smoke">The protocol co-designer has not scored this protocol yet.</p>
      </section>
    );
  }
  const synthetic = /synthetic/i.test(risk.calibration ?? "");
  const frozen = atEnrolment && isNum(atEnrolment.u) ? atEnrolment : null;
  const base = baseline && isNum(baseline.u) ? baseline : null;
  // Compare as displayed, so a difference that rounds away does not draw a second marker.
  const moved = base !== null && formatNumber(base.u) !== formatNumber(risk.u);
  const tone = toneForStatus(risk.band);
  const band = bandWord(risk.band);

  const markers: Marker[] = [];
  if (moved && base) markers.push({ key: "base", u: base.u, label: "Before fixes", current: false });
  if (frozen) markers.push({ key: "enrol", u: frozen.u, label: "At enrolment", current: false });
  markers.push({ key: "now", u: risk.u, label: frozen ? "Now" : "Before enrolment", current: true });

  const ariaParts = [`Predicted unblinding u ${formatNumber(risk.u)}, ${band.toLowerCase()} risk`];
  if (moved && base) ariaParts.push(`before fixes ${formatNumber(base.u)}`);
  if (frozen) ariaParts.push(`at enrolment ${formatNumber(frozen.u)}`);
  const ariaLabel = `${ariaParts.join("; ")}. Scale from 0, a coin flip, to 1, everyone knows.`;

  const biasNow = risk.expected_bias_g;
  const biasBefore = base?.expected_bias_g;

  return (
    <section className="st-block rk" aria-labelledby="risk-title">
      <div className="rk__head">
        <div className="stack stack--tight">
          <div className="st-label">Predicted unblinding</div>
          <h2 className="st-subtitle" id="risk-title">Blinding risk</h2>
        </div>
        <SpecimenTag />
      </div>

      <div className="rk__value">
        <span className="rk__u num">u = {formatNumber(risk.u)}</span>
        <span className={`rk__band rk__band--${tone}`}>
          <span className="rk__dot" aria-hidden="true" />
          {band}<span className="visually-hidden"> risk</span>
        </span>
      </div>

      <UnblindingScale markers={markers} ariaLabel={ariaLabel} />

      <p className="rk__why">Predicted unblinding changes with the comparator and prior use. Rater fixes lower expected bias.</p>

      <dl className="rk__facts">
        <div>
          <dt>Uncertainty</dt>
          <dd className="num">&plusmn; {formatNumber(risk.u_sd)} u (1 sd)</dd>
        </div>
        {base ? (
          <div>
            <dt>Before fixes</dt>
            <dd className="num">
              <span>{formatNumber(base.u)} u, now {formatNumber(risk.u)} u</span>
              <Delta before={base.u} now={risk.u} unit="u" />
            </dd>
          </div>
        ) : null}
        {isNum(biasNow) ? (
          <div>
            <dt>Expected bias (Hedges g)</dt>
            <dd className="num">
              <span>{isNum(biasBefore) ? <>{formatNumber(biasBefore)} g before fixes, now </> : null}{formatNumber(biasNow)} g</span>
              {isNum(biasBefore) ? <Delta before={biasBefore} now={biasNow} unit="g" /> : null}
            </dd>
          </div>
        ) : null}
        {frozen ? (
          <div>
            <dt>At enrolment</dt>
            <dd className="num">
              <span>
                u {formatNumber(frozen.u)}
                {isNum(frozen.expected_bias_g) ? <>, expected bias {formatNumber(frozen.expected_bias_g)} g</> : null}
                {frozen.band ? <>, {bandWord(frozen.band).toLowerCase()} risk</> : null}.
                {" "}Frozen when enrolment completed; later amendments do not change it.
              </span>
            </dd>
          </div>
        ) : null}
      </dl>

      <p className="rk__note">
        {synthetic ? "Predicted from a synthetic calibration. " : ""}
        {risk.calibration || "Calibration not stated."}
        {risk.design_model ? <> Design model: {risk.design_model}.</> : null}
      </p>
    </section>
  );
}
