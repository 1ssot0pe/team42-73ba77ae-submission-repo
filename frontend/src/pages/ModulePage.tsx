/**
 * Generic stage content for dosing and follow-up (design v2). Embedded inside the project workspace,
 * which supplies the heading, trial clock and stepper, so no page chrome is drawn here.
 * Rendered entirely from the module's view model (GET /modules/{module}/view), refetched on every trial tick:
 *   stub note -> one readout row -> approvals -> the key chart -> details -> forms.
 * Design v2: the bottlenecks, the other charts, the agent notes, the tables and the agent log open in
 * right-hand drawers.
 * Every view key is optional; normalise.ts reads them defensively.
 */
import { useEffect, useMemo, useState } from "react";
import { api, errorText } from "../api";
import { useTrial } from "../trial";
import type { ViewModel } from "../types";
import {
  AgentLog, ApprovalInbox, BottleneckCards, EmptyState, LoadingHairline, ReadoutGrid, loadBottlenecks, moduleLabel,
} from "../components/shared";
import {
  ModuleChart, ViewCards, ViewForm, ViewTables, readCards, readCharts, readForms, readKpis, readTables,
} from "../components/module";
import { DetailsDrawer, DetailsRow } from "../components/projects/Drawer";
import "../styles/module.css";

export interface ModulePageProps {
  module: "dosing" | "postdose";
}

export default function ModulePage({ module }: ModulePageProps) {
  const { trialId, state, tick } = useTrial();
  const [view, setView] = useState<ViewModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [bnTitles, setBnTitles] = useState<Set<string>>(new Set());
  const label = moduleLabel(module);

  // A new module or trial starts clean.
  useEffect(() => {
    setView(null);
    setError(null);
  }, [module, trialId]);

  useEffect(() => {
    if (!trialId) return;
    let live = true;
    setLoading(true);
    api.view(trialId, module)
      .then((v) => {
        if (!live) return;
        setView(v && typeof v === "object" ? v : null);
        setError(null);
      })
      .catch((e) => live && setError(errorText(e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [trialId, module, tick]);

  // Bottleneck titles, so cards that only repeat a bottleneck card are not shown twice.
  useEffect(() => {
    let live = true;
    loadBottlenecks()
      .then((bs) => live && setBnTitles(new Set(bs.map((b) => b.title.trim().toLowerCase()))))
      .catch(() => { /* the bottleneck cards show their own error */ });
    return () => { live = false; };
  }, []);

  const model = useMemo(() => {
    const v = (view ?? {}) as Record<string, unknown>;
    return {
      kpis: readKpis(v.kpis),
      cards: readCards(v.cards).filter((c) => !bnTitles.has(c.title.trim().toLowerCase())),
      charts: readCharts(v.charts),
      forms: readForms(v.forms),
      tables: readTables(v.tables),
    };
  }, [view, bnTitles]);

  const isStub = view?.status === "stub" || state?.module_status?.[module] === "stub";
  const title = (typeof view?.title === "string" && view.title) || label;
  const keyChart = model.charts[0] ?? null;

  if (!trialId) {
    return (
      <div className="stage-page mpage">
        <EmptyState
          title="No trial yet"
          message={`Launch the trial from this project to start the agents. The ${label.toLowerCase()} stage fills in as the simulated days pass.`}
        />
      </div>
    );
  }

  return (
    <div className="stage-page mpage">
      <LoadingHairline active={loading && !view} />
      <div className="st-intro">
        {title !== label ? <h2 className="st-title">{title}</h2> : null}
        {isStub ? (
          <p className="st-status"><span className="st-dot st-dot--watch" aria-hidden="true" />
            Stub module. It does the minimum so the trial runs end to end.</p>
        ) : null}
        {state?.blocked ? (
          <p className="st-status"><span className="st-dot st-dot--alert" aria-hidden="true" />Blocked: {state.blocked}</p>
        ) : null}
      </div>

      {error && !view ? (
        <EmptyState title="View not available" message={`The ${label.toLowerCase()} view could not be loaded: ${error}. Check that the backend is running, then reload.`} />
      ) : null}
      {view?.error ? <EmptyState title="View not available" message={String(view.error)} /> : null}

      <section className="st-section st-section--first" aria-label="Readouts">
        <ReadoutGrid kpis={model.kpis} empty={view ? "This module reports no readouts yet." : "Loading readouts."} />
      </section>

      <section className="st-section" aria-label="Approvals">
        <ApprovalInbox module={module} title="Approvals" />
      </section>

      <section className="st-section" aria-labelledby="m-charts">
        {keyChart ? (
          <>
            <div className="st-head">
              <div className="st-head__text">
                <h2 id="m-charts" className="st-title">At a glance</h2>
                <p className="st-label">Synthetic data</p>
              </div>
            </div>
            <div className="mcharts mcharts--key">
              <ModuleChart chart={keyChart} />
            </div>
          </>
        ) : (
          <h2 id="m-charts" className="mdetails__title">Details</h2>
        )}
        <DetailsRow>
          <DetailsDrawer label="View bottlenecks" title="Bottlenecks" width={560}
            subtitle="The published problems this stage is built to fix, with their sources">
            <BottleneckCards module={module} />
          </DetailsDrawer>
          {model.charts.length > 1 ? (
            <DetailsDrawer label="View all charts" title="Charts" subtitle="Synthetic data" width={760}
              meta={<><span className="num">{model.charts.length}</span> charts</>}>
              <div className="mcharts">
                {model.charts.map((c, i) => <ModuleChart key={`${c.title}-${i}`} chart={c} />)}
              </div>
            </DetailsDrawer>
          ) : null}
          {model.cards.length > 0 ? (
            <DetailsDrawer label="View agent notes" title="What the agents see"
              meta={<><span className="num">{model.cards.length}</span> {model.cards.length === 1 ? "note" : "notes"}</>}>
              <ViewCards cards={model.cards} />
            </DetailsDrawer>
          ) : null}
          {model.tables.length > 0 ? (
            <DetailsDrawer label="View all tables" title="Ledgers" subtitle="Synthetic data. Wide tables scroll sideways." width={880}
              meta={<><span className="num">{model.tables.length}</span> {model.tables.length === 1 ? "table" : "tables"}</>}>
              <ViewTables tables={model.tables} />
            </DetailsDrawer>
          ) : null}
          <DetailsDrawer label="View agent log" title="Agent log" subtitle={`${label} agents, newest first`} width={560}>
            <AgentLog module={module} title="Agent log" />
          </DetailsDrawer>
        </DetailsRow>
      </section>

      {model.forms.length > 0 ? (
        <section className="st-section" aria-labelledby="m-forms">
          <div className="st-head">
            <div className="st-head__text">
              <h2 id="m-forms" className="st-title">Act on the trial</h2>
              <p className="st-label">Synthetic participants</p>
            </div>
          </div>
          <div className="mforms">
            {model.forms.map((f) => <ViewForm key={f.id} module={module} form={f} />)}
          </div>
        </section>
      ) : null}
    </div>
  );
}
