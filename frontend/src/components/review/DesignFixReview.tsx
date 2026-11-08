/**
 * DesignFixReview (fix round 1, F1). One panel to sign every pending protocol fix from the design review.
 *
 * Props: fixes (pending predose approvals whose action.type is "apply_fix", in list order);
 *   signed (recently decided fixes, shown under a quiet line when nothing is waiting).
 * One reviewer name (useReviewer, remembered), a checkbox per fix (all ticked by default), a quiet
 * "Select all / none" toggle, "Approve selected" (the one primary pill) and "Reject selected" (quiet).
 * Each ticked fix is decided on its own through api.decide, one at a time in list order. A failure
 * does not stop the rest. Each row then shows its result as a dot plus a word. After the batch the
 * last returned state is adopted (or the trial refreshed) so the header, clock and stepper update.
 */
import { useMemo, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { Approval, TrialState } from "../../types";
import { SignedStamp } from "../shared/Approvals";
import { Button } from "../shared/Button";
import { useReviewer } from "../shared/useReviewer";

type Decision = "approved" | "rejected";
type Outcome = { kind: Decision } | { kind: "failed"; error: string };

interface Batch {
  decision: Decision;
  items: Approval[];
  done: number;
  running: boolean;
}

const FIX_PREFIX = /^protocol fix:\s*/i;

/** "Protocol fix: Central raters" -> "Central raters" */
export function fixTitle(a: Approval): string {
  const t = a.title.replace(FIX_PREFIX, "").trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : a.title;
}

/** The sentence a fix adds, or another short reason from its evidence, if there is one. */
export function fixDetail(a: Approval): string | null {
  const ev = a.evidence;
  if (typeof ev === "string") return ev.trim() || null;
  if (ev && typeof ev === "object" && !Array.isArray(ev)) {
    const o = ev as Record<string, unknown>;
    for (const k of ["sentence_to_add", "reason", "summary", "why"]) {
      const v = o[k];
      if (typeof v === "string" && v.trim()) return v.trim();
    }
  }
  return null;
}

const plural = (n: number, one: string, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

export function DesignFixReview({ fixes, signed = [] }: { fixes: Approval[]; signed?: Approval[] }) {
  const { trialId, refresh, adopt } = useTrial();
  const [reviewer, setReviewer] = useReviewer();
  const [comment, setComment] = useState("");
  const [unticked, setUnticked] = useState<Set<string>>(() => new Set());
  const [results, setResults] = useState<Record<string, Outcome>>({});
  const [batch, setBatch] = useState<Batch | null>(null);

  const running = batch?.running ?? false;

  // Rows on screen: the batch snapshot (so results stay visible after the fixes leave the pending list),
  // then any pending fix that is not part of it.
  const rows = useMemo(() => {
    if (!batch) return fixes;
    const seen = new Set(batch.items.map((a) => a.id));
    return [...batch.items, ...fixes.filter((a) => !seen.has(a.id))];
  }, [batch, fixes]);

  const open = rows.filter((a) => !results[a.id] || results[a.id].kind === "failed");
  const openIds = new Set(fixes.map((a) => a.id));
  const selectable = open.filter((a) => openIds.has(a.id));
  const selected = selectable.filter((a) => !unticked.has(a.id));
  const allTicked = selected.length === selectable.length;

  const name = reviewer.trim();
  const canSign = !running && !!trialId && name.length > 0 && selected.length > 0;
  const hint = !name ? "Type your name to sign." : selected.length === 0 ? "Tick at least one fix." : null;

  const toggle = (id: string) =>
    setUnticked((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const toggleAll = () =>
    setUnticked(allTicked ? new Set(selectable.map((a) => a.id)) : new Set());

  const run = async (decision: Decision) => {
    if (!canSign || !trialId) return;
    const items = selected.slice();
    setBatch({ decision, items, done: 0, running: true });
    setResults((r) => {
      const n = { ...r };
      for (const a of items) delete n[a.id];
      return n;
    });
    let last: TrialState | null = null;
    for (let i = 0; i < items.length; i += 1) {
      const a = items[i];
      let out: Outcome;
      try {
        const res = await api.decide(trialId, a.id, name, decision, comment.trim());
        if (res?.state) last = res.state;
        out = { kind: decision };
      } catch (e) {
        out = { kind: "failed", error: errorText(e) };
      }
      setResults((r) => ({ ...r, [a.id]: out }));
      setBatch((b) => (b ? { ...b, done: i + 1 } : b));
    }
    setBatch((b) => (b ? { ...b, running: false } : b));
    setUnticked(new Set());
    try {
      if (last) adopt(last);
      else await refresh();
    } catch {
      /* the provider retries refreshes itself */
    }
  };

  const clear = () => {
    setBatch(null);
    setResults({});
  };

  const verb = batch?.decision === "rejected" ? "Rejecting" : "Approving";
  const summary = useMemo(() => {
    if (!batch || batch.running) return null;
    const outs = batch.items.map((a) => results[a.id]).filter(Boolean) as Outcome[];
    const ok = outs.filter((o) => o.kind !== "failed").length;
    const failed = outs.length - ok;
    const done = batch.decision === "approved" ? "approved" : "rejected";
    const retry = batch.items.some((a) => results[a.id]?.kind === "failed" && fixes.some((f) => f.id === a.id));
    if (!failed) return `${plural(ok, "fix", "fixes")} ${done}.`;
    return `${plural(ok, "fix", "fixes")} ${done}, ${failed} failed.${retry ? " Tick the failed ones to try again." : ""}`;
  }, [batch, results, fixes]);

  if (rows.length === 0) {
    return (
      <section className="rv-quietbox" aria-labelledby="rv-fixes-title">
        <h2 className="rv-head__title" id="rv-fixes-title">Design fixes</h2>
        <p className="rv-lede">
          No design fixes waiting. The co-designer will ask again if a protocol edit opens a new gap.
        </p>
        {signed.length > 0 ? (
          <div className="rv-recent">
            <span className="rv-label">Recently signed</span>
            {signed.map((a) => <SignedStamp key={a.id} approval={a} />)}
          </div>
        ) : null}
      </section>
    );
  }
  const idle = selectable.length === 0 && !running;   // every fix in view has been signed

  return (
    <section className="rv-fixes" aria-labelledby="rv-fixes-title">
      <div className="rv-head">
        <h2 className="rv-head__title" id="rv-fixes-title">Review design fixes</h2>
        <span className="rv-head__count">{fixes.length ? `${plural(fixes.length, "fix", "fixes")} waiting` : "All signed"}</span>
      </div>
      <p className="rv-lede">
        The co-designer checked the protocol against the FDA July 2026 guidance and the blinding risk model.
        Approving a fix adds its sentence to the protocol, saves a new version and re-checks it. Each fix is
        signed on its own, in this order.
      </p>

      {idle ? null : (
        <>
          <div className="rv-sign">
            <label className="rv-field" htmlFor="rv-fixes-reviewer">
              <span className="rv-label">Reviewer</span>
              <input id="rv-fixes-reviewer" className="input input--line" value={reviewer} autoComplete="name"
                placeholder="Your name" aria-required="true" disabled={running}
                onChange={(e) => setReviewer(e.target.value)} />
            </label>
            <label className="rv-field" htmlFor="rv-fixes-comment">
              <span className="rv-label">Comment (optional, added to each decision)</span>
              <input id="rv-fixes-comment" className="input input--line" value={comment} disabled={running}
                onChange={(e) => setComment(e.target.value)} />
            </label>
          </div>

          <div className="rv-listbar">
            <span className="rv-label">{selected.length} of {selectable.length} selected</span>
            {selectable.length > 1 ? (
              <button type="button" className="rv-quiet" onClick={toggleAll} disabled={running}>
                {allTicked ? "Select none" : "Select all"}
              </button>
            ) : null}
          </div>
        </>
      )}

      <ul className="rv-list">
        {rows.map((a) => {
          const out = results[a.id];
          const inBatch = batch?.running && batch.items.some((x) => x.id === a.id);
          const pendingHere = openIds.has(a.id);
          const canTick = pendingHere && (!out || out.kind === "failed") && !running;
          const detail = fixDetail(a);
          const id = `rv-fix-${a.id}`;
          return (
            <li key={a.id} className={`rv-item${out && out.kind !== "failed" ? " rv-item--done" : ""}`}>
              {pendingHere && (!out || out.kind === "failed") ? (
                <input id={id} type="checkbox" className="rv-check" checked={!unticked.has(a.id)}
                  disabled={!canTick} onChange={() => toggle(a.id)} />
              ) : (
                <span className="rv-check rv-check--blank" aria-hidden="true" />
              )}
              <div className="rv-item__body">
                <label htmlFor={pendingHere ? id : undefined} className="rv-item__title">{fixTitle(a)}</label>
                {detail ? <p className="rv-item__detail">Adds: {detail}</p> : null}
                {out ? (
                  <OutcomeTag out={out} />
                ) : inBatch ? (
                  <span className="rv-status rv-status--neutral"><span className="rv-status__dot" aria-hidden="true" />Waiting</span>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>

      {idle ? null : (
        <div className="rv-actions">
          <Button variant="filled" disabled={!canSign} onClick={() => run("approved")}>Approve selected</Button>
          <Button variant="outline" disabled={!canSign} onClick={() => run("rejected")}>Reject selected</Button>
          {hint && !running ? <span className="rv-hint">{hint}</span> : null}
        </div>
      )}

      <p className="rv-progress" role="status" aria-live="polite">
        {batch?.running
          ? `${verb} ${Math.min(batch.done + 1, batch.items.length)} of ${batch.items.length}…`
          : summary}
        {summary ? (
          <button type="button" className="rv-quiet rv-progress__clear" onClick={clear}>Clear results</button>
        ) : null}
      </p>
    </section>
  );
}

function OutcomeTag({ out }: { out: Outcome }) {
  if (out.kind === "failed") {
    return (
      <span className="rv-status rv-status--alert">
        <span className="rv-status__dot" aria-hidden="true" />Failed<span className="rv-status__error">{out.error}</span>
      </span>
    );
  }
  return out.kind === "approved" ? (
    <span className="rv-status rv-status--good"><span className="rv-status__dot" aria-hidden="true" />Approved</span>
  ) : (
    <span className="rv-status rv-status--alert"><span className="rv-status__dot" aria-hidden="true" />Rejected</span>
  );
}
