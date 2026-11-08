/**
 * MissionReadouts (design.md Section 9 item 4): key readouts from every module, grouped with a small eyebrow.
 * A "Trial" group comes from state.counts; each module shows its first `perModule` KPIs from /kpis and links
 * to its page for the rest. STUB modules with no KPIs say so. Props: state, kpis (KpiMap | null), perModule.
 */
import { Link } from "react-router-dom";
import type { Kpi, KpiMap, TrialState } from "../../types";
import { ReadoutGrid, StatusPill, moduleLabel } from "../shared";

const ORDER = ["predose", "dosing", "postdose"];
const ROUTE: Record<string, string> = { predose: "/predose", dosing: "/dosing", postdose: "/postdose" };

function trialKpis(s: TrialState): Kpi[] {
  return [
    { label: "Participants enrolled", value: s.counts.enrolled, unit: `of ${s.counts.applicants} applied`,
      note: "SYNTHETIC applicants screened by the pre-screening agent" },
    { label: "Scheduled tasks", value: s.counts.schedule, unit: "tasks",
      note: "Dosing sessions, debriefs, check-ins, rater visits and follow-ups" },
    { label: "Blinding check-ins", value: s.counts.checkins, unit: "check-ins", note: "Collected so far" },
    { label: "Decisions waiting", value: s.pending_approvals, unit: "to sign",
      note: s.auto_approve ? "Auto-approve is on (demo): decisions sign themselves" : "Every trial-changing action needs a named human" },
  ];
}

export function MissionReadouts({ state, kpis, perModule = 4 }: { state: TrialState; kpis: KpiMap | null; perModule?: number }) {
  const mods = [...ORDER, ...Object.keys(kpis ?? {}).filter((m) => !ORDER.includes(m))];
  return (
    <section className="section" aria-label="Key readouts">
      <div className="section__head">
        <h2 className="t-heading-sm">Key readouts</h2>
        <span className="t-caption c-ash">All figures come from a SYNTHETIC simulation</span>
      </div>
      <div className="mc-readouts">
        <div className="mc-readouts__group">
          <div className="eyebrow">Trial</div>
          <ReadoutGrid kpis={trialKpis(state)} />
        </div>
        {mods.map((m) => {
          const list = kpis?.[m] ?? [];
          const stub = state.module_status[m] === "stub";
          return (
            <div key={m} className="mc-readouts__group">
              <div className="row row--between">
                <div className="row">
                  <span className="eyebrow">{moduleLabel(m)}</span>
                  {stub ? <StatusPill tone="neutral">Stub</StatusPill> : null}
                </div>
                {list.length > perModule && ROUTE[m] ? (
                  <Link className="link-smoke t-body-sm" to={ROUTE[m]}>
                    All <span className="num">{list.length}</span> readouts
                  </Link>
                ) : null}
              </div>
              {list.length > 0 ? (
                <ReadoutGrid kpis={list.slice(0, perModule)} />
              ) : (
                <p className="t-body-sm c-smoke mc-readouts__empty">
                  {kpis === null ? "Loading readouts…"
                    : stub ? `${moduleLabel(m)} is a labelled STUB until its module is merged. Its readouts appear here then.`
                    : "Readouts appear once this module's agents have run."}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
