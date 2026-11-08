/**
 * Draft stage: a quiet document editor. Title (the project name) and the protocol body, autosaved to the
 * projects store after 600 ms. The body is a block editor that renders the markdown as formatting and
 * stores plain markdown. The title lives only in the name field; Launch sends "# <name>" plus the body,
 * creates the backend trial and moves to Design review. After launch the draft is read-only.
 */
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorText } from "../../api";
import { projects, type Project } from "../../store/projects";
import { useTrial } from "../../trial";
import { BlockEditor } from "../editor/BlockEditor";
import { stripLeadingTitle } from "../editor/markdown";

const PLACEHOLDER =
  "Start writing your protocol. Describe the drug, comparator, raters, who you will recruit and your primary outcome.";

type SaveState = "idle" | "saving" | "saved";

/** Older projects kept the template's "# title" line in the body; drop it when it repeats the name. */
function withoutTitle(p: Project): string {
  return stripLeadingTitle(p.draft, p.name) ?? p.draft;
}

export function DraftEditor({ project }: { project: Project }) {
  const navigate = useNavigate();
  const { adopt } = useTrial();
  const [name, setName] = useState(project.name);
  const [draft, setDraft] = useState(() => withoutTitle(project));
  const [save, setSave] = useState<SaveState>("idle");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const titleRef = useRef<HTMLTextAreaElement>(null);
  const pending = useRef<{ name: string; draft: string } | null>(null);
  const launched = !!project.trialId;

  // Switching project resets local text.
  // Also fixes older projects whose body repeats the title, saving the stripped draft once.
  useEffect(() => {
    const clean = withoutTitle(project);
    setName(project.name);
    setDraft(clean);
    setSave("idle");
    if (clean !== project.draft && !project.trialId) projects.update(project.id, { draft: clean });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  // The title wraps rather than clipping long names: grow its height to fit, also when the width changes.
  const fitTitle = () => {
    const el = titleRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  };
  useLayoutEffect(fitTitle, [name]);
  useEffect(() => {
    const el = titleRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    let w = el.clientWidth;
    const ro = new ResizeObserver(() => { if (el.clientWidth !== w) { w = el.clientWidth; fitTitle(); } });
    ro.observe(el);
    void document.fonts?.ready.then(fitTitle);
    return () => ro.disconnect();
  }, []);

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
      const title = name.trim() || "Untitled trial";
      const state = await api.createTrial({ protocol_text: `# ${title}\n\n${draft}` });
      projects.update(project.id, { trialId: state.trial_id, status: "running", draft, name: title });
      adopt(state);
      navigate(`/trials/${project.id}/design-review`);
    } catch (e) {
      setError(errorText(e));
      setLaunching(false);
    }
  };

  return (
    <article className="draft draft--doc">
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

      <textarea ref={titleRef} className="draft__title draft__title--wrap" aria-label="Trial name" value={name} readOnly={launched}
        placeholder="Untitled trial" rows={1}
        onKeyDown={(e) => { if (e.key === "Enter") e.preventDefault(); }}
        onChange={(e) => {
          const v = e.target.value.replace(/[\r\n]+/g, " ");
          setName(v);
          schedule({ name: v, draft });
        }} />
      <BlockEditor key={project.id} value={draft} readOnly={launched} placeholder={PLACEHOLDER} ariaLabel="Protocol"
        onChange={(md) => { setDraft(md); schedule({ name, draft: md }); }} />
    </article>
  );
}
