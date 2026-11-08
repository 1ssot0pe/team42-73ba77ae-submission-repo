/**
 * FdaChecklist (design.md 8.7). Flat hairline rows: mono item code, item text, a Present or
 * Missing pill, the evidence quote from the protocol and any agent note. A summary readout sits above: "2 / 8 → 4 / 8".
 * windowNote (design_review.window_note) shows as a watch-toned line under the rows when present.
 */
import { EvidenceQuote, StatusPill } from "../shared";
import type { ChecklistItem } from "../../types";

export interface FdaChecklistProps {
  items: ChecklistItem[];
  /** design_review.window_note: primary endpoint week outside the 90-day simulation window. Hidden when empty. */
  windowNote?: string | null;
  baselineOk?: number | null;
  /** e.g. "protocol v3", used as the evidence source tag */
  source?: string;
}

export function FdaChecklist({ items, baselineOk, source, windowNote }: FdaChecklistProps) {
  const ok = items.filter((c) => c.present).length;
  const n = items.length;
  return (
    <section className="st-block checklist" aria-labelledby="fda-title">
      <div className="checklist__head">
        <div className="stack stack--tight">
          <div className="st-label">FDA July 2026 guidance</div>
          <h2 className="st-subtitle" id="fda-title">Blinding checklist</h2>
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
                {c.evidence ? <EvidenceQuote quote={c.evidence} source={source} /> : null}
                {c.note?.trim() ? (
                  <span className="t-caption c-ash">{c.note}</span>
                ) : !c.evidence ? (
                  <span className="t-caption c-ash">No supporting sentence found in the protocol.</span>
                ) : null}
              </div>
              {c.present
                ? <span className="st-status"><span className="st-dot st-dot--good" aria-hidden="true" />Present</span>
                : <StatusPill tone="alert">Missing</StatusPill>}
            </li>
          ))}
        </ol>
      )}
      {windowNote?.trim() ? (
        <p className="checklist__window" role="note">
          <span className="checklist__window-flag">Note</span>
          <span>{windowNote}</span>
        </p>
      ) : null}
    </section>
  );
}
