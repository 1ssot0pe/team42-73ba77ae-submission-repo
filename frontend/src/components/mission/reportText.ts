/**
 * Text helpers for state.report_status (FDA blinding report sign-off). Optional field: older backends omit it.
 * reportSentence(state): the Mission control header sentence for a closed trial, or null to keep the old copy.
 */
import type { ReportStatus, TrialState } from "../../types";
import { formatDay } from "../shared";

export function isSigned(rs: ReportStatus | undefined | null): rs is ReportStatus & { status: "signed" } {
  return Boolean(rs && rs.status === "signed");
}

export function signedText(rs: ReportStatus): string {
  return rs.signed_by ? `Report signed by ${rs.signed_by}` : "Report signed";
}

function sentence(s: string): string {
  const t = s.trim();
  if (!t) return t;
  const c = t.charAt(0).toUpperCase() + t.slice(1);
  return /[.!?]$/.test(c) ? c : `${c}.`;
}

/** Header sentence once the trial is closed. Null means report_status is missing: keep the old copy. */
export function reportSentence(state: TrialState): string | null {
  const rs = state.report_status;
  if (!rs) return null;
  if (isSigned(rs)) {
    const day = rs.signed_day !== null && rs.signed_day !== undefined ? ` on ${formatDay(rs.signed_day)}` : "";
    return `The trial is closed. The FDA blinding report was signed${rs.signed_by ? ` by ${rs.signed_by}` : ""}${day}.`;
  }
  if (!rs.label) return null;
  const label = sentence(rs.label);
  return /closed/i.test(label) ? label : `The trial is closed. ${label}`;
}
