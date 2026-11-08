/**
 * StartTrial (design.md Section 9, before a trial exists): example protocol tab pills above a paper-document
 * protocol editor, an Auto-approve (demo fast-forward) switch and a filled "Create trial" pill.
 * On success it adopts the new TrialState (which also stores the trial id).
 */
import { useEffect, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { ProtocolSummary } from "../../types";
import { Button, LoadingHairline, useToast } from "../shared";

/** "DRAFT protocol (FICTIONAL EXAMPLE): Single-dose psilocybin ..." -> "Single-dose psilocybin ..." */
function shortTitle(p: ProtocolSummary): string {
  const t = p.title || p.name;
  const i = t.indexOf(": ");
  return i >= 0 ? t.slice(i + 2) : t;
}

export function StartTrial() {
  const { setTrialId, adopt } = useTrial();
  const toast = useToast();
  const [protocols, setProtocols] = useState<ProtocolSummary[] | null>(null);
  const [example, setExample] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [edited, setEdited] = useState(false);
  const [loadingText, setLoadingText] = useState(false);
  const [autoApprove, setAutoApprove] = useState(false);
  const [busy, setBusy] = useState(false);

  const pick = async (name: string | null) => {
    setExample(name);
    setEdited(false);
    if (!name) { setText(""); return; }
    setLoadingText(true);
    try {
      const p = await api.protocol(name);
      setText(p.text);
    } catch (e) {
      toast(errorText(e), "alert");
    } finally {
      setLoadingText(false);
    }
  };

  useEffect(() => {
    let live = true;
    api.protocols()
      .then((ps) => {
        if (!live) return;
        setProtocols(ps);
        const first = ps.find((p) => p.name.includes("psilocybin")) ?? ps[0];
        if (first) void pick(first.name);
      })
      .catch((e) => { if (live) { setProtocols([]); toast(errorText(e), "alert"); } });
    return () => { live = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const create = async () => {
    if (!text.trim()) { toast("Paste or pick a protocol first", "watch"); return; }
    setBusy(true);
    try {
      const body = edited || !example
        ? { protocol_text: text, auto_approve: autoApprove }
        : { example, auto_approve: autoApprove };
      const s = await api.createTrial(body);
      setTrialId(s.trial_id);
      adopt(s);
      toast(`Trial ${s.trial_id} created`, "good");
    } catch (e) {
      toast(errorText(e), "alert");
    } finally {
      setBusy(false);
    }
  };

  const lines = text ? text.split("\n").length : 0;

  return (
    <>
      <LoadingHairline active={busy || loadingText} />
      <header className="section mc-head">
        <div className="eyebrow">Mission control · Synthetic</div>
        <h1 className="t-display">Start a trial</h1>
        <p className="t-body-lg c-smoke">
          Pick an example draft protocol or paste your own. The pre-dosing agents score its blinding risk, check it
          against the FDA guidance, write recruitment ads and screen <span className="num">500</span> synthetic applicants.
        </p>
      </header>

      <section className="section" aria-label="Protocol">
        <div className="tabs" role="group" aria-label="Example protocols">
          {(protocols ?? []).map((p) => (
            <button key={p.name} type="button" className="tab" aria-pressed={example === p.name && !edited}
              onClick={() => void pick(p.name)} title={p.title}>
              {shortTitle(p)}
            </button>
          ))}
          <button type="button" className="tab" aria-pressed={protocols !== null && example === null && !edited} onClick={() => void pick(null)}>
            Blank page
          </button>
        </div>

        <div className="paper mc-editor">
          <div className="mc-editor__head">
            <span className="eyebrow">Draft protocol</span>
            <span className="t-caption c-ash">
              {edited ? "Edited" : example ? "Fictional example" : "Your own text"}
              {" · "}<span className="num">{lines}</span> lines
            </span>
          </div>
          <label htmlFor="mc-protocol" className="visually-hidden">Protocol text</label>
          <textarea id="mc-protocol" className="mc-editor__text" value={text} spellCheck={false}
            placeholder="Paste a draft protocol here: title, drug, comparator, raters, sites, eligibility, endpoints."
            onChange={(e) => { setText(e.target.value); setEdited(true); }} disabled={busy} />
        </div>

        <div className="mc-start__actions">
          <label className="switch switch--watch">
            <input type="checkbox" checked={autoApprove} onChange={(e) => setAutoApprove(e.target.checked)} disabled={busy} />
            <span>Auto-approve (demo fast-forward)</span>
          </label>
          <span className="field__help">Signs every decision as "demo reviewer (auto-approve ON)". Leave it off to sign them yourself.</span>
          <Button variant="filled" busy={busy} onClick={() => void create()} disabled={!text.trim() || loadingText}
            className="mc-start__create">
            Create trial
          </Button>
        </div>
      </section>
    </>
  );
}
