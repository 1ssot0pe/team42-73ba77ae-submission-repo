/**
 * ApprovalSlip, SignedStamp and ApprovalInbox (design.md 8.8). Every decision a human signs looks like a lab slip.
 *
 * ApprovalSlip props: approval (an Approval); onDecided (optional callback with the decided Approval).
 *   Pending: eyebrow MODULE · AGENT · DAY, title, rationale, evidence in <details>, an underlined Reviewer
 *   signature line (required, remembered) plus an optional comment, then Approve (filled) and Reject (outline).
 *   Calls api.decide, then trial.refresh(), and shows a toast. A decided approval renders as a SignedStamp row.
 * SignedStamp props: approval (decided). "SIGNED · APPROVED · DANNY · D+3", "REJECTED", or "AUTO-APPROVED (DEMO)".
 * ApprovalInbox props: module (optional filter, e.g. "predose"); title (default "Approval inbox");
 *   showSigned (default true; recent signed slips under the pending ones); signedLimit (default 6);
 *   moduleTabs (default true when no module is given: filter pills by module).
 *   Refetches whenever trial.tick changes. Heading shows "N waiting for a human".
 */
import { useEffect, useMemo, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { Approval } from "../../types";
import { Button } from "./Button";
import { EmptyState } from "./EmptyState";
import { EvidenceView, hasEvidence } from "./EvidenceView";
import { dotJoin, formatDay, moduleLabel } from "./format";
import { useToast } from "./Toast";
import { useReviewer } from "./useReviewer";

const AUTO_REVIEWER = /auto-approve/i;

/* ------------------------------------------------------------------ stamp */
export function SignedStamp({ approval: a, land = false }: { approval: Approval; land?: boolean }) {
  const auto = AUTO_REVIEWER.test(a.reviewer ?? "");
  const day = formatDay(a.decided_day ?? a.day);
  let text: string;
  let tone: "good" | "alert" | "watch";
  if (auto && a.status === "approved") {
    text = dotJoin("Auto-approved (demo)", day);
    tone = "watch";
  } else if (a.status === "approved") {
    text = dotJoin("Signed", "Approved", a.reviewer, day);
    tone = "good";
  } else {
    text = dotJoin("Signed", "Rejected", a.reviewer, day);
    tone = "alert";
  }
  return (
    <div className="signed">
      <span className="signed__title">{a.title}</span>
      <span className={`stamp stamp--${tone}${land ? " stamp--land" : ""}`} title={a.comment || undefined}>{text}</span>
    </div>
  );
}

/* ------------------------------------------------------------------ slip */
export interface ApprovalSlipProps {
  approval: Approval;
  onDecided?: (a: Approval) => void;
}

export function ApprovalSlip({ approval, onDecided }: ApprovalSlipProps) {
  const { trialId, refresh } = useTrial();
  const toast = useToast();
  const [reviewer, setReviewer] = useReviewer();
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState<"approved" | "rejected" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [decided, setDecided] = useState<Approval | null>(approval.status === "pending" ? null : approval);

  if (decided) return <SignedStamp approval={decided} land />;

  const a = approval;
  const idBase = `slip-${a.id}`;

  const decide = async (decision: "approved" | "rejected") => {
    if (!reviewer.trim()) {
      setError("Type your name first. Every decision is signed.");
      document.getElementById(`${idBase}-reviewer`)?.focus();
      return;
    }
    if (!trialId) return;
    setBusy(decision);
    setError(null);
    try {
      const res = await api.decide(trialId, a.id, reviewer.trim(), decision, comment.trim());
      setDecided(res.approval);
      toast(dotJoin(decision === "approved" ? "Approved" : "Rejected", a.title), decision === "approved" ? "good" : "alert");
      onDecided?.(res.approval);
      await refresh();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <article className="slip glass glass--strong glass--enter" aria-labelledby={`${idBase}-title`}>
      <div className="slip__eyebrow">{dotJoin(moduleLabel(a.module), a.agent, formatDay(a.day))}</div>
      <h3 className="slip__title" id={`${idBase}-title`}>{a.title}</h3>
      {a.rationale ? <p className="slip__rationale">{a.rationale}</p> : null}
      {hasEvidence(a.evidence) ? (
        <details className="slip__evidence">
          <summary>View evidence</summary>
          <EvidenceView evidence={a.evidence} />
        </details>
      ) : null}
      <div className="slip__sign">
        <label className="field" htmlFor={`${idBase}-reviewer`}>
          <span className="field__label">Reviewer</span>
          <input id={`${idBase}-reviewer`} className="input input--line" value={reviewer} autoComplete="name"
            placeholder="Your name" onChange={(e) => setReviewer(e.target.value)} aria-required="true" />
        </label>
        <label className="field" htmlFor={`${idBase}-comment`}>
          <span className="field__label">Comment (optional)</span>
          <input id={`${idBase}-comment`} className="input input--line" value={comment}
            onChange={(e) => setComment(e.target.value)} />
        </label>
      </div>
      {error ? <p className="slip__error" role="alert">{error}</p> : null}
      <div className="slip__actions">
        <Button variant="filled" busy={busy === "approved"} busyLabel="Signing…" disabled={busy !== null}
          onClick={() => decide("approved")}>Approve</Button>
        <Button variant="outline" busy={busy === "rejected"} busyLabel="Signing…" disabled={busy !== null}
          onClick={() => decide("rejected")}>Reject</Button>
      </div>
    </article>
  );
}

/* ------------------------------------------------------------------ inbox */
export interface ApprovalInboxProps {
  module?: string;
  title?: string;
  showSigned?: boolean;
  signedLimit?: number;
  moduleTabs?: boolean;
}

const MODULE_TABS = ["predose", "dosing", "postdose"];

export function ApprovalInbox({ module, title = "Approval inbox", showSigned = true, signedLimit = 6, moduleTabs }: ApprovalInboxProps) {
  const { trialId, tick } = useTrial();
  const [rows, setRows] = useState<Approval[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<string>("all");
  const showTabs = moduleTabs ?? !module;

  useEffect(() => {
    if (!trialId) { setRows(null); return; }
    let live = true;
    api.approvals(trialId, "all")
      .then((r) => { if (live) { setRows(r); setError(null); } })
      .catch((e) => live && setError(errorText(e)));
    return () => { live = false; };
  }, [trialId, tick]);

  const filterMod = module ?? (tab === "all" ? undefined : tab);
  const { pending, signed } = useMemo(() => {
    const xs = (rows ?? []).filter((a) => !filterMod || a.module === filterMod);
    return {
      pending: xs.filter((a) => a.status === "pending"),
      signed: xs.filter((a) => a.status !== "pending").reverse().slice(0, signedLimit),
    };
  }, [rows, filterMod, signedLimit]);

  return (
    <section className="inbox" aria-label={title}>
      <div className="inbox__head">
        <h2 className="t-heading-sm">{title}</h2>
        <span className="inbox__count">{pending.length}</span>
        <span className="inbox__count-label">waiting for a human</span>
      </div>
      {showTabs ? (
        <div className="tabs" role="group" aria-label="Filter by module">
          {["all", ...MODULE_TABS].map((m) => (
            <button key={m} type="button" className="tab" aria-pressed={tab === m} onClick={() => setTab(m)}>
              {m === "all" ? "All modules" : moduleLabel(m)}
            </button>
          ))}
        </div>
      ) : null}
      {error ? <p className="slip__error" role="alert">{error}</p> : null}
      {!trialId ? (
        <EmptyState message="Create a trial to start the agents. Their decisions will wait here for a named human." />
      ) : rows === null ? null : (
        <>
          <div className="inbox__list">
            {pending.length === 0 ? (
              <p className="t-body-sm c-smoke">Nothing to sign right now. The agents will ask when a decision changes the trial.</p>
            ) : (
              pending.map((a) => <ApprovalSlip key={a.id} approval={a} />)
            )}
          </div>
          {showSigned && signed.length > 0 ? (
            <div className="inbox__signed">
              <div className="eyebrow">Recently signed</div>
              {signed.map((a) => <SignedStamp key={a.id} approval={a} />)}
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
