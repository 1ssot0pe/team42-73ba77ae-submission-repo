/**
 * UnblindingSphere (design.md 8.6). A 220px sphere driven by the CSS custom property --u (0 to 1):
 * stone at u = 0, violet blooming from the centre and ember from the lower rim as u rises.
 * RiskCard wraps it with the value, band, meaning, expected bias, calibration and before vs after.
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

export function RiskCard({ risk, baseline }: { risk: Risk | null | undefined; baseline: Risk | null | undefined }) {
  if (!risk) {
    return (
      <section className="sheet risk">
        <div className="eyebrow">Predicted unblinding</div>
        <p className="t-body-sm c-smoke">The protocol co-designer has not scored this protocol yet.</p>
      </section>
    );
  }
  const synthetic = /synthetic/i.test(risk.calibration ?? "");
  const moved = baseline && baseline.u !== risk.u;
  return (
    <section className="sheet risk" aria-labelledby="risk-title">
      <div className="risk__head">
        <div className="stack stack--tight">
          <div className="eyebrow">Predicted unblinding</div>
          <h2 className="t-heading-sm" id="risk-title">Blinding risk</h2>
        </div>
        <SpecimenTag />
      </div>
      <div className="risk__body">
        <UnblindingSphere u={risk.u} label={`Predicted unblinding u ${formatNumber(risk.u)}, ${risk.band} risk`} />
        <div className="risk__facts">
          <div className="risk__value">
            <span className="t-readout-xl">u = {formatNumber(risk.u)}</span>
            <StatusPill tone={toneForStatus(risk.band)} size="lg">{bandWord(risk.band)}</StatusPill>
          </div>
          <p className="t-body-sm c-smoke">0 is a coin flip, 1 means everyone knew which group they were in.</p>
          <UScale u={risk.u} baseline={baseline?.u} />
          <dl className="risk__dl">
            <div>
              <dt>Uncertainty</dt>
              <dd className="num">&plusmn; {formatNumber(risk.u_sd)} u (1 sd)</dd>
            </div>
            <div>
              <dt>Expected bias</dt>
              <dd className="num">{formatNumber(risk.expected_bias_g)} g (Hedges)</dd>
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
            {baseline ? (
              <div>
                <dt>Bias before</dt>
                <dd className="num">{formatNumber(baseline.expected_bias_g)} g &rarr; {formatNumber(risk.expected_bias_g)} g</dd>
              </div>
            ) : null}
          </dl>
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
