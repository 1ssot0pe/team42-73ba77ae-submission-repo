/**
 * Recruitment ads as paper sheets (reading ease and check pills), the channels, and the parked
 * behavioural-targeting note. Plus the measurement plan ledger (UNBLIND-BLIND-1 instruments).
 */
import { LedgerTable, StatusPill, formatNumber, humanise } from "../shared";
import type { MeasurementPlan, Recruitment } from "../../types";
import { parkedText } from "./types";

/** Flesch reading ease bands, so the number has context. */
function easeWord(x: number): string {
  if (x >= 70) return "easy";
  if (x >= 60) return "plain English";
  if (x >= 50) return "fairly hard";
  return "hard";
}

export function RecruitmentAds({ recruitment }: { recruitment: Recruitment | null | undefined }) {
  const ads = recruitment?.ads ?? [];
  const parked = parkedText(recruitment?.parked);
  const channels = (recruitment?.channels ?? []).map(String);
  return (
    <div className="stack stack--loose">
      {ads.length === 0 ? <p className="t-body-sm c-smoke">The ad writer has not drafted any ads yet.</p> : (
        <div className="ads">
          {ads.map((ad) => {
            const passed = Object.values(ad.checks).filter(Boolean).length;
            const total = Object.keys(ad.checks).length;
            return (
              <article key={ad.id} className="paper ad">
                <div className="row row--between">
                  <span className="eyebrow">{ad.id}</span>
                  <StatusPill tone={passed === total ? "good" : "alert"}>{passed} / {total} checks</StatusPill>
                </div>
                <p className="ad__text">{ad.text}</p>
                <div className="ad__ease">
                  <span className="t-readout">{formatNumber(ad.reading_ease)}</span>
                  <span className="t-caption c-smoke">Flesch reading ease ({easeWord(ad.reading_ease)})</span>
                </div>
                <div className="row">
                  {Object.entries(ad.checks).map(([k, v]) => (
                    <StatusPill key={k} tone={v ? "good" : "alert"} title={v ? "Pass" : "Fail"}>
                      {v ? "Pass" : "Fail"} · {humanise(k)}
                    </StatusPill>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      )}
      <div className="grid-pd">
        <section className="sheet stack">
          <div className="eyebrow">Channels</div>
          {channels.length ? (
            <ul className="ad__channels">{channels.map((c) => <li key={c}>{c}</li>)}</ul>
          ) : <p className="t-body-sm c-smoke">No channels chosen yet.</p>}
          <p className="t-caption c-ash">Every ad needs ethics committee approval before it runs.</p>
        </section>
        {parked ? (
          <section className="sheet stack">
            <div className="row">
              <span className="eyebrow">Behavioural targeting</span>
              <StatusPill tone="watch">Parked</StatusPill>
            </div>
            <p className="t-body-sm c-graphite">{parked}</p>
          </section>
        ) : null}
      </div>
    </div>
  );
}

export function MeasurementPlanLedger({ plan }: { plan: MeasurementPlan | null | undefined }) {
  if (!plan || !Array.isArray(plan.instruments) || plan.instruments.length === 0) {
    return (
      <LedgerTable title="Measurement plan" columns={["Instrument", "Who", "Questions", "Timepoints", "Purpose"]} rows={[]}
        empty="The measurement planner builds the UNBLIND-BLIND-1 schedule once a clinician approves the shortlist." />
    );
  }
  const rows = plan.instruments.map((ins) => [
    <span className="num">{ins.id}</span>,
    humanise(ins.who),
    <ul className="mplan__list">{(ins.questions ?? []).map((q, i) => <li key={i}>{q}</li>)}</ul>,
    <span className="mplan__times">{(ins.timepoints_days ?? []).map((t, i) => <StatusPill key={i} tone="neutral">{String(t)}</StatusPill>)}</span>,
    <span className="c-smoke">{ins.purpose}</span>,
  ]);
  return (
    <div className="stack">
      <div className="row mplan__meta">
        <StatusPill tone="ink">{plan.standard}</StatusPill>
        <span className="t-body-sm c-graphite">
          <span className="num">{plan.instruments.length}</span> instruments · primary endpoint at
          week <span className="num">{plan.primary_week}</span>
        </span>
      </div>
      <LedgerTable columns={[{ label: "Instrument", mono: true }, "Who", "Questions", "Timepoints", "Purpose"]} rows={rows} maxHeight={560} />
    </div>
  );
}
