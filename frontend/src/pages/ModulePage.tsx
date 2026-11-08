/**
 * Generic stage content for dosing and follow-up (design v2). Embedded inside the project workspace,
 * which supplies the heading, trial clock and stepper, so no page chrome is drawn here.
 * Rendered entirely from the module's view model (GET /modules/{module}/view), refetched on every trial tick:
 *   stub note -> bottlenecks -> one readout row -> agent notes -> charts -> approvals -> forms -> tables -> agent log.
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

      <section className="st-section st-section--first" aria-label="Bottlenecks and readouts">
        <BottleneckCards module={module} />
        <ReadoutGrid kpis={model.kpis} empty={view ? "This module reports no readouts yet." : "Loading readouts."} />
      </section>

      {model.cards.length > 0 ? (
        <section className="st-section" aria-labelledby="m-cards">
          <div className="st-head">
            <div className="st-head__text">
              <h2 id="m-cards" className="st-title">What the agents see</h2>
              <p className="st-label"><span className="num">{model.cards.length}</span> {model.cards.length === 1 ? "note" : "notes"}</p>
            </div>
          </div>
          <ViewCards cards={model.cards} />
        </section>
      ) : null}

      {model.charts.length > 0 ? (
        <section className="st-section" aria-labelledby="m-charts">
          <div className="st-head">
            <div className="st-head__text">
              <h2 id="m-charts" className="st-title">Charts</h2>
              <p className="st-label">Synthetic data</p>
            </div>
          </div>
          <div className="mcharts">
            {model.charts.map((c, i) => <ModuleChart key={`${c.title}-${i}`} chart={c} />)}
          </div>
        </section>
      ) : null}

      <section className="st-section" aria-label="Approvals">
        <ApprovalInbox module={module} title="Approvals" />
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

      {model.tables.length > 0 ? (
        <section className="st-section" aria-labelledby="m-tables">
          <div className="st-head">
            <div className="st-head__text">
              <h2 id="m-tables" className="st-title">Ledgers</h2>
              <p className="st-label"><span className="num">{model.tables.length}</span> {model.tables.length === 1 ? "table" : "tables"}</p>
            </div>
          </div>
          <ViewTables tables={model.tables} />
        </section>
      ) : null}

      <section className="st-section">
        <AgentLog module={module} title="Agent log" />
      </section>
    </div>
  );
}
