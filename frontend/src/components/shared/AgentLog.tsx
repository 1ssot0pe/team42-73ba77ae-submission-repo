/**
 * AgentLog (design.md 8.9). The lab notebook of everything the agents did. Newest first.
 * Props: module (optional: only that module's events, e.g. "predose"); title (default "Agent log");
 *   limit (events fetched, default 400); moduleTabs (default true when no module is given: filter pills by module).
 * Filter tabs: All, Decisions, Warnings, Human. Decision rows carry a DECISION pill, warnings a watch tint,
 * human rows a good-tint left hairline. Refetches whenever trial.tick changes.
 */
import { useEffect, useMemo, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { EventLevel, TrialEvent } from "../../types";
import { formatDay, moduleLabel } from "./format";
import { StatusPill } from "./Pills";

type Filter = "all" | "decision" | "warn" | "human";
const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" },
  { id: "decision", label: "Decisions" },
  { id: "warn", label: "Warnings" },
  { id: "human", label: "Human" },
];
const MODULE_TABS = ["master", "predose", "dosing", "postdose"];

export interface AgentLogProps {
  module?: string;
  title?: string;
  limit?: number;
  moduleTabs?: boolean;
}

function rowClass(level: EventLevel): string {
  if (level === "human") return "log__row log__row--human";
  if (level === "warn") return "log__row log__row--warn";
  return "log__row";
}

export function AgentLog({ module, title = "Agent log", limit = 400, moduleTabs }: AgentLogProps) {
  const { trialId, tick } = useTrial();
  const [events, setEvents] = useState<TrialEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [mod, setMod] = useState<string>("all");
  const showModTabs = moduleTabs ?? !module;

  useEffect(() => {
    if (!trialId) { setEvents(null); return; }
    let live = true;
    api.events(trialId, { module, limit })
      .then((ev) => { if (live) { setEvents(ev); setError(null); } })
      .catch((e) => live && setError(errorText(e)));
    return () => { live = false; };
  }, [trialId, tick, module, limit]);

  const rows = useMemo(() => {
    const xs = (events ?? []).filter((e) =>
      (filter === "all" || e.level === filter) && (module || mod === "all" || e.module === mod));
    return xs.slice().reverse();
  }, [events, filter, mod, module]);

  return (
    <section className="log" aria-label={title}>
      <div className="log__head">
        <div className="row row--between">
          <h2 className="t-title">{title}</h2>
          {events ? <span className="t-caption c-ash num">{rows.length} entries</span> : null}
        </div>
        <div className="tabs" role="group" aria-label="Filter by kind">
          {FILTERS.map((f) => (
            <button key={f.id} type="button" className="tab" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
              {f.label}
            </button>
          ))}
        </div>
        {showModTabs ? (
          <div className="tabs" role="group" aria-label="Filter by module">
            {["all", ...MODULE_TABS].map((m) => (
              <button key={m} type="button" className="tab" aria-pressed={mod === m} onClick={() => setMod(m)}>
                {m === "all" ? "All modules" : moduleLabel(m)}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {error ? <p className="log__empty" role="alert">{error}</p> : null}
      {!trialId ? (
        <p className="log__empty">Create a trial to start the agents. Everything they do is written here.</p>
      ) : events && rows.length === 0 ? (
        <p className="log__empty">No entries match this filter yet.</p>
      ) : (
        <div className="log__rows" tabIndex={0} aria-label={`${title} entries, newest first`}>
          {rows.map((e) => (
            <div key={e.idx} className={rowClass(e.level)}>
              <span className="log__day">{formatDay(e.day)}</span>
              <div className="log__body">
                <span className="log__agent">
                  {e.agent}
                  {!module && e.module ? <span className="log__module">{moduleLabel(String(e.module))}</span> : null}
                  {e.level === "decision" ? <StatusPill tone="outline">Decision</StatusPill> : null}
                  {e.level === "warn" ? <StatusPill tone="watch">Warning</StatusPill> : null}
                  {e.level === "human" ? <StatusPill tone="good">Human</StatusPill> : null}
                </span>
                <span className="log__text">{e.text}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
