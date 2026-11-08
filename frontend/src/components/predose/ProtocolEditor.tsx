/**
 * ProtocolEditor (design.md 8.13). Version chips above, the protocol shown as formatted markdown (the draft
 * editor's read-only renderer) with "Edit text" to switch to the plain text box, a slim diff gutter for the
 * returned +/- lines, a signed editor name and "Save version and re-check".
 *
 * module.py "recheck":
 *   before enrolment -> {ok, diff, risk, checklist, version}: applied at once, good toast.
 *   after enrolment  -> {ok, pending_approval, diff, message}: an amendment waiting for a human, info toast,
 *                       and the proposed diff is shown as pending.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { Protocol, ProtocolVersion } from "../../types";
import { Button, StatusPill, dotJoin, formatDay, formatNumber, useReviewer, useToast } from "../shared";
import { BlockView } from "../editor/BlockEditor";
import { isPending, type RecheckResult } from "./types";

/** One diff line: "+text" added, "-text" removed, anything else is shown as added (fix sentences). */
export function DiffLines({ lines, empty }: { lines: string[]; empty?: string }) {
  if (lines.length === 0) return <p className="t-caption c-ash">{empty ?? "No line changes."}</p>;
  return (
    <ol className="diff" role="list">
      {lines.map((ln, i) => {
        const del = ln.startsWith("-");
        const body = ln.startsWith("+") || del ? ln.slice(1) : ln;
        return (
          <li key={i} className={`diff__line ${del ? "diff__line--del" : "diff__line--add"}`}>
            <span className="diff__gutter" aria-label={del ? "removed" : "added"}>{del ? "−" : "+"}</span>
            <span className="diff__text">{body || " "}</span>
          </li>
        );
      })}
    </ol>
  );
}

function chipLabel(v: ProtocolVersion): string {
  const why = v.why.replace(/^fix approved by [^:]+:\s*/i, "").replace(/^amendment by /i, "amended by ");
  return why.length > 30 ? `${why.slice(0, 29).trimEnd()}…` : why;
}

interface LastSave {
  lines: string[];
  /** latest version number when the result came back */
  atVersion: number;
  pending: string | null;
  version: number | null;
}

export interface ProtocolEditorProps {
  protocol: Protocol | null | undefined;
  versions: ProtocolVersion[];
  enrolled: boolean;
}

