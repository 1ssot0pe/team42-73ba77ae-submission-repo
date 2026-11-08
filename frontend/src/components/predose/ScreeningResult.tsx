/**
 * The pre-screening agent's answer for one portal applicant, on strong glass (design.md Section 9 Volunteer portal):
 * decision pill, reasons, quoted disclosure and "Final eligibility is always confirmed by a clinician."
 */
import { DecisionPill, EvidenceQuote, formatDay } from "../shared";
import type { Applicant } from "../../types";

export function ScreeningResult({ applicant, busy, error }: { applicant: Applicant | null; busy: boolean; error?: string | null }) {
  const s = applicant?.screening;
  return (
    <section className="portal__result glass glass--strong glass--enter" aria-live="polite" aria-labelledby="result-title">
      <div className="eyebrow">Pre-screening agent</div>
      <h2 className="t-heading-sm" id="result-title">Result</h2>
      {error ? (
        <div className="stack stack--tight">
          <div className="eyebrow">Not screened</div>
          <p className="portal__field-error" role="alert">{error}</p>
          <p className="t-body-sm c-smoke">Correct the form and press Apply again. No decision was made.</p>
        </div>
      ) : !applicant || !s ? (
        <p className="t-body-sm c-smoke">
          {busy ? "Agents working…" : "Fill in the form and press Apply. The pre-screening agent checks it against the protocol's criteria and explains its decision here."}
        </p>
      ) : (
        <div className="stack">
          <div className="row">
            <DecisionPill decision={s.decision} size="lg" />
            <span className="t-caption c-ash num">{applicant.id} · {formatDay(applicant.applied_day)}</span>
          </div>
          {s.reasons.length ? (
            <div className="stack stack--tight">
              <div className="eyebrow">Reasons</div>
              <ul className="portal__reasons">{s.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          ) : (
            <p className="t-body-sm c-graphite">Every criterion the agent checks is met.</p>
          )}
          {s.evidence?.length ? (
            <div className="stack stack--tight">
              <div className="eyebrow">Quoted disclosure</div>
              {s.evidence.map((e, i) => <EvidenceQuote key={i} quote={e.quote} source="your free text" />)}
            </div>
          ) : null}
        </div>
      )}
      <p className="portal__clinician">Final eligibility is always confirmed by a clinician.</p>
    </section>
  );
}
