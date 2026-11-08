/**
 * Evidence studio (/studio): check how blinded a published trial was and what its effect looks like
 * after adjusting for it. Saved analyses open from /studio?a=<id> without re-running.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../api";
import { EvidenceTimeout, health, runEvidence } from "../api-extra";
import { ProgressSteps } from "../components/studio/ProgressSteps";
import { ReportView } from "../components/studio/ReportView";
import { draftOutline, title as reportTitle } from "../components/studio/report";
import { analyses, onAnalysesChange } from "../store/analyses";
import type { Analysis } from "../store/analyses";
import { projects } from "../store/projects";
import "../styles/studio.css";

const EXAMPLES = ["NCT03866174", "NCT04077437", "NCT03429075"];
const TOO_LONG = "This analysis took too long for the live server. Try a trial ID, or run it locally.";

type Phase = "idle" | "running" | "done" | "error";

function errorMessage(e: unknown): string {
  if (e instanceof ApiError && e.status >= 400 && e.status < 500 && e.detail) return `${e.detail} ${TOO_LONG}`;
  return TOO_LONG;
}

function dateText(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

const ID_RE = /^(NCT\d{8}|10\.\d{4,}\/\S+)$/i;

export default function Studio() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const [input, setInput] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState("");
  const [current, setCurrent] = useState<Analysis | null>(null);
  const [past, setPast] = useState<Analysis[]>(() => analyses.list());
  const [gemini, setGemini] = useState<boolean | null>(null);
  const ctrl = useRef<AbortController | null>(null);
  const field = useRef<HTMLTextAreaElement>(null);

  useEffect(() => onAnalysesChange(() => setPast(analyses.list())), []);
  useEffect(() => () => ctrl.current?.abort(), []);

  useEffect(() => {
    let live = true;
    health().then((h) => live && setGemini(Boolean(h?.gemini))).catch(() => live && setGemini(null));
    return () => { live = false; };
  }, []);

  const grow = useCallback(() => {
    const el = field.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 320)}px`;
  }, []);
  useEffect(grow, [input, grow]);

  // Open a saved analysis from ?a=<id>. Each id is handled once, so a later error is not overwritten.
  const wanted = params.get("a");
  const handled = useRef<string | null>(null);
  useEffect(() => {
    if (!wanted || handled.current === wanted) return;
    handled.current = wanted;
    const a = analyses.get(wanted);
    if (a) {
      ctrl.current?.abort();
      setCurrent(a);
      setInput(a.input);
      setError("");
      setPhase("done");
    }
  }, [wanted]);

  const run = useCallback(async (raw: string) => {
    const text = raw.trim();
    if (!text) return;
    ctrl.current?.abort();
    const c = new AbortController();
    ctrl.current = c;
    setInput(text);
    setPhase("running");
    setError("");
    setCurrent(null);
    try {
      const report = await runEvidence(text, { signal: c.signal });
      if (c.signal.aborted) return;
      const saved = analyses.save({ input: text, title: reportTitle(report, ""), report });
      setCurrent(saved);
      setPhase("done");
      handled.current = saved.id;
      setParams({ a: saved.id });
    } catch (e) {
      if (c.signal.aborted && !(e instanceof EvidenceTimeout)) return;
      setError(errorMessage(e));
      setPhase("error");
    }
  }, [setParams]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    void run(input);
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      void run(input);
    }
  };

  const openSaved = (a: Analysis) => {
    ctrl.current?.abort();
    setCurrent(a);
    setInput(a.input);
    setError("");
    setPhase("done");
    handled.current = a.id;
    setParams({ a: a.id });
  };

  const useFixes = () => {
    if (!current) return;
    const name = current.title || current.input;
    const p = projects.create({
      name: `Trial informed by ${name.length > 80 ? `${name.slice(0, 77)}...` : name}`,
      template: "blank",
      draft: draftOutline(current.report, current.input),
    });
    navigate(`/trials/${p.id}/draft`);
  };

  const running = phase === "running";

  return (
    <main className="studio">
      <header className="studio-intro">
        <h1 className="studio-title">Evidence studio</h1>
        <p className="studio-lede">
          Check how blinded a published trial was and what its effect looks like after adjusting for it.
        </p>
      </header>

      <form className="studio-form" onSubmit={onSubmit}>
        <label htmlFor="studio-input" className="studio-label">Trial ID, DOI or pasted text</label>
        <div className="studio-form__row">
          <textarea
            id="studio-input"
            ref={field}
            className="studio-input"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder="NCT03866174"
            spellCheck={false}
            aria-describedby="studio-hint"
          />
          <button type="submit" className="btn btn--filled studio-run" disabled={running || !input.trim()}>
            {running ? "Running" : "Run"}
          </button>
        </div>
        <div className="studio-form__meta" id="studio-hint">
          <span className="studio-examples">
            <span className="studio-muted">Try</span>
            {EXAMPLES.map((ex) => (
              <button key={ex} type="button" className="studio-chip t-id" disabled={running} onClick={() => void run(ex)}>
                {ex}
              </button>
            ))}
          </span>
          {gemini !== null ? (
            <span className={`studio-status studio-status--${gemini ? "good" : "neutral"}`}>
              <span className="studio-status__dot" aria-hidden="true" />
              {gemini ? "AI assistance on" : "Rule-based mode"}
            </span>
          ) : null}
        </div>
      </form>

      {past.length ? (
        <section className="studio-past" aria-labelledby="studio-past-h">
          <h2 id="studio-past-h" className="studio-label">Past analyses</h2>
          <ul className="studio-past__list">
            {past.slice(0, 8).map((a) => {
              const label = a.title || a.input;
              return (
                <li key={a.id}>
                  <button
                    type="button"
                    className={`studio-past__row${current?.id === a.id ? " is-current" : ""}`}
                    aria-current={current?.id === a.id ? "true" : undefined}
                    onClick={() => openSaved(a)}
                  >
                    <span className={`studio-past__name${ID_RE.test(label) ? " t-id" : ""}`}>{label}</span>
                    <span className="studio-past__date">{dateText(a.createdAt)}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      <div className="studio-body">
        {running ? <ProgressSteps /> : null}
        {phase === "error" ? (
          <p className="studio-error" role="alert">
            <span className="studio-status studio-status--alert"><span className="studio-status__dot" aria-hidden="true" /></span>
            {error}
          </p>
        ) : null}
        {phase === "done" && current ? (
          <ReportView key={current.id} report={current.report} input={current.input} onUseFixes={useFixes} />
        ) : null}
      </div>
    </main>
  );
}
