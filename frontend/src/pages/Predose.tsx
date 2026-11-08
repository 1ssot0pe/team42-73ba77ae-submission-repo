/**
 * Pre-dosing page (plan.md 7.1, design.md Section 9 Pre-dosing).
 * Bottleneck cards → readouts → sphere | FDA checklist → protocol editor | drafted section and versions →
 * screening funnel, flagged ledger, fairness → recruitment ads → measurement plan → agent log.
 * Approval slips for pre-dosing sit in a sticky right column at 1100px and wider.
 */
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api";
import { useTrial } from "../trial";
import type { Kpi, RecordSections } from "../types";
import {
  AgentLog, ApprovalInbox, BottleneckCards, EmptyState, LoadingHairline, ReadoutGrid, SpecimenBand, buttonClass, dotJoin,
} from "../components/shared";
import { FdaChecklist } from "../components/predose/FdaChecklist";
import { ProtocolEditor } from "../components/predose/ProtocolEditor";
import { DraftedSection, VersionHistory } from "../components/predose/BlindingSection";
import { FairnessTable, FlaggedLedger, ScreeningFunnel } from "../components/predose/Screening";
import { MeasurementPlanLedger, RecruitmentAds } from "../components/predose/RecruitmentAds";
import { RiskCard } from "../components/predose/UnblindingSphere";
import "../styles/predose.css";

const SECTIONS = ["protocol", "protocol_versions", "design_review", "recruitment", "applicants", "enrolled", "measurement_plan"] as const;
type Sections = Partial<Pick<RecordSections, (typeof SECTIONS)[number]>>;

function SectionHead({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return (
    <div className="section__head">
      <div className="stack stack--tight">
        <div className="eyebrow">{eyebrow}</div>
        <h2 className="t-heading">{title}</h2>
      </div>
      {children}
    </div>
  );
}

export default function Predose() {
  const { trialId, state, tick } = useTrial();
  const [data, setData] = useState<Sections | null>(null);
  const [kpis, setKpis] = useState<Kpi[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!trialId) { setData(null); setKpis(null); return; }
    let live = true;
    setLoading(true);
    Promise.all([api.record(trialId, [...SECTIONS]), api.kpis(trialId)])
      .then(([rec, k]) => {
        if (!live) return;
        setData(rec);
        setKpis(k.predose ?? []);
        setError(null);
      })
      .catch((e) => live && setError(errorText(e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [trialId, tick]);

  if (!trialId) {
    return (
      <>
        <SpecimenBand />
        <main className="page">
          <header className="section">
            <div className="eyebrow">Pre-dosing</div>
            <h1 className="t-display">Design, recruitment and screening</h1>
          </header>
          <EmptyState title="No trial yet"
            message="Create a trial in Mission control to start the agents. The protocol review, screening funnel and measurement plan appear here."
            action={<Link className={buttonClass("filled")} to="/">Go to Mission control</Link>} />
        </main>
      </>
    );
  }

  const dr = data?.design_review ?? null;
  const versions = data?.protocol_versions ?? [];
  const latest = versions.length ? versions[versions.length - 1].version : null;
  const enrolledN = data?.enrolled?.length ?? 0;
  const funnel = data?.recruitment?.funnel;

  return (
    <>
      <SpecimenBand />
      <LoadingHairline active={loading && !data} />
      <main className="page pd-page">
        <header className="section">
          <div className="eyebrow">{dotJoin("Pre-dosing", state?.trial_id ?? trialId, "Synthetic")}</div>
          <h1 className="t-display">Design, recruitment and screening</h1>
          <p className="t-body-lg c-smoke">
            {data?.protocol?.title ? <>Protocol: {data.protocol.title}. </> : null}
            {enrolledN > 0
              ? <><span className="num">{enrolledN}</span> participants enrolled. Protocol edits are now amendments that need a named human.</>
              : funnel?.applied
                ? <><span className="num">{funnel.applied}</span> applicants screened. The shortlist waits for a clinician.</>
                : <>The agents are reviewing the protocol.</>}
          </p>
          {error ? <p className="pd-error" role="alert">{error}</p> : null}
        </header>

        <div className="pd-layout">
          <div className="pd-top stack stack--loose">
            <BottleneckCards module="predose" />
            <ReadoutGrid kpis={kpis} />
          </div>

          <aside className="pd-aside" aria-label="Pre-dosing approvals">
            <ApprovalInbox module="predose" title="Pre-dosing approvals" signedLimit={4} />
          </aside>

          <div className="pd-main">
            {!data ? null : (
              <>
                <section className="section">
                  <SectionHead eyebrow="Design review" title="Blinding risk and the FDA checklist" />
                  <div className="grid-pd">
                    <RiskCard risk={dr?.risk} baseline={dr?.baseline_risk} />
                    <FdaChecklist items={dr?.checklist ?? []} baselineOk={dr?.baseline_checklist_ok}
                      source={latest ? `protocol v${latest}` : "protocol"} />
                  </div>
                </section>

                <section className="section">
                  <SectionHead eyebrow="Protocol co-designer" title="Edit, save and re-check" />
                  <div className="grid-pd">
                    <ProtocolEditor protocol={data.protocol} versions={versions} enrolled={enrolledN > 0} />
                    <div className="stack stack--loose">
                      <DraftedSection md={dr?.blinding_section_md} />
                      <VersionHistory versions={versions} />
                    </div>
                  </div>
                </section>

                <section className="section">
                  <SectionHead eyebrow="Recruitment and pre-screening" title="Screening" />
                  <ScreeningFunnel funnel={funnel} />
                  <FlaggedLedger applicants={data.applicants ?? []} />
                  <FairnessTable groups={data.recruitment?.fairness ?? []} />
                </section>

                <section className="section">
                  <SectionHead eyebrow="Recruitment ad writer" title="Recruitment ads" />
                  <RecruitmentAds recruitment={data.recruitment} />
                </section>

                <section className="section">
                  <SectionHead eyebrow="Measurement planner" title="Measurement plan" />
                  <MeasurementPlanLedger plan={data.measurement_plan} />
                </section>

                <AgentLog module="predose" title="Pre-dosing agent log" />
              </>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
