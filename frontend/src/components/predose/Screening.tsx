/**
 * screening-funnel (visuals spec, chart D): a CONSORT-style flow, not a funnel. Eligible, needs clinician
 * and excluded are a split of everyone who applied (they add up to Applied), so they sit side by side
 * under it. Enrolled is drawn under the two groups it can come from, with the count from each stated.
 * Under each group, the most frequent screening reasons; at the bottom, enrolled people by stratum
 * (site and prior psychedelic use). Boxes are hairline outlines; each is named in words, never by colour.
 * Every number is counted in the browser from applicants[].screening, enrolled[] and recruitment.funnel.
 * Styles: styles/screening.css (classes sf-).
 */
import { useEffect, useRef } from "react";
import { ChartFrame, EvidenceQuote, LedgerTable, formatNumber } from "../shared";
import type { Applicant, Enrolled, FairnessGroup, Funnel } from "../../types";
import "../../styles/screening.css";

const pct = (n: number, d: number) => (d > 0 ? `${formatNumber(Math.round((1000 * n) / d) / 10)}%` : "0%");
/** The reason text up to its first ": " or "; ", which is the fact; the rest is the rule. */
const shortReason = (r: string) => r.split(/: |; /)[0];
const plural = (n: number, one: string, many: string) => `${formatNumber(n)} ${n === 1 ? one : many}`;

interface ReasonCount { reason: string; n: number }

function countReasons(apps: Applicant[]): ReasonCount[] {
  const m = new Map<string, number>();
  for (const a of apps) for (const r of a.screening?.reasons ?? []) m.set(r, (m.get(r) ?? 0) + 1);
  return [...m.entries()].map(([reason, n]) => ({ reason, n })).sort((a, b) => b.n - a.n || a.reason.localeCompare(b.reason));
}

function Reasons({ items, of, groupWord, show, id }: { items: ReasonCount[]; of: number; groupWord: string; show: number; id: string }) {
  if (!items.length) return <p className="sf-reasons__none">No reasons recorded.</p>;
  const top = items.slice(0, show);
  const rest = items.length - top.length;
  return (
    <div className="sf-reasons">
      <p className="sf-reasons__head" id={id}>Most frequent reasons</p>
      <ul className="sf-reasons__list" aria-labelledby={id}>
        {top.map((r) => {
          const words = `${formatNumber(r.n)} of ${formatNumber(of)} ${groupWord} (${pct(r.n, of)}): ${r.reason}`;
          return (
            <li key={r.reason} className="sf-reason" tabIndex={0} aria-label={words}>
              <span className="sf-reason__text">{shortReason(r.reason)}</span>
              <span className="sf-reason__bar" aria-hidden="true">
                <span style={{ width: `${(100 * r.n) / Math.max(1, of)}%` }} />
              </span>
              <span className="sf-reason__n num" aria-hidden="true">{formatNumber(r.n)}</span>
              <span className="sf-tip" role="tooltip">{words}</span>
            </li>
          );
        })}
      </ul>
      {rest > 0 ? <p className="sf-reasons__more">and {plural(rest, "more reason", "more reasons")} (View data)</p> : null}
    </div>
  );
}

const siteShort = (s: string) => s.replace(/\s*\(.*\)\s*$/, "");

export interface ScreeningFlowProps {
  funnel: Funnel | null | undefined;
  applicants?: Applicant[];
  enrolled?: Enrolled[];
  strata?: Record<string, number> | null;
}

