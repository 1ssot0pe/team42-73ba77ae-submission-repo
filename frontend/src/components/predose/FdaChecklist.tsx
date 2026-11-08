/**
 * FdaChecklist (design.md 8.7). Taupe sheet of ledger rows: mono item code, item text, a Present or
 * Missing pill, and the evidence quote from the protocol. A summary readout sits above: "2 / 8 → 4 / 8".
 */
import { EvidenceQuote, StatusPill } from "../shared";
import type { ChecklistItem } from "../../types";

export interface FdaChecklistProps {
  items: ChecklistItem[];
  baselineOk?: number | null;
  /** e.g. "protocol v3", used as the evidence source tag */
  source?: string;
}

export function FdaChecklist({ items, baselineOk, source }: FdaChecklistProps) {
  const ok = items.filter((c) => c.present).length;
  const n = items.length;
  return (
    <section className="sheet checklist" aria-labelledby="fda-title">
      <div className="checklist__head">
        <div className="stack stack--tight">
          <div className="eyebrow">FDA July 2026 guidance</div>
          <h2 className="t-heading-sm" id="fda-title">Blinding checklist</h2>
        </div>
        <div className="checklist__summary" aria-label={`${ok} of ${n} items met`}>
          {baselineOk !== undefined && baselineOk !== null && baselineOk !== ok ? (
            <span className="checklist__before num">{baselineOk} / {n} &rarr;</span>
          ) : null}
          <span className="t-readout num">{ok} / {n}</span>
          <span className="t-caption c-ash">items met</span>
        </div>
      </div>
      {n === 0 ? (
        <p className="t-body-sm c-smoke">The checklist appears after the first design review.</p>
      ) : (
        <ol className="checklist__rows" role="list">
          {items.map((c, i) => (
            <li key={c.id} className="checklist__row">
              <span className="checklist__code">FDA-{String(i + 1).padStart(2, "0")}</span>
              <div className="checklist__main">
                <span className="checklist__item">{c.item}</span>
                {c.evidence ? (
                  <EvidenceQuote quote={c.evidence} source={source} />
                ) : (
                  <span className="t-caption c-ash">{c.note || "No supporting sentence found in the protocol."}</span>
                )}
              </div>
              <StatusPill tone={c.present ? "good" : "alert"}>{c.present ? "Present" : "Missing"}</StatusPill>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
