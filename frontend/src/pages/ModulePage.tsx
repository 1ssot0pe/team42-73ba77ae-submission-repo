/**
 * Generic module page for dosing and post-dosing (design.md Section 9, plan.md Phase 8).
 * Rendered entirely from the module's view model (GET /modules/{module}/view), refetched on every trial tick:
 *   STUB band (when the module is a placeholder) -> header -> bottleneck cards -> readouts -> cards -> charts
 *   -> approval slips for this module -> forms as paper documents -> tables -> agent log for this module.
 * Every view key is optional; normalise.ts reads them defensively.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorText } from "../api";
import { useTrial } from "../trial";
import type { ViewModel } from "../types";
import {
  AgentLog, ApprovalInbox, BottleneckCards, EmptyState, LoadingHairline, ReadoutGrid, SpecimenBand, buttonClass,
  dotJoin, formatDay, loadBottlenecks, moduleLabel,
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
      <>
        <SpecimenBand />
        <main className="page">
          <header className="section mpage__head">
            <div className="eyebrow">{label}</div>
            <h1 className="t-display">{label}</h1>
          </header>
          <EmptyState
            title="No trial yet"
            message={`Create a trial in Mission control to start the agents. The ${label.toLowerCase()} page fills in as the simulated days pass.`}
            action={<Link className={buttonClass("filled")} to="/">Go to Mission control</Link>}
          />
        </main>
      </>
    );
  }

  return (
    <>
      <SpecimenBand />
      {isStub ? (
        <SpecimenBand
          variant="stub"
          label="STUB MODULE"
          message={`This ${label.toLowerCase()} module is a labelled STUB. It does the minimum so the trial runs end to end.`}
        />
      ) : null}
      <LoadingHairline active={loading && !view} />
      <main className="page">
        <header className="section mpage__head">
          <div className="eyebrow">
            {dotJoin(label, trialId, state ? formatDay(state.day) : null, isStub ? "STUB" : null, "SYNTHETIC")}
          </div>
          <h1 className="t-display">{title}</h1>
          {state ? (
            <p className="t-body c-smoke mpage__lede">
              Day <span className="num">{state.day}</span> of <span className="num">{state.close_day}</span>, phase {state.phase}.
              {state.blocked ? ` Blocked: ${state.blocked}` : ""}
            </p>
          ) : null}
        </header>

        {error && !view ? (
          <EmptyState title="View not available" message={`The ${label.toLowerCase()} view could not be loaded: ${error}. Check that the backend is running, then reload.`} />
        ) : null}
        {view?.error ? <EmptyState title="View not available" message={String(view.error)} /> : null}

        <section className="section" aria-label="Bottlenecks">
          <BottleneckCards module={module} />
        </section>

        <section className="section" aria-labelledby="m-readouts">
          <div className="section__head">
            <h2 id="m-readouts" className="t-heading-sm">Readouts</h2>
            <span className="t-label c-ash">Quantified impact</span>
          </div>
          <ReadoutGrid kpis={model.kpis} empty={view ? "This module reports no readouts yet." : "Loading readouts."} />
        </section>

        {model.cards.length > 0 ? (
          <section className="section" aria-labelledby="m-cards">
            <div className="section__head">
              <h2 id="m-cards" className="t-heading-sm">What the agents see</h2>
              <span className="t-label c-ash"><span className="num">{model.cards.length}</span> {model.cards.length === 1 ? "note" : "notes"}</span>
            </div>
            <ViewCards cards={model.cards} />
          </section>
        ) : null}

        {model.charts.length > 0 ? (
          <section className="section" aria-labelledby="m-charts">
            <div className="section__head">
              <h2 id="m-charts" className="t-heading-sm">Charts</h2>
              <span className="t-label c-ash">Synthetic data</span>
            </div>
            <div className="mcharts">
              {model.charts.map((c, i) => <ModuleChart key={`${c.title}-${i}`} chart={c} />)}
            </div>
          </section>
        ) : null}

        <ApprovalInbox module={module} title={`${label} approvals`} />

        {model.forms.length > 0 ? (
          <section className="section" aria-labelledby="m-forms">
            <div className="section__head">
              <h2 id="m-forms" className="t-heading-sm">Act on the trial</h2>
              <span className="t-label c-ash">Synthetic participants</span>
            </div>
            <div className="mforms">
              {model.forms.map((f) => <ViewForm key={f.id} module={module} form={f} />)}
            </div>
          </section>
        ) : null}

        {model.tables.length > 0 ? (
          <section className="section" aria-labelledby="m-tables">
            <div className="section__head">
              <h2 id="m-tables" className="t-heading-sm">Ledgers</h2>
              <span className="t-label c-ash"><span className="num">{model.tables.length}</span> {model.tables.length === 1 ? "table" : "tables"}</span>
            </div>
            <ViewTables tables={model.tables} />
          </section>
        ) : null}

        <AgentLog module={module} title={`${label} agent log`} />
      </main>
    </>
  );
}