export function ProtocolEditor({ protocol, versions, enrolled }: ProtocolEditorProps) {
  const { trialId, adopt } = useTrial();
  const toast = useToast();
  const [editor, setEditor] = useReviewer();
  const latest = versions.length ? versions[versions.length - 1] : null;
  const latestNo = latest?.version ?? 0;
  const [text, setText] = useState<string>(protocol?.text ?? "");
  const [selected, setSelected] = useState<number>(latestNo);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [last, setLast] = useState<LastSave | null>(null);
  const [editing, setEditing] = useState(false);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const seen = useRef<number>(-1);
  // Formatted view unless the person chose to edit or has unsaved changes.
  const showText = editing || dirty;

  useEffect(() => {
    if (editing) textRef.current?.focus();
  }, [editing]);

  // Load the newest text when a new version lands, unless the person is mid-edit.
  useEffect(() => {
    if (latestNo === seen.current) return;
    seen.current = latestNo;
    if (!dirty) {
      setText(protocol?.text ?? latest?.text ?? "");
      setSelected(latestNo);
    }
  }, [latestNo, dirty, protocol?.text, latest?.text]);

  const shown = useMemo(() => {
    if (last && last.atVersion === latestNo) return last;
    return null;
  }, [last, latestNo]);

  const pick = (v: ProtocolVersion) => {
    setSelected(v.version);
    setText(v.text);
    setDirty(v.version !== latestNo);
    setError(null);
  };

  const save = async () => {
    if (!trialId) return;
    if (!editor.trim()) {
      setError("Type your name first. Every decision is signed.");
      document.getElementById("protocol-editor-name")?.focus();
      return;
    }
    if (!text.trim()) {
      setError("The protocol is empty. Paste or type the protocol text first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await api.action<RecheckResult>(trialId, "predose", "recheck", { text, editor: editor.trim() });
      const r = res.result;
      if (!r.ok) {
        setError(r.error || "The re-check failed.");
        toast(r.error || "Re-check failed", "alert");
        return;
      }
      if (isPending(r)) {
        setLast({ lines: r.diff, atVersion: latestNo, pending: r.pending_approval, version: null });
        toast(`Sent for approval · ${r.diff.length} changed lines`, "info");
      } else {
        setLast({ lines: r.diff, atVersion: r.version, pending: null, version: r.version });
        toast(dotJoin(`Saved protocol v${r.version}`, `u ${formatNumber(r.risk.u)} (${r.risk.band})`,
          `${r.checklist.filter((c) => c.present).length} / ${r.checklist.length} FDA items`), "good");
      }
      setDirty(false);
      setEditing(false);
      adopt(res.state);
    } catch (e) {
      setError(errorText(e));
      toast(errorText(e), "alert");
    } finally {
      setBusy(false);
    }
  };

  const diffLines = shown ? shown.lines : (latest?.changes ?? []);
  const lineCount = text ? text.split("\n").length : 0;

  return (
    <section className="st-block editor" aria-labelledby="editor-title">
      <div className="stack stack--tight">
        <div className="st-label">Protocol co-designer</div>
        <h2 className="st-subtitle" id="editor-title">Protocol</h2>
      </div>
      {versions.length ? (
        <div className="editor__chips" role="group" aria-label="Protocol versions">
          {versions.map((v) => (
            <button key={v.version} type="button" className="vchip" aria-pressed={selected === v.version}
              title={`${v.why} (${formatDay(v.day)})`} onClick={() => pick(v)}>
              <span className="num">v{v.version}</span> {chipLabel(v)}
            </button>
          ))}
        </div>
      ) : null}
      {showText ? (
        <>
          <label className="visually-hidden" htmlFor="protocol-editor-text">Protocol text</label>
          <textarea id="protocol-editor-text" ref={textRef} className="editor__text" value={text} spellCheck
            onChange={(e) => { setText(e.target.value); setDirty(true); }} rows={18} />
        </>
      ) : (
        <BlockView value={text} className="editor__doc" ariaLabel="Protocol text" />
      )}
      <div className="row">
        {showText ? (
          !dirty ? <button type="button" className="textbtn" onClick={() => setEditing(false)}>Show formatted</button> : null
        ) : (
          <button type="button" className="textbtn" onClick={() => setEditing(true)}>Edit text</button>
        )}
      </div>
      <div className="editor__meta t-caption c-ash">
        <span className="num">{formatNumber(lineCount)} lines</span>
        <span className="num">{formatNumber(text.length)} characters</span>
        {selected !== latestNo ? <span>Showing v{selected}. Saving makes it a new version.</span> : null}
        {dirty ? <span>Unsaved changes</span> : null}
      </div>

      <div className="editor__diff">
        <div className="row row--between">
          <span className="st-label">
            {shown?.pending ? "Proposed change" : shown?.version ? `Re-check · v${shown.version}` : latest ? `Changes in v${latest.version}` : "Changes"}
          </span>
          {shown?.pending ? <StatusPill tone="watch">Waiting for approval</StatusPill> : null}
        </div>
        {shown?.pending ? (
          <p className="t-body-sm c-smoke">
            Participants are enrolled, so this edit is a protocol amendment. It applies once a named human approves it
            in the approval slips.
          </p>
        ) : null}
        <DiffLines lines={diffLines} empty={latest?.version === 1 ? "Initial draft. No changes yet." : undefined} />
      </div>

      <div className="editor__sign">
        <label className="field" htmlFor="protocol-editor-name">
          <span className="field__label">Editor</span>
          <input id="protocol-editor-name" className="input input--line" value={editor} autoComplete="name"
            placeholder="Your name" onChange={(e) => setEditor(e.target.value)} aria-required="true" />
        </label>
        <Button variant="outline" busy={busy} onClick={save}>Save version and re-check</Button>
      </div>
      <p className="field__help">
        {enrolled
          ? "Participants are enrolled: a saved edit becomes a protocol amendment that waits for approval."
          : "Before enrolment a saved edit becomes a new version at once and the agents re-check it."}
      </p>
      {error ? <p className="editor__error" role="alert">{error}</p> : null}
    </section>
  );
}
