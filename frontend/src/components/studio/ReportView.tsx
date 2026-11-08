/**
 * ReportView: the evidence report as a readable document. Effect, blinding, facts (open in a drawer),
 * ranked design fixes, warnings and the agent trace. Renders only what the report contains.
 */
import { useCallback, useMemo, useState } from "react";
import type { EvidenceReport } from "../../types";
import { EffectChart } from "./EffectChart";
import { FactDrawer, StatusDot, statusTone, statusWord } from "./FactDrawer";
import type { FactRow } from "./report";
import * as R from "./report";

function pct(v: string): string {
  const n = Number(v);
  return Number.isFinite(n) && n >= 0 && n <= 1 ? `${Math.round(n * 100)}%` : v;
}

/** Values the statistician derives for its own use; shown only under "Show every value". */
const INTERNAL = new Set(["se_g", "u_sd", "g", "u"]);

export function ReportView({ report, input, onUseFixes }: {
  report: EvidenceReport;
  input: string;
  onUseFixes: () => void;
}) {
  const [open, setOpen] = useState<FactRow | null>(null);
  const [showAll, setShowAll] = useState(false);
  const close = useCallback(() => setOpen(null), []);

  const nct = R.str(report.nct);
  const name = R.title(report, input);
  const drugs = R.strings(report.drug);
  const eff = R.effect(report);
  const bl = R.blinding(report);
  const fixes = R.fixes(report);
  const warnings = R.strings(report.warnings);
  const limitations = R.strings(report.limitations);
  const trace = R.trace(report);
  const synthetic = R.isSynthetic(report);
  const calibration = R.str(report.calibration);
  const allFacts = useMemo(() => R.facts(report), [report]);
  const keyFacts = allFacts.filter((f) => f.quote && !INTERNAL.has(f.key));
  const shownFacts = showAll ? allFacts : keyFacts.length ? keyFacts : allFacts.slice(0, 6);
  const guessP = allFacts.find((f) => f.key === "guess_acc_participants");
  const guessR = allFacts.find((f) => f.key === "guess_acc_raters");

  return (
    <article className="studio-report" aria-label="Evidence report">
      <header className="studio-report__head">
        <h2 className="studio-report__title">{name}</h2>
        <p className="studio-small studio-muted">
          {nct && nct !== name ? <span className="t-id">{nct}</span> : null}
          {nct && nct !== name && drugs.length ? " · " : null}
          {drugs.length ? drugs.join(", ") : null}
          {report.in_domain === false ? " · outside the psychedelic trials the model was fitted on" : null}
        </p>
      </header>

      {eff ? (
        <section className="studio-section" aria-labelledby="st-effect">
          <h3 id="st-effect" className="studio-h3">Effect</h3>
          <dl className="studio-readout">
            <div>
              <dt>Reported</dt>
              <dd>{R.fmt(eff.reported)}</dd>
              {eff.reportedLo !== null && eff.reportedHi !== null ? (
                <dd className="studio-readout__range">{R.fmt(eff.reportedLo)} to {R.fmt(eff.reportedHi)}</dd>
              ) : null}
            </div>
            <div>
              <dt>Bias-adjusted</dt>
              <dd>{R.fmt(eff.adjusted)}</dd>
              {eff.adjustedLo !== null && eff.adjustedHi !== null ? (
                <dd className="studio-readout__range">{R.fmt(eff.adjustedLo)} to {R.fmt(eff.adjustedHi)}</dd>
              ) : null}
            </div>
            {eff.bias !== null ? (
              <div>
                <dt>Estimated bias</dt>
                <dd>{R.fmt(eff.bias)}</dd>
              </div>
            ) : null}
          </dl>
          <p className="studio-small studio-muted">
            Standardised effect (Hedges&rsquo; g), 95% range. Positive favours the drug.
            {eff.reportedStatus === "imputed" ? " The reported g was converted using estimated arm sizes." : null}
            {eff.extrapolated ? " This trial sits outside the range of the calibration data, so the adjustment is extrapolated." : null}
          </p>
          {eff.reported !== null || eff.adjusted !== null ? (
            <EffectChart e={eff} note={synthetic ? "Synthetic calibration" : calibration ? `Calibration: ${R.tidy(calibration)}` : ""} />
          ) : null}
        </section>
      ) : null}

      {bl ? (
        <section className="studio-section" aria-labelledby="st-blinding">
          <h3 id="st-blinding" className="studio-h3">How blinded it was</h3>
          <dl className="studio-pairs">
            <div>
              <dt>Overall</dt>
              <dd><StatusDot tone={bl.tone}>{bl.word}</StatusDot></dd>
            </div>
            <div>
              <dt>Unblinding, 0 to 1</dt>
              <dd className="studio-num">{R.fmt(bl.u)}{bl.uSd !== null ? <span className="studio-muted"> ± {R.fmt(bl.uSd)}</span> : null}</dd>
            </div>
            {guessP ? (
              <div>
                <dt>Participant guess accuracy</dt>
                <dd className="studio-num">{guessP.status !== "unknown" ? pct(guessP.value) : <span className="studio-muted">Not reported</span>}</dd>
              </div>
            ) : null}
            {guessR ? (
              <div>
                <dt>Rater guess accuracy</dt>
                <dd className="studio-num">{guessR.status !== "unknown" ? pct(guessR.value) : <span className="studio-muted">Not reported</span>}</dd>
              </div>
            ) : null}
          </dl>
          <p className="studio-small studio-muted studio-note">
            {bl.observed
              ? "Observed: worked out from the trial's own blinding data (how often people guessed their arm)."
              : "Estimated: the trial did not report blinding data, so this comes from its design."}
          </p>
          <p className="studio-small studio-muted">0 means nobody could tell which arm they were in; 1 means everyone could.</p>
        </section>
      ) : null}

      {allFacts.length ? (
        <section className="studio-section" aria-labelledby="st-facts">
          <h3 id="st-facts" className="studio-h3">What the sources say</h3>
          <ul className="studio-facts">
            {shownFacts.map((f) => (
              <li key={f.key}>
                <button type="button" className="studio-fact" onClick={() => setOpen(f)}>
                  <span className="studio-fact__label">{f.label}</span>
                  <span className="studio-fact__value">{f.value}</span>
                  <StatusDot tone={statusTone(f.status)}>{statusWord(f.status)}</StatusDot>
                </button>
              </li>
            ))}
          </ul>
          {allFacts.length > shownFacts.length || showAll ? (
            <button type="button" className="studio-text-btn" onClick={() => setShowAll((s) => !s)}>
              {showAll ? "Show quoted facts only" : `Show every value (${allFacts.length})`}
            </button>
          ) : null}
        </section>
      ) : null}

      {fixes.length ? (
        <section className="studio-section" aria-labelledby="st-fixes">
          <h3 id="st-fixes" className="studio-h3">Design fixes, best first</h3>
          <ol className="studio-fixes">
            {fixes.map((f, i) => (
              <li key={`${f.change}-${i}`}>
                <span>{f.change}</span>
                {f.reduction !== null ? (
                  <span className="studio-small studio-muted studio-num">
                    {f.reduction > 0 ? ` cuts expected bias by ${R.fmt(f.reduction, 3)}` : " no predicted reduction"}
                  </span>
                ) : null}
              </li>
            ))}
          </ol>
          <button type="button" className="studio-action" onClick={onUseFixes}>
            Use these fixes in a new trial <span aria-hidden="true">&rarr;</span>
          </button>
        </section>
      ) : null}

      {warnings.length ? (
        <section className="studio-section" aria-labelledby="st-warn">
          <h3 id="st-warn" className="studio-h3">Read with care</h3>
          <ul className="studio-notes">{warnings.map((w, i) => <li key={i}>{R.tidy(w)}</li>)}</ul>
        </section>
      ) : null}

      {trace.length || limitations.length ? (
        <section className="studio-section">
          {trace.length ? (
            <details className="studio-details">
              <summary>How this was worked out</summary>
              <ol className="studio-trace">
                {trace.map((t, i) => (
                  <li key={i} className={`studio-trace__row studio-trace__row--${t.level}`}>
                    <span className="studio-trace__agent">{t.agent}</span>
                    <span>
                      {R.tidy(t.action)}
                      {t.detail ? <span className="studio-muted">: {R.tidy(t.detail)}</span> : null}
                    </span>
                  </li>
                ))}
              </ol>
            </details>
          ) : null}
          {limitations.length ? (
            <details className="studio-details">
              <summary>Limitations</summary>
              <ul className="studio-notes">{limitations.map((l, i) => <li key={i}>{R.tidy(l)}</li>)}</ul>
            </details>
          ) : null}
        </section>
      ) : null}

      <FactDrawer fact={open} onClose={close} />
    </article>
  );
}
