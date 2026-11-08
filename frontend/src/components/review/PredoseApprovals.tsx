/**
 * PredoseApprovals (fix round 1, F1). Pre-dosing approvals for the workspace stages.
 *
 * Props: only (optional) "design" | "recruitment" | "screening"; omitted on the full pre-dosing page.
 * Protocol fixes (action.type "apply_fix", raised by the co-designer during design review) are signed
 * together in DesignFixReview on the design slice and the full page. Every other pre-dosing approval
 * (the clinician shortlist, protocol amendments) stays a separate ApprovalSlip with a plain heading.
 * When nothing in this slice is waiting, a quiet line and a short list of recent decisions show instead.
 * Refetches whenever trial.tick changes.
 */
import { useEffect, useMemo, useState } from "react";
import { api, errorText } from "../../api";
import { useTrial } from "../../trial";
import type { Approval } from "../../types";
import { ApprovalSlip, ExpiredStamp, SignedStamp } from "../shared/Approvals";
import { DesignFixReview } from "./DesignFixReview";
import "../../styles/review.css";

type Only = "design" | "recruitment" | "screening";

const kindOf = (a: Approval) => String(a.action?.type ?? "");
const isFix = (a: Approval) => kindOf(a) === "apply_fix";
const isShortlist = (a: Approval) => kindOf(a) === "shortlist";
const isExpired = (a: Approval) => a.status === "expired" || /^nobody\b/i.test(a.reviewer ?? "");

const COPY: Record<string, { heading: string; text: string }> = {
  shortlist: {
    heading: "Clinician shortlist",
    text:
      "The pre-screening agent has a shortlist of eligible applicants and a list it flagged for a clinician. " +
      "Signing confirms the shortlist and enrols those applicants. Rejecting enrols nobody, and the trial waits " +
      "until a clinician approves a new shortlist.",
  },
  amendment: {
    heading: "Protocol amendment",
    text:
      "Participants are already enrolled, so this change to the protocol is an amendment. Signing saves a new " +
      "protocol version, re-checks it and tells the other modules.",
  },
  other: {
    heading: "Other approval",
    text: "An agent needs a named human before it acts. Signing records your name against the decision.",
  },
};

const copyFor = (a: Approval) =>
  isShortlist(a) ? COPY.shortlist : kindOf(a).startsWith("amendment") ? COPY.amendment : COPY.other;

export function PredoseApprovals({ only }: { only?: Only }) {
  const { trialId, tick } = useTrial();
  const [rows, setRows] = useState<Approval[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!trialId) { setRows(null); return; }
    let live = true;
    api.approvals(trialId, "all")
      .then((r) => { if (live) { setRows(r); setError(null); } })
      .catch((e) => live && setError(errorText(e)));
    return () => { live = false; };
  }, [trialId, tick]);

  const showFixes = only === undefined || only === "design";
  const showOthers = only !== "recruitment";

  const { fixes, others, signedFixes, signedOthers, expired } = useMemo(() => {
    const xs = (rows ?? []).filter((a) => a.module === "predose");
    const pending = xs.filter((a) => a.status === "pending");
    const decided = xs.filter((a) => a.status !== "pending");
    return {
      fixes: showFixes ? pending.filter(isFix) : [],
      others: showOthers ? pending.filter((a) => !isFix(a)) : [],
      signedFixes: decided.filter((a) => !isExpired(a) && isFix(a)).reverse().slice(0, 5),
      signedOthers: decided.filter((a) => !isExpired(a) && !isFix(a)).reverse().slice(0, 5),
      expired: decided.filter((a) => isExpired(a) && isFix(a) && showFixes).reverse(),
    };
  }, [rows, showFixes, showOthers]);

  if (!trialId) return null;

  return (
    <div className="rv">
      {error ? <p className="rv-error" role="alert">{error}</p> : null}

      {showFixes && rows !== null ? <DesignFixReview fixes={fixes} signed={signedFixes} /> : null}

      {others.map((a) => {
        const c = copyFor(a);
        return (
          <section key={a.id} className="rv-other" aria-labelledby={`rv-other-${a.id}`}>
            <div className="rv-head">
              <h2 className="rv-head__title" id={`rv-other-${a.id}`}>{c.heading}</h2>
              <span className="rv-status rv-status--watch"><span className="rv-status__dot" aria-hidden="true" />Needs sign-off</span>
            </div>
            <p className="rv-lede">{c.text}</p>
            <ApprovalSlip approval={a} quiet={showFixes} />
          </section>
        );
      })}

      {rows !== null && only === "screening" && others.length === 0 ? (
        <section className="rv-quietbox" aria-labelledby="rv-shortlist-none">
          <h2 className="rv-head__title" id="rv-shortlist-none">Clinician shortlist</h2>
          <p className="rv-lede">Nothing to sign here yet. The clinician shortlist will appear once screening has run.</p>
          {signedOthers.length > 0 ? (
            <div className="rv-recent">
              <span className="rv-label">Recently signed</span>
              {signedOthers.map((a) => <SignedStamp key={a.id} approval={a} />)}
            </div>
          ) : null}
        </section>
      ) : null}

      {expired.length > 0 ? (
        <div className="rv-recent rv-recent--expired">
          <span className="rv-label">Expired at enrolment</span>
          <p className="rv-lede">
            Dosing started before {expired.length === 1 ? "this fix was" : "these fixes were"} signed, so{" "}
            {expired.length === 1 ? "it was" : "they were"} not applied. Edit the protocol to propose an amendment instead.
          </p>
          {expired.map((a) => <ExpiredStamp key={a.id} approval={a} />)}
        </div>
      ) : null}
    </div>
  );
}
