/**
 * FDA blinding report sign-off, read from state.report_status (optional: older backends do not send it).
 * ReportSeal: the signed stamp, "Report signed by <name> · D+90", with a tick. The words carry the meaning;
 *   the tick and the good tint are decoration only.
 * ReportStatusChip: the seal when signed, otherwise a pill with the server's label (nothing for "none").
 * Text helpers (isSigned, signedText, reportSentence) live in reportText.ts.
 */
import type { ReportStatus } from "../../types";
import { StatusPill, dotJoin, formatDay, type Tone } from "../shared";
import { isSigned, signedText } from "./reportText";

function TickGlyph() {
  return (
    <svg viewBox="0 0 10 10" aria-hidden="true" focusable="false">
      <path d="M2 5.2 4.1 7.2 8 2.8" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ReportSeal({ report, className = "" }: { report: ReportStatus; className?: string }) {
  const day = report.signed_day !== null && report.signed_day !== undefined ? formatDay(report.signed_day) : null;
  return (
    <span className={`seal ${className}`.trim()} title={dotJoin("FDA blinding report", signedText(report), day)}>
      <span className="seal__tick"><TickGlyph /></span>
      <span className="seal__text">{dotJoin(signedText(report), day)}</span>
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
  return (
    <StatusPill tone={TONE[report.status] ?? "neutral"} className={className} title={`FDA blinding report: ${report.label}`}>
      {report.label}
    </StatusPill>
  );
}
