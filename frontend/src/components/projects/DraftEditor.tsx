/**
 * Draft stage: a quiet document editor. Title (the project name) and the protocol body, autosaved to the
 * projects store after 600 ms. "Launch trial" creates the backend trial from the draft and moves to Design review.
 * After launch the draft is read-only.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../../api";
import { projects, type Project } from "../../store/projects";
import { useTrial } from "../../trial";

const PLACEHOLDER =
  "Start writing your protocol. Describe the drug, comparator, raters, who you will recruit and your primary outcome.";

type SaveState = "idle" | "saving" | "saved";

export function DraftEditor({ project }: { project: Project }) {
  const navigate = useNavigate();
  const { adopt } = useTrial();
  const [name, setName] = useState(project.name);
  const [draft, setDraft] = useState(project.draft);
  const [save, setSave] = useState<SaveState>("idle");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const body = useRef<HTMLTextAreaElement>(null);
  const timer = useRef<number | null>(null);
  const pending = useRef<{ name: string; draft: string } | null>(null);
  const launched = !!project.trialId;

  // Switching project resets local text.
  useEffect(() => {
    setName(project.name);
    setDraft(project.draft);
    setSave("idle");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  // Auto-grow the body.
  useLayoutEffect(() => {
    const el = body.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft]);

  const flush = () => {
    if (timer.current !== null) { window.clearTimeout(timer.current); timer.current = null; }
    const p = pending.current;
    if (!p) return;
    pending.current = null;
    projects.update(project.id, { name: p.name.trim() || "Untitled trial", draft: p.draft });
    setSave("saved");
  };

  // Save on unmount so nothing typed is lost.
  useEffect(() => () => flush(), // eslint-disable-line react-hooks/exhaustive-deps
    [project.id]);

  const schedule = (next: { name: string; draft: string }) => {
    pending.current = next;
    setSave("saving");
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(flush, 600);
  };

  const launch = async () => {
    if (!draft.trim() || launching) return;
    flush();
    setLaunching(true);
    setError(null);
    try {
      const state = await api.createTrial({ protocol_text: draft });
      projects.update(project.id, { trialId: state.trial_id, status: "running", draft, name: name.trim() || "Untitled trial" });
      adopt(state);
      navigate(`/trials/${project.id}/design-review`);
    } catch (e) {
      setError(errorText(e));
      setLaunching(false);
    }
  };

  return (
    <article className="draft">
      <div className="draft__bar">
        <span className="draft__save" aria-live="polite">
          {launched ? (
            <>Launched as trial <span className="t-id">{project.trialId}</span></>
          ) : save === "saving" ? "Saving…" : save === "saved" ? "Saved" : ""}
        </span>
        {launched ? null : (
          <button type="button" className="btn btn--filled" disabled={!draft.trim() || launching} onClick={() => void launch()}>
            {launching ? "Launching…" : "Launch trial"}
          </button>
        )}
      </div>
      {error ? <p className="draft__error" role="alert">{error}</p> : null}

      <input className="draft__title" aria-label="Trial name" value={name} readOnly={launched} placeholder="Untitled trial"
        onChange={(e) => { setName(e.target.value); schedule({ name: e.target.value, draft }); }} />
      <textarea ref={body} className="draft__body" aria-label="Protocol" value={draft} readOnly={launched} rows={12}
        placeholder={PLACEHOLDER}
        onChange={(e) => { setDraft(e.target.value); schedule({ name, draft: e.target.value }); }} />
    </article>
  );
}
