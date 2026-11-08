/**
 * Report stage: the FDA blinding report status (from state.report_status) and the post-dosing approvals,
 * which is where the report is signed off.
 */
import { ApprovalInbox } from "../shared";
import { ReportSeal } from "../mission/ReportStatus";
import { isSigned, reportSentence, signedText } from "../mission/reportText";
import type { TrialState } from "../../types";
import { StatusDot, type DotTone } from "./StatusDot";

const TONE: Record<string, DotTone> = {
  none: "neutral",
  collecting: "neutral",
  waiting_for_signoff: "watch",
  changes_requested: "watch",
  signed: "good",
};

export function ReportPanel({ state }: { state: TrialState }) {
  const rs = state.report_status;
  const closed = state.phase === "closed" || state.phase === "close-out";
  const word = !rs || rs.status === "none" ? "Not started" : isSigned(rs) ? signedText(rs) : rs.label || "In progress";
  const line = closed
    ? reportSentence(state) ?? "The trial is closed. The FDA blinding report is waiting for sign-off."
    : "The FDA blinding report is drafted once follow-up ends. Advance the trial clock to get there.";

  return (
    <div className="ws-stage">
      <section className="ws-section">
        <h2 className="ws-h2">FDA blinding report</h2>
        <p className="ws-line">
          {isSigned(rs) ? <ReportSeal report={rs} /> : <StatusDot tone={TONE[rs?.status ?? "none"] ?? "neutral"}>{word}</StatusDot>}
        </p>
        <p className="ws-lede">{line}</p>
      </section>
      <section className="ws-section">
        <ApprovalInbox module="postdose" title="Sign-off" />
      </section>
    </div>
  );
}
