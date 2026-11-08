/**
 * Mission control (design.md Section 9, plan.md 6.3). Judges drive the whole trial from here.
 * No trial: StartTrial (example tabs, paper protocol editor, auto-approve, Create trial).
 * With a trial: header (eyebrow, "Day X of 90", one smoke sentence), PhaseTrack, key readouts,
 * ApprovalInbox | AgentLog (5/12, 7/12), AgentNetwork, and the floating ControlDock.
 * KPIs, messages and the master summary refetch whenever trial.tick changes.
 */
import { useEffect, useState } from "react";
import { api, errorText } from "../api";
import { AgentNetwork } from "../components/mission/AgentNetwork";
import { ControlDock } from "../components/mission/ControlDock";
import { MissionReadouts } from "../components/mission/MissionReadouts";
import { PhaseTrack } from "../components/mission/PhaseTrack";
import { ReportSeal } from "../components/mission/ReportStatus";
import { isSigned, reportSentence } from "../components/mission/reportText";
import { StartTrial } from "../components/mission/StartTrial";
import { AgentLog, ApprovalInbox, Button, LoadingHairline, SpecimenBand, useToast } from "../components/shared";
import { useTrial } from "../trial";
import type { KpiMap, MessagesResponse, TrialEvent, TrialState } from "../types";
import "../styles/mission.css";

function sentence(s: string): string {
  const t = s.trim();
  if (!t) return t;
  const c = t.charAt(0).toUpperCase() + t.slice(1);
  return /[.!?]$/.test(c) ? c : `${c}.`;
}

/** Digits roll up on each change (design.md Section 10); reduced motion keeps a plain swap. */
function RollingNumber({ value }: { value: number }) {
  return (
    <span className="mc-roll" aria-live="off">
      <span key={value} className="mc-roll__digits num">{value}</span>
    </span>
  );
}

function Headline({ state }: { state: TrialState }) {
  if (state.day < 1) {
    return (
      <h1 className="t-display mc-head__title">
        Setup <span className="mc-head__sub">before day <span className="num">1</span> of <span className="num">{state.close_day}</span></span>
      </h1>
    );
  }
  return (
    <h1 className="t-display mc-head__title" aria-label={`Day ${state.day} of ${state.close_day}`}>
      Day <RollingNumber value={state.day} /> of <span className="num mc-head__num">{state.close_day}</span>
    </h1>
  );
}

function Running({ state }: { state: TrialState }) {
  const { trialId, tick, setTrialId } = useTrial();
  const toast = useToast();
  const [kpis, setKpis] = useState<KpiMap | null>(null);
  const [messages, setMessages] = useState<MessagesResponse | null>(null);
  const [summary, setSummary] = useState<TrialEvent | null>(null);

  useEffect(() => {
    if (!trialId) return;
    let live = true;
    Promise.all([api.kpis(trialId), api.messages(trialId), api.events(trialId, { module: "master", limit: 40 })])
      .then(([k, m, ev]) => {
        if (!live) return;
        setKpis(k);
        setMessages(m);
        const latest = [...ev].reverse().find((e) => e.level !== "warn") ?? null;
        setSummary(latest);
      })
      .catch((e) => { if (live) toast(errorText(e), "alert"); });
    return () => { live = false; };
  }, [trialId, tick, toast]);

  const n = state.pending_approvals;
  const deadEnd = Boolean(state.blocked) && n === 0;
  const closed = state.phase === "closed";
  // Once closed, the report sign-off status (when the backend sends it) beats the latest master event.
  const closedLine = closed ? reportSentence(state) : null;
  const report = state.report_status;
  const now = state.blocked
    ? deadEnd
      ? "Nothing to sign. Start a new trial or edit the protocol eligibility."
      : `Waiting for a human: ${n} ${n === 1 ? "decision" : "decisions"} to sign.`
    : closedLine
      ? closedLine
      : summary
        ? sentence(summary.text)
        : closed
          ? "The trial is closed. The FDA blinding report is waiting for sign-off."
          : "The agents are at work. Press Play or step a day to move the clock.";

  return (
    <>
      <header className="section mc-head">
        <div className="eyebrow">
          Trial <span className="num">{state.trial_id}</span> · Synthetic
        </div>
        <Headline state={state} />
        <p className={`t-body-lg mc-head__now${state.blocked ? " mc-head__now--blocked" : ""}`}>
          {state.blocked ? <span className="mc-head__flag">Waiting</span> : null}
          {now}
        </p>
        {isSigned(report) ? <div className="row"><ReportSeal report={report} className="mc-head__seal" /></div> : null}
        {deadEnd ? (
          <div className="row"><Button variant="filled" onClick={() => setTrialId(null)}>New trial</Button></div>
        ) : null}
      </header>

      <PhaseTrack state={state} />

      <MissionReadouts state={state} kpis={kpis} />

      <div className="grid-5-7 mc-columns">
        <ApprovalInbox moduleTabs />
        <AgentLog moduleTabs />
      </div>

      <AgentNetwork edges={messages?.edges ?? null} moduleStatus={state.module_status} />

      <ControlDock state={state} />
    </>
  );
}

export default function MissionControl() {
  const { trialId, state, error, setTrialId } = useTrial();
  const toast = useToast();

  useEffect(() => {
    if (error) toast(error, "alert");
  }, [error, toast]);

  return (
    <>
      <SpecimenBand />
      <main className={`page mc-page${state ? " mc-page--dock" : ""}`}>
        {state ? (
          <Running state={state} />
        ) : trialId ? (
          <>
            <LoadingHairline active={!error} />
            <header className="section mc-head">
              <div className="eyebrow">Trial <span className="num">{trialId}</span> · Synthetic</div>
              <h1 className="t-display">Loading the trial</h1>
              <p className="t-body-lg c-smoke">
                {error ? `${error}. Start the API server, or start a new trial.` : "Fetching the latest state from the master agent."}
              </p>
              {error ? <div className="row"><Button variant="filled" onClick={() => setTrialId(null)}>Start a new trial</Button></div> : null}
            </header>
          </>
        ) : (
          <StartTrial />
        )}
      </main>
    </>
  );
}
