/**
 * Recruitment ads as flat columns (reading ease and check dots), the channels, and the parked
 * behavioural-targeting note. Plus the measurement plan ledger (UNBLIND-BLIND-1 instruments).
 */
import { LedgerTable, StatusPill, formatNumber, humanise } from "../shared";
import type { Instrument, MeasurementPlan, Recruitment } from "../../types";
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
              <article key={ad.id} className="st-block ad">
                <div className="row row--between">
                  <span className="st-label">{ad.id}</span>
                  {passed === total
                    ? <span className="st-status"><span className="st-dot st-dot--good" aria-hidden="true" /><span className="num">{passed} / {total}</span> checks</span>
                    : <StatusPill tone="alert">{passed} / {total} checks</StatusPill>}
                </div>
                <p className="ad__text">{ad.text}</p>
                <div className="ad__ease">
                  <span className="t-readout">{formatNumber(ad.reading_ease)}</span>
                  <span className="t-caption c-smoke">Flesch reading ease ({easeWord(ad.reading_ease)})</span>
                </div>
                <ul className="ad__checks" role="list">
                  {Object.entries(ad.checks).map(([k, v]) => (
                    <li key={k} className="st-status" title={v ? "Pass" : "Fail"}>
                      <span className={`st-dot st-dot--${v ? "good" : "alert"}`} aria-hidden="true" />
                      {v ? "Pass" : "Fail"}: {humanise(k)}
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
      )}
      <div className="grid-pd">
        <section className="st-block stack">
          <div className="st-label">Channels</div>
          {channels.length ? (
            <ul className="ad__channels">{channels.map((c) => <li key={c}>{c}</li>)}</ul>
          ) : <p className="t-body-sm c-smoke">No channels chosen yet.</p>}
          <p className="t-caption c-ash">Every ad needs ethics committee approval before it runs.</p>
        </section>
        {parked ? (
          <section className="st-block stack">
            <div className="row">
              <span className="st-label">Behavioural targeting</span>
              <StatusPill tone="watch">Parked</StatusPill>
            </div>
            <p className="t-body-sm c-graphite">{parked}</p>
          </section>
        ) : null}
      </div>
    </div>
  );
}

/** A day relative to dosing day as words: -1 "before randomisation", 0 "dosing day", 7 "week 1". */
export function formatTimepointDay(d: number): string {
  if (d === -1) return "baseline / before randomisation";
  if (d < 0) return `day ${d}`;
  if (d === 0) return "dosing day";
  if (d === 1) return "dosing +1";
  if (d % 7 === 0) return `week ${d / 7}`;
  return `day ${d}`;
}

/** Prefer the backend's human labels; otherwise format timepoints_days (integers or older label strings). */
function timepointLabels(ins: Instrument): string[] {
  const days = ins.timepoints_days ?? [];
  const labels = Array.isArray(ins.timepoints) ? ins.timepoints : [];
  if (labels.length > 0) return labels.map((l, i) => (l ? String(l) : fallbackLabel(days[i])));
  return days.map(fallbackLabel);
}

function fallbackLabel(t: number | string | undefined): string {
  if (t === undefined || t === null) return "";
  if (typeof t === "number" && Number.isFinite(t)) return formatTimepointDay(Math.round(t));
  const n = typeof t === "string" && /^-?\d+$/.test(t.trim()) ? Number(t.trim()) : NaN;
  return Number.isFinite(n) ? formatTimepointDay(n) : String(t);
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
    <span className="mplan__times num">{timepointLabels(ins).join(", ")}</span>,
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
