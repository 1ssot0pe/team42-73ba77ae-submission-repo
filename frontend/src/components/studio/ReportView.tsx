/**
 * ReportView: the evidence report as a readable document. Effect, blinding, facts (open in a drawer),
 * ranked design fixes, warnings and the agent trace. Renders only what the report contains.
 */
import { useCallback, useMemo, useState } from "react";
import type { EvidenceReport } from "../../types";
import { BlindingMeter, blindingAria, blindingSubtitle, blindingTable, blindingTitle } from "./BlindingMeter";
import { EffectChart, effectAria, effectFlags, effectTable, effectTitle } from "./EffectChart";
import { FixesChart, fixesAria, fixesSubtitle, fixesTable, fixesTitle } from "./FixesChart";
import { ChartFrame } from "./Frame";
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
  const sign = R.signOff(report);
  const flags = eff ? effectFlags(eff, sign?.label ?? "") : null;
  const fit = R.fitPrimary(report);
  const accP = R.guessAccuracy(report, "participants");
  const accR = R.guessAccuracy(report, "raters");
  const allFacts = useMemo(() => R.facts(report), [report]);
  const keyFacts = allFacts.filter((f) => f.quote && !INTERNAL.has(f.key));
  const shownFacts = showAll ? allFacts : keyFacts.length ? keyFacts : allFacts.slice(0, 6);

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
          <dl className="studio-readout st-tiles">
            <div className="st-tile">
              <dt>Reported</dt>
              <dd className="st-tile__value">{eff.reported !== null ? <>{R.fmt(eff.reported)} <span className="st-unit">g</span></> : <span className="studio-muted">Not reported</span>}</dd>
              {eff.reportedLo !== null && eff.reportedHi !== null ? (
                <dd className="studio-readout__range">95% CI {R.fmt(eff.reportedLo)} to {R.fmt(eff.reportedHi)}</dd>
              ) : null}
              {flags && flags.reportedImputed ? (
                <dd className="st-tile__note"><StatusDot tone="watch">Imputed</StatusDot> <span className="studio-muted">from estimated arm sizes</span></dd>
              ) : null}
            </div>
            <div className="st-tile">
              <dt>Bias-adjusted</dt>
              <dd className="st-tile__value">{eff.adjusted !== null ? <>{R.fmt(eff.adjusted)} <span className="st-unit">g</span></> : <span className="studio-muted">Not reported</span>}</dd>
              {eff.adjustedLo !== null && eff.adjustedHi !== null ? (
                <dd className="studio-readout__range">95% CI {R.fmt(eff.adjustedLo)} to {R.fmt(eff.adjustedHi)}</dd>
              ) : null}
              {sign ? <dd className="st-tile__note"><StatusDot tone="watch">{sign.label}</StatusDot></dd> : null}
              {synthetic ? <dd className="st-tile__note studio-muted">Synthetic calibration</dd> : null}
            </div>
            <div className="st-tile">
              <dt>Estimated bias</dt>
              <dd className="st-tile__value">{eff.bias !== null ? <>{R.fmt(eff.bias)} <span className="st-unit">g</span></> : <span className="studio-muted">Not reported</span>}</dd>
              {eff.bias !== null && eff.bias !== 0 ? (
                <dd className="studio-readout__range">{eff.bias > 0 ? "Inflates the reported effect towards the drug" : "Pulls the reported effect towards control"}</dd>
              ) : null}
            </div>
          </dl>
          <p className="studio-small studio-muted">
            Hedges&rsquo; g, standardised mean difference. Positive favours the drug.
            {eff.extrapolated ? " This trial sits outside the range of the calibration data, so the adjustment is extrapolated." : null}
          </p>
          {flags && (eff.reported !== null || eff.adjusted !== null) ? (
            <ChartFrame
              id="effect-forest"
              title={effectTitle(eff)}
              subtitle="Adjusted estimate is conservative, under stated assumptions"
              synthetic={synthetic}
              status={sign ? { label: sign.label, tone: "watch" } : undefined}
              ariaLabel={effectAria(eff, flags)}
              dataTable={effectTable(eff, flags)}
              footnotes={
                <ul className="st-notes">
                  <li>
                    The adjustment uses a linear meta-regression of g on unblinding u across {fit.k ?? "the"} calibration trials
                    {synthetic ? ", a synthetic calibration set, not real-world performance" : ""}.
                  </li>
                  {flags.uImputed ? <li>This trial&rsquo;s u{bl ? ` (${R.fmt(bl.u)})` : ""} is imputed from its design, not observed.</li> : null}
                  <li>The adjusted value extrapolates to u = 0 with central blinded raters, where few trials sit and the intercept is least certain.</li>
                  {fit.tau2 === 0 ? <li>Between-trial heterogeneity (tau²) was estimated at 0, so it adds no width to the interval.</li> : null}
                  <li>Reverse causation: people who improve may guess &ldquo;drug&rdquo;, so the adjusted value is best read as a conservative bound.</li>
                  {flags.reportedImputed ? <li>The reported interval is g ± 1.96 × SE; the SE rests on imputed arm sizes.</li> : null}
                </ul>
              }
            >
              <EffectChart e={eff} flags={flags} />
            </ChartFrame>
          ) : null}
        </section>
      ) : null}

      {bl ? (
        <section className="studio-section" aria-labelledby="st-blinding">
          <h3 id="st-blinding" className="studio-h3">How blinded it was</h3>
          <ChartFrame
            id="blinding-meter"
            title={blindingTitle(bl)}
            subtitle={blindingSubtitle(bl)}
            synthetic={false}
            ariaLabel={blindingAria(bl)}
            dataTable={blindingTable(bl, accP, accR)}
            empty={bl.u === null ? { title: "Blinding not assessed in the source" } : null}
            footnotes={
              bl.observed
                ? "Observed: worked out from the trial's own blinding data (how often people guessed their arm)."
                : "Estimated: the trial did not report blinding data, so u comes from its design. Hollow marker means imputed."
            }
          >
            <BlindingMeter b={bl} />
          </ChartFrame>
          <dl className="studio-pairs st-guess">
            <div>
              <dt>Participant guess accuracy</dt>
              <dd className="studio-num">{accP !== null ? pct(String(accP)) : <span className="studio-muted">Not reported</span>}</dd>
            </div>
            <div>
              <dt>Rater guess accuracy</dt>
              <dd className="studio-num">{accR !== null ? pct(String(accR)) : <span className="studio-muted">Not reported</span>}</dd>
            </div>
          </dl>
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

      <section className="studio-section" aria-labelledby="st-fixes">
        <h3 id="st-fixes" className="studio-h3">Design fixes</h3>
        <ChartFrame
          id="design-fixes"
          title={fixes.length ? fixesTitle(fixes) : "No design changes proposed"}
          subtitle={fixes.length ? fixesSubtitle(fixes) : undefined}
          synthetic={synthetic}
          ariaLabel={fixes.length ? fixesAria(fixes) : "No design changes proposed"}
          dataTable={fixes.length ? fixesTable(fixes) : undefined}
          empty={fixes.length ? null : { title: "No design changes proposed" }}
          footnotes={fixes.length ? "Expected bias is the model's prediction for a new trial with this change, using the same calibration." : undefined}
        >
          <FixesChart fx={fixes} />
        </ChartFrame>
        {fixes.length ? (
          <button type="button" className="studio-action" onClick={onUseFixes}>
            Use these fixes in a new trial <span aria-hidden="true">&rarr;</span>
          </button>
        ) : null}
      </section>

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
