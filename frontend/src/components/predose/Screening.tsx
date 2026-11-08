/**
 * ScreeningFunnel (design.md 8.14), the flagged-applicant ledger and the fairness table.
 * Funnel: Applied → Eligible (auto) → Excluded (auto) → Needs clinician → Enrolled, bar length proportional
 * to the count, stone fill with an ink leading edge; Needs clinician watch, Excluded alert, Enrolled ink.
 */
import { EvidenceQuote, LedgerTable, StatusPill, formatNumber } from "../shared";
import type { Applicant, FairnessGroup, Funnel } from "../../types";

const STAGES: Array<{ key: keyof Funnel; label: string; tone: string }> = [
  { key: "applied", label: "Applied", tone: "base" },
  { key: "auto_eligible", label: "Eligible (auto)", tone: "base" },
  { key: "auto_excluded", label: "Excluded (auto)", tone: "alert" },
  { key: "needs_clinician", label: "Needs clinician", tone: "watch" },
  { key: "enrolled", label: "Enrolled", tone: "ink" },
];

export function ScreeningFunnel({ funnel }: { funnel: Funnel | null | undefined }) {
  const f = funnel ?? { applied: 0, auto_eligible: 0, auto_excluded: 0, needs_clinician: 0, enrolled: 0 };
  const max = Math.max(1, f.applied);
  return (
    <section className="st-block funnel" aria-labelledby="funnel-title">
      <div className="stack stack--tight">
        <div className="st-label">Pre-screening agent</div>
        <h2 className="st-subtitle" id="funnel-title">Screening funnel</h2>
      </div>
      <ol className="funnel__stages" role="list">
        {STAGES.map((s) => {
          const n = f[s.key] ?? 0;
          const pct = (100 * n) / max;
          return (
            <li key={s.key} className={`funnel__stage funnel__stage--${s.tone}`}>
              <span className="st-label">{s.label}</span>
              <div className="funnel__row">
                <div className="funnel__track" aria-hidden="true">
                  <span className="funnel__bar" style={{ width: `${Math.max(pct, n > 0 ? 1 : 0)}%` }} />
                </div>
                <span className="funnel__count">
                  <span className="t-readout">{formatNumber(n)}</span>
                  <span className="funnel__unit">{s.key === "applied" ? "people" : `${formatNumber(Math.round(pct * 10) / 10)} %`}</span>
                </span>
              </div>
            </li>
          );
        })}
      </ol>
      <p className="t-caption c-ash">SYNTHETIC applicants. A clinician confirms the shortlist and every flagged case.</p>
    </section>
  );
}

export function FlaggedLedger({ applicants }: { applicants: Applicant[] }) {
  const flagged = applicants.filter((a) => a.screening?.decision === "needs_clinician");
  const rows = flagged.slice().reverse().map((a) => [
    <span className="flagged__who">
      <span className="t-id">{a.id}</span>
      <span className="c-graphite">{a.name}</span>
      {a.source === "portal" ? <StatusPill tone="outline">Portal</StatusPill> : null}
    </span>,
    <ul className="flagged__reasons">{a.screening.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>,
    a.screening.evidence?.length ? (
      <div className="stack stack--tight">
        {a.screening.evidence.map((e, i) => <EvidenceQuote key={i} quote={e.quote} source="free text" />)}
      </div>
    ) : <span className="c-ash">No disclosure</span>,
  ]);
  return (
    <LedgerTable title={`Flagged for a clinician · ${flagged.length} applicants`}
      columns={["Applicant", "Reasons", "Quoted disclosure"]} rows={rows} maxHeight={420}
      empty="No applicant is waiting for a clinician." />
  );
}

export function FairnessTable({ groups }: { groups: FairnessGroup[] }) {
  const rows = groups.flatMap((g) => g.rows.map((r, i) => [
    i === 0 ? <span className="c-graphite">{g.by}</span> : "",
    r.group,
    <span className="num">{formatNumber(r.n)}</span>,
    <span className="num">{formatNumber(r.eligible)}</span>,
    <span className="num">{formatNumber(r.rate_pct)} %</span>,
  ]));
  const right = { align: "right" as const, mono: true };
  return (
    <div className="stack">
      <LedgerTable title="Fairness: eligibility by group"
        columns={["By", "Group", { label: "Applicants", ...right }, { label: "Eligible", ...right }, { label: "Rate", ...right }]}
        rows={rows} empty="Fairness is checked after screening." maxHeight={420} />
      <div className="fair__notes">
        {groups.map((g) => (
          <div key={g.by} className="fair__note">
            <StatusPill tone={g.flag ? "watch" : "good"}>{g.flag ? "Check" : "Even"}</StatusPill>
            <span className="t-body-sm c-graphite">
              {g.by}: spread <span className="num">{formatNumber(g.spread_pts)} pts</span>
              {g.note ? `. ${g.note}` : ", within 20 pts."}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
