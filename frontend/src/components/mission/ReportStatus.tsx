/**
 * FDA blinding report sign-off, read from state.report_status (optional: older backends do not send it).
 * ReportSeal: a small green dot plus "Report signed by <name> · D+90" (design v2). The words carry the meaning;
 *   the dot is decoration only.
 * ReportStatusChip: the seal when signed; a pill only when the report needs attention (waiting for sign-off,
 *   changes requested); otherwise a quiet dot plus the server's label (nothing for "none").
 * Text helpers (isSigned, signedText, reportSentence) live in reportText.ts.
 */
import type { ReportStatus } from "../../types";
import { StatusPill, dotJoin, formatDay, type Tone } from "../shared";
import { isSigned, signedText } from "./reportText";
import "../../styles/module.css";

export function ReportSeal({ report, className = "" }: { report: ReportStatus; className?: string }) {
  const day = report.signed_day !== null && report.signed_day !== undefined ? formatDay(report.signed_day) : null;
  return (
    <span className={`st-status report-seal ${className}`.trim()} title={dotJoin("FDA blinding report", signedText(report), day)}>
      <span className="st-dot st-dot--good" aria-hidden="true" />
      <span className="report-seal__text">{dotJoin(signedText(report), day)}</span>
    </span>
  );
}

const TONE: Record<string, Tone> = {
  collecting: "neutral",
  waiting_for_signoff: "watch",
  changes_requested: "watch",
};

/** Seal when signed; a status pill with the server's label otherwise; nothing when there is no report yet. */
export function ReportStatusChip({ report, className = "" }: { report: ReportStatus | undefined | null; className?: string }) {
  if (!report || report.status === "none") return null;
  if (isSigned(report)) return <ReportSeal report={report} className={className} />;
  if (!report.label) return null;
  const tone = TONE[report.status] ?? "neutral";
  if (tone === "neutral") {
    return (
      <span className={`st-status ${className}`.trim()} title={`FDA blinding report: ${report.label}`}>
        <span className="st-dot st-dot--neutral" aria-hidden="true" />{report.label}
      </span>
    );
  }
  return (
    <StatusPill tone={tone} className={className} title={`FDA blinding report: ${report.label}`}>
      {report.label}
    </StatusPill>
  );
}