export function ScreeningFunnel({ funnel, applicants = [], enrolled = [], strata }: ScreeningFlowProps) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {   // touch: a tapped tooltip closes on scroll
    const blur = () => {
      const a = document.activeElement as HTMLElement | null;
      if (a && ref.current?.contains(a)) a.blur();
    };
    window.addEventListener("scroll", blur, { passive: true });
    return () => window.removeEventListener("scroll", blur);
  }, []);

  const subtitle = "People, from application to enrolment. Automatic pre-screening, then one clinician decision on the shortlist.";
  const byDecision = (d: string) => applicants.filter((a) => a.screening?.decision === d);
  const eligible = byDecision("eligible");
  const flagged = byDecision("needs_clinician");
  const excluded = byDecision("excluded");
  const applied = applicants.length || funnel?.applied || 0;
  if (!applied) {
    return (
      <div ref={ref} className="sf">
        <ChartFrame id="screening-funnel" title="Screening" subtitle={subtitle} ariaLabel="Screening flow: no applicants yet."
          empty={{ title: "Screening starts after the recruitment adverts are approved" }}>{null}</ChartFrame>
      </div>
    );
  }
  const nE = applicants.length ? eligible.length : funnel?.auto_eligible ?? 0;
  const nF = applicants.length ? flagged.length : funnel?.needs_clinician ?? 0;
  const nX = applicants.length ? excluded.length : funnel?.auto_excluded ?? 0;
  const ids = new Set(enrolled.map((e) => e.id));
  const enrE = eligible.filter((a) => ids.has(a.id)).length;
  const enrF = flagged.filter((a) => ids.has(a.id)).length;
  const enrX = excluded.filter((a) => ids.has(a.id)).length;
  const nEnr = enrolled.length;
  const enrOther = nEnr - enrE - enrF - enrX;   // e.g. applicants not in this list; shown only when non-zero
  const reasonsX = countReasons(excluded);
  const reasonsF = countReasons(flagged);
  const waiting = nEnr === 0;

  // strata: enrolled people by site and prior use (from enrolled[].stratum, else recruitment.strata)
  const cellMap = new Map<string, number>();
  if (enrolled.length) for (const e of enrolled) if (e.stratum) cellMap.set(e.stratum, (cellMap.get(e.stratum) ?? 0) + 1);
  else for (const [k, v] of Object.entries(strata ?? {})) cellMap.set(k, v);
  const cells = [...cellMap.entries()].map(([k, n]) => {
    const [site, prior] = k.split("|");
    return { key: k, site: site ?? k, prior: prior ?? "", n };
  }).sort((a, b) => a.site.localeCompare(b.site) || a.prior.localeCompare(b.prior));
  const sites = [...new Set(cells.map((c) => c.site))];

  const title = waiting
    ? `${formatNumber(applied)} applicants screened: ${formatNumber(nE)} eligible, ${formatNumber(nF)} for a clinician, ${formatNumber(nX)} excluded`
    : `${formatNumber(nEnr)} of ${formatNumber(applied)} applicants enrolled: ${formatNumber(enrE)} of ${formatNumber(nE)} eligible, ${formatNumber(enrF)} of ${formatNumber(nF)} flagged`;
  const topX = reasonsX[0];
  const aria = `Screening flow: ${applied} applied; ${nE} eligible, ${nF} flagged for a clinician, ${nX} excluded; `
    + `${nEnr} enrolled${waiting ? " (the shortlist waits for a clinician)" : `, ${enrE} from eligible and ${enrF} from flagged`}.`
    + (topX ? ` Top exclusion reason ${shortReason(topX.reason)} (${topX.n}).` : "");

  const rows: Array<Record<string, string | number>> = [
    { group: "Flow", item: "Applied", n: applied, share: "100% of applied" },
    { group: "Flow", item: "Eligible (automatic)", n: nE, share: `${pct(nE, applied)} of applied` },
    { group: "Flow", item: "Needs clinician", n: nF, share: `${pct(nF, applied)} of applied` },
    { group: "Flow", item: "Excluded (automatic)", n: nX, share: `${pct(nX, applied)} of applied` },
    { group: "Flow", item: "Enrolled from eligible", n: enrE, share: `${pct(enrE, nE)} of eligible` },
    { group: "Flow", item: "Enrolled from needs clinician", n: enrF, share: `${pct(enrF, nF)} of flagged` },
    ...reasonsX.map((r) => ({ group: "Reason, excluded", item: r.reason, n: r.n, share: `${pct(r.n, nX)} of excluded` })),
    ...reasonsF.map((r) => ({ group: "Reason, needs clinician", item: r.reason, n: r.n, share: `${pct(r.n, nF)} of flagged` })),
    ...cells.map((c) => ({ group: "Enrolled by stratum", item: `${c.site}, ${c.prior}`, n: c.n, share: `${pct(c.n, nEnr)} of enrolled` })),
  ];

  const box = (cls: string, label: string, n: number, share: string | null, extra?: string) => (
    <div className={`sf-box ${cls}`}>
      <span className="sf-box__label">{label}</span>
      <span className="sf-box__n num">{formatNumber(n)}</span>
      {share ? <span className="sf-box__share num">{share}</span> : null}
      {extra ? <span className="sf-box__extra num">{extra}</span> : null}
    </div>
  );

  return (
    <div ref={ref} className="sf">
      <ChartFrame
        id="screening-funnel"
        title={title}
        subtitle={subtitle}
        ariaLabel={aria}
        dataTable={{
          columns: [
            { key: "group", label: "Group" }, { key: "item", label: "Item" },
            { key: "n", label: "Count", align: "right" }, { key: "share", label: "Share", align: "right", derived: true },
          ],
          rows,
          note: "Counted in the browser from applicants[].screening (decision and reasons), enrolled[] (ids and stratum) "
            + "and recruitment.funnel. Reasons can overlap: counts are mentions, not people.",
        }}
        dataTitle="Data: screening flow, reasons and strata"
        footnotes={<p>Reasons can overlap: counts are mentions, not people. Bars are shares of their own group.</p>}
      >
        <div className="sf-flow">
          <div className="sf-top">{box("sf-box--applied", "Applied", applied, null)}</div>
          <div className="sf-split" role="list" aria-label="Automatic pre-screening outcome">
            <div className="sf-col sf-col--eligible" role="listitem">
              {box("", "Eligible (automatic)", nE, `${pct(nE, applied)} of applied`)}
              <p className="sf-col__note">Met every rule. Go on the shortlist.</p>
            </div>
            <div className="sf-col sf-col--flagged" role="listitem">
              {box("sf-box--dashed", "Needs clinician", nF, `${pct(nF, applied)} of applied`)}
              <Reasons items={reasonsF} of={nF} groupWord="flagged" show={4} id="sf-r-f" />
            </div>
            <div className="sf-col sf-col--excluded" role="listitem">
              {box("sf-box--dotted", "Excluded (automatic)", nX, `${pct(nX, applied)} of applied`)}
              <Reasons items={reasonsX} of={nX} groupWord="excluded" show={6} id="sf-r-x" />
            </div>
          </div>
          <div className="sf-enrol">
            <div className="sf-enrol__links" aria-hidden="true">
              <span className={`sf-link sf-link--e${enrE === 0 ? " sf-link--zero" : ""}`}><span className="num">{formatNumber(enrE)}</span></span>
              <span className={`sf-link sf-link--f${enrF === 0 ? " sf-link--zero" : ""}`}><span className="num">{formatNumber(enrF)}</span></span>
            </div>
            {box("sf-box--enrolled", "Enrolled", nEnr, null,
              waiting ? "The shortlist waits for a clinician"
                : `${formatNumber(enrE)} of ${formatNumber(nE)} eligible, ${formatNumber(enrF)} of ${formatNumber(nF)} flagged`
                  + (enrX ? `, ${formatNumber(enrX)} of ${formatNumber(nX)} excluded` : "")
                  + (enrOther > 0 ? `, ${formatNumber(enrOther)} from elsewhere` : ""))}
          </div>
          {cells.length && !waiting ? (
            <div className="sf-strata">
              <p className="sf-strata__head">Enrolled by randomisation stratum (site and prior psychedelic use)</p>
              <div className="sf-strata__grid">
                {sites.map((site) => (
                  <div key={site} className="sf-site">
                    <span className="sf-site__name">{siteShort(site)}</span>
                    {cells.filter((c) => c.site === site).map((c) => (
                      <span key={c.key} className="sf-cell">
                        <span className="sf-cell__label">{c.prior}</span>
                        <span className="sf-cell__n num">{formatNumber(c.n)}</span>
                      </span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </ChartFrame>
    </div>
  );
}

export function FlaggedLedger({ applicants }: { applicants: Applicant[] }) {
  const flagged = applicants.filter((a) => a.screening?.decision === "needs_clinician");
  const rows = flagged.slice().reverse().map((a) => [
    <span className="flagged__who">
      <span className="t-id">{a.id}</span>
      <span className="c-graphite">{a.name}</span>
      {a.source === "portal" ? <span className="st-label">From the portal</span> : null}
    </span>,
    <ul className="flagged__reasons">{a.screening.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>,
    a.screening.evidence?.length ? (
      <div className="stack stack--tight">
        {a.screening.evidence.map((e, i) => <EvidenceQuote key={i} quote={e.quote} source="free text" />)}
      </div>
    ) : <span className="c-ash">No disclosure</span>,
  ]);
  return (
    <LedgerTable title={`Flagged for a clinician: ${flagged.length} ${flagged.length === 1 ? "applicant" : "applicants"}`}
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
            <span className="st-status fair__word">
              <span className={`st-dot st-dot--${g.flag ? "watch" : "good"}`} aria-hidden="true" />{g.flag ? "Check" : "Even"}
            </span>
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

/** One line for the page: how many groupings were checked and whether any needs a look. Null before screening. */
export function fairnessSummary(groups: FairnessGroup[]): { text: string; flagged: boolean } | null {
  if (!groups.length) return null;
  const flagged = groups.filter((g) => g.flag).map((g) => g.by);
  if (flagged.length === 0) {
    return { flagged: false, text: `Fairness: eligibility is even across ${groups.length === 1 ? "the one grouping" : `all ${groups.length} groupings`} checked.` };
  }
  return { flagged: true, text: `Fairness: check eligibility by ${flagged.join(" and ")}. The full table is in the fairness drawer.` };
}
