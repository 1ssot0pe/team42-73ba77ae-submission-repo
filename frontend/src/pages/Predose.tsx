/**
 * Pre-dosing stage content (design v2). Embedded inside the project workspace, which supplies the
 * page heading, trial clock and stepper, so this component draws no page chrome of its own.
 *
 * `only` picks one slice of the page for a workspace stage:
 *   "design"      protocol editor, FDA checklist, blinding risk sphere, drafted section, versions
 *   "recruitment" recruitment ads and the measurement plan
 *   "screening"   screening funnel, fairness table, flagged ledger
 * Left undefined, everything renders. Data fetching is identical in every case.
 */
import { useEffect, useState, type ReactNode } from "react";
import { api, errorText } from "../api";
import { useTrial } from "../trial";
import type { Kpi, RecordSections } from "../types";
import {
  AgentLog, ApprovalInbox, BottleneckCards, EmptyState, LoadingHairline, ReadoutGrid,
} from "../components/shared";
import { FdaChecklist } from "../components/predose/FdaChecklist";
import { ProtocolEditor } from "../components/predose/ProtocolEditor";
import { DraftedSection, VersionHistory } from "../components/predose/BlindingSection";
import { FairnessTable, FlaggedLedger, ScreeningFunnel } from "../components/predose/Screening";
import { MeasurementPlanLedger, RecruitmentAds } from "../components/predose/RecruitmentAds";
import { RiskCard } from "../components/predose/UnblindingSphere";
import "../styles/module.css";
import "../styles/predose.css";

const SECTIONS = ["protocol", "protocol_versions", "design_review", "recruitment", "applicants", "enrolled", "measurement_plan"] as const;
type Sections = Partial<Pick<RecordSections, (typeof SECTIONS)[number]>>;

export type PredoseSlice = "design" | "recruitment" | "screening";

function SectionHead({ label, title, children }: { label: string; title: string; children?: ReactNode }) {
  return (
    <div className="st-head">
      <div className="st-head__text">
        <h2 className="st-title">{title}</h2>
        <p className="st-label">{label}</p>
      </div>
      {children}
    </div>
  );
}

export default function Predose({ only }: { only?: PredoseSlice } = {}) {
  const { trialId, tick } = useTrial();
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
      <div className="stage-page pd-page">
        <EmptyState title="No trial yet"
          message="Launch the trial from this project to start the agents. The protocol review, screening funnel and measurement plan appear here." />
      </div>
    );
  }

  const dr = data?.design_review ?? null;
  const versions = data?.protocol_versions ?? [];
  const latest = versions.length ? versions[versions.length - 1].version : null;
  const enrolledN = data?.enrolled?.length ?? 0;
  const funnel = data?.recruitment?.funnel;

  const show = (slice: PredoseSlice) => !only || only === slice;
  const full = !only;
  const lead = enrolledN > 0
    ? <><span className="num">{enrolledN}</span> participants enrolled. Protocol edits are now amendments that need a named human.</>
    : funnel?.applied
      ? <><span className="num">{funnel.applied}</span> applicants screened. The shortlist waits for a clinician.</>
      : <>The agents are reviewing the protocol.</>;

  return (
    <div className="stage-page pd-page">
      <LoadingHairline active={loading && !data} />
      {full || error ? (
        <div className="st-intro">
          {full ? (
            <p className="st-lead">
              {data?.protocol?.title ? <>Protocol: {data.protocol.title}. </> : null}
              {lead}
            </p>
          ) : null}
          {error ? <p className="pd-error" role="alert">{error}</p> : null}
        </div>
      ) : null}

      <div className={`pd-layout${full ? "" : " pd-layout--slice"}`}>
        {full ? (
          <div className="pd-top">
            <BottleneckCards module="predose" />
            <ReadoutGrid kpis={kpis} />
          </div>
        ) : null}

        {full || only === "design" || only === "screening" ? (
          <aside className="pd-aside" aria-label="Pre-dosing approvals">
            <ApprovalInbox module="predose" title="Approvals" signedLimit={4} />
          </aside>
        ) : null}

        <div className="pd-main">
          {!data ? null : (
            <>
              {show("design") ? (
                <>
                  <section className="st-section">
                    <SectionHead label="Design review" title="Blinding risk and the FDA checklist" />
                    <div className="grid-pd">
                      <RiskCard risk={dr?.risk} baseline={dr?.baseline_risk} atEnrolment={dr?.risk_at_enrolment} />
                      <FdaChecklist items={dr?.checklist ?? []} baselineOk={dr?.baseline_checklist_ok} windowNote={dr?.window_note}
                        source={latest ? `protocol v${latest}` : "protocol"} />
                    </div>
                  </section>

                  <section className="st-section">
                    <SectionHead label="Protocol co-designer" title="Edit, save and re-check" />
                    <ProtocolEditor protocol={data.protocol} versions={versions} enrolled={enrolledN > 0} />
                    <DraftedSection md={dr?.blinding_section_md} />
                    <VersionHistory versions={versions} />
                  </section>
                </>
              ) : null}

              {show("screening") ? (
                <section className="st-section">
                  <SectionHead label="Pre-screening agent" title="Screening" />
                  <ScreeningFunnel funnel={funnel} />
                  <FairnessTable groups={data.recruitment?.fairness ?? []} />
                  <FlaggedLedger applicants={data.applicants ?? []} />
                </section>
              ) : null}

              {show("recruitment") ? (
                <>
                  <section className="st-section">
                    <SectionHead label="Recruitment ad writer" title="Recruitment ads" />
                    <RecruitmentAds recruitment={data.recruitment} />
                  </section>

                  <section className="st-section">
                    <SectionHead label="Measurement planner" title="Measurement plan" />
                    <MeasurementPlanLedger plan={data.measurement_plan} />
                  </section>
                </>
              ) : null}

              {full ? <AgentLog module="predose" title="Agent log" /> : null}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
