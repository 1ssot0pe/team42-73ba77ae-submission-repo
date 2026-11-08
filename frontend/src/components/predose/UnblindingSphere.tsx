/**
 * UnblindingSphere (design.md 8.6). A 220px sphere driven by the CSS custom property --u (0 to 1):
 * stone at u = 0, violet blooming from the centre and ember from the lower rim as u rises.
 * RiskCard wraps it with the value, band, meaning, a one-line reason under the sphere, calibration,
 * before vs after for u, and expected bias (Hedges g) before and now as two small readouts.
 * When design_review.risk_at_enrolment exists (frozen when enrolment completed), a neutral chip beside the
 * readout shows "At enrolment: u 0.62"; its tooltip adds the frozen bias and band, so later amendments
 * can be compared with what the enrolled participants signed up to.
 */
import type { CSSProperties } from "react";
import { SpecimenTag, StatusPill, formatNumber, toneForStatus } from "../shared";
import type { Risk } from "../../types";

const clamp = (x: number) => Math.max(0, Math.min(1, x));

export function UnblindingSphere({ u, label }: { u: number; label?: string }) {
  const style = { "--u": clamp(u) } as CSSProperties;
  return <div className="sphere" style={style} role="img" aria-label={label ?? `Predicted unblinding u ${formatNumber(u)}`} />;
}

function bandWord(b: string | undefined): string {
  if (!b) return "Unknown";
  return b.charAt(0).toUpperCase() + b.slice(1);
}

/** 0 to 1 scale with the current needle and a dashed marker for the baseline. */
function UScale({ u, baseline }: { u: number; baseline?: number | null }) {
  return (
    <div className="uscale">
      <div className="uscale__track">
        {baseline !== undefined && baseline !== null && baseline !== u ? (
          <span className="uscale__mark uscale__mark--before" style={{ left: `${clamp(baseline) * 100}%` }}
            title={`before ${formatNumber(baseline)} u`} />
        ) : null}
        <span className="uscale__mark" style={{ left: `${clamp(u) * 100}%` }} title={`now ${formatNumber(u)} u`} />
      </div>
      <div className="uscale__ends">
        <span><span className="num">0</span> coin flip</span>
        <span><span className="num">1</span> everyone knows</span>
      </div>
    </div>
  );
}

const isNum = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** Expected bias (Hedges g) before the approved fixes and now, as two small readouts. Lower is better. */
function BiasReadouts({ before, now }: { before: number | null | undefined; now: number | null | undefined }) {
  if (!isNum(now)) return null;
  const hasBefore = isNum(before);
  let arrow: { glyph: string; tone: "good" | "alert" | "neutral"; text: string } | null = null;
  if (hasBefore) {
    if (now === before) arrow = { glyph: "=", tone: "neutral", text: "no change" };
    else if (now < before) arrow = { glyph: "↓", tone: "good", text: "moved the right way" };
    else arrow = { glyph: "↑", tone: "alert", text: "moved the wrong way" };
  }
  return (
    <div className="risk__bias" role="group" aria-labelledby="risk-bias-label">
      <div className="risk__bias-head">
        <span className="readout__label" id="risk-bias-label">Expected bias (Hedges g)</span>
        {arrow ? (
          <span className={`readout__arrow readout__arrow--${arrow.tone} num`}>
            <span aria-hidden="true">{arrow.glyph}</span>{arrow.glyph !== "=" ? ` ${formatNumber(Math.abs(now - (before as number)))} g` : ""}
            <span className="visually-hidden"> {arrow.text}</span>
          </span>
        ) : null}
      </div>
      <div className="risk__bias-pair">
        {hasBefore ? (
          <div className="risk__bias-tile">
            <span className="risk__bias-label">before</span>
            <span className="risk__bias-value"><span className="risk__bias-num">{formatNumber(before)}</span><span className="readout__unit risk__bias-unit">g</span></span>
          </div>
        ) : null}
        <div className="risk__bias-tile">
          <span className="risk__bias-label">now</span>
          <span className="risk__bias-value"><span className="risk__bias-num">{formatNumber(now)}</span><span className="readout__unit risk__bias-unit">g</span></span>
        </div>
      </div>
    </div>
  );
}

/** Tooltip for the at-enrolment chip: u, bias and band, frozen when enrolment completed. */
function frozenTitle(r: Risk): string {
  const parts = [`u ${formatNumber(r.u)}`];
  if (isNum(r.expected_bias_g)) parts.push(`expected bias ${formatNumber(r.expected_bias_g)} g`);
  if (r.band) parts.push(`${bandWord(r.band).toLowerCase()} risk`);
  return `At enrolment: ${parts.join(", ")}. Frozen when enrolment completed; later amendments do not change it.`;
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
      <section className="st-block risk">
        <div className="st-label">Predicted unblinding</div>
        <p className="t-body-sm c-smoke">The protocol co-designer has not scored this protocol yet.</p>
      </section>
    );
  }
  const synthetic = /synthetic/i.test(risk.calibration ?? "");
  const moved = baseline && baseline.u !== risk.u;
  const frozen = atEnrolment && isNum(atEnrolment.u) ? atEnrolment : null;
  return (
    <section className="st-block risk" aria-labelledby="risk-title">
      <div className="risk__head">
        <div className="stack stack--tight">
          <div className="st-label">Predicted unblinding</div>
          <h2 className="st-subtitle" id="risk-title">Blinding risk</h2>
        </div>
        <SpecimenTag />
      </div>
      <div className="risk__body">
        <div className="risk__sphere">
          <UnblindingSphere u={risk.u} label={`Predicted unblinding u ${formatNumber(risk.u)}, ${risk.band} risk`} />
          <p className="risk__why">Predicted unblinding changes with the comparator and prior use. Rater fixes lower expected bias.</p>
        </div>
        <div className="risk__facts">
          <div className="risk__value">
            <span className="t-readout-xl">u = {formatNumber(risk.u)}</span>
            <StatusPill tone={toneForStatus(risk.band)} size="lg">{bandWord(risk.band)}</StatusPill>
            {frozen ? (
              <span className="risk__frozen num" title={frozenTitle(frozen)}>
                At enrolment: u {formatNumber(frozen.u)}
              </span>
            ) : null}
          </div>
          <p className="t-body-sm c-smoke">0 is a coin flip, 1 means everyone knew which group they were in.</p>
          <UScale u={risk.u} baseline={baseline?.u} />
          <dl className="risk__dl">
            <div>
              <dt>Uncertainty</dt>
              <dd className="num">&plusmn; {formatNumber(risk.u_sd)} u (1 sd)</dd>
            </div>
            {baseline ? (
              <div>
                <dt>Before fixes</dt>
                <dd className="num">
                  before {formatNumber(baseline.u)} u &rarr; now {formatNumber(risk.u)} u
                  {moved ? (
                    <span className={`risk__delta risk__delta--${risk.u < baseline.u ? "good" : "alert"}`}>
                      {risk.u < baseline.u ? "↓" : "↑"} {formatNumber(Math.abs(risk.u - baseline.u))} u
                    </span>
                  ) : <span className="risk__delta risk__delta--neutral">=</span>}
                </dd>
              </div>
            ) : null}
          </dl>
          <BiasReadouts before={baseline?.expected_bias_g} now={risk.expected_bias_g} />
          <p className="t-caption c-ash">
            {synthetic ? "Predicted from a SYNTHETIC calibration. " : ""}
            {risk.calibration || "Calibration not stated."}
            {risk.design_model ? <> Design model: {risk.design_model}.</> : null}
          </p>
        </div>
      </div>
    </section>
  );
}
