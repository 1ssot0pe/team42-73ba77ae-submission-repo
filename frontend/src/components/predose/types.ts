/**
 * Local shapes for the pre-dosing page and the volunteer portal that types.ts does not spell out.
 * Confirmed against unblind/platform/predose/module.py (handle "recheck" and "apply").
 */
import type { Applicant, ChecklistItem, Risk } from "../../types";

/** Before enrolment: the edit is applied at once (module._apply_edit). */
export interface RecheckApplied {
  ok: true;
  diff: string[];
  risk: Risk;
  checklist: ChecklistItem[];
  version: number;
}

/** After enrolment: the edit becomes a protocol amendment that waits for a named human. */
export interface RecheckPending {
  ok: true;
  pending_approval: string;
  diff: string[];
  message: string;
}

export interface ActionFailed {
  ok: false;
  error: string;
}

export type RecheckResult = RecheckApplied | RecheckPending | ActionFailed;

export function isPending(r: RecheckResult): r is RecheckPending {
  return r.ok === true && "pending_approval" in r;
}

/**
 * What the portal sends as {applicant: {...}}. Keys match the World applicant shape that
 * PreScreeningAgent.screen_one reads. The server assigns id, applied_day and source.
 */
export interface PortalApplicant {
  name: string;
  age: number | null;
  phone: string;
  self_reported_diagnosis: string;
  failed_antidepressants: number | null;
  current_medication: string;
  prior_psychedelic_use: "never" | "once" | "several times";
  months_since_last_psychedelic: number | null;
  history_psychosis: boolean;
  history_bipolar: boolean;
  cardiovascular_condition: boolean;
  pregnant_or_breastfeeding: boolean;
  can_attend_8_visits: boolean;
  consents_to_chatbot_checkins: boolean;
  consents_to_data_sharing: boolean;
  free_text: string;
}

export type ApplyResult = { ok: true; applicant: Applicant } | ActionFailed;

/** recruitment.parked may be a string or an object in older records. */
export function parkedText(parked: unknown): string {
  if (!parked) return "";
  if (typeof parked === "string") return parked;
  if (typeof parked === "object") {
    const o = parked as Record<string, unknown>;
    return String(o.note ?? o.text ?? o.reason ?? JSON.stringify(o));
  }
  return String(parked);
}

/**
 * One row of the predose view's design_history (module.py _design_history): predicted unblinding per
 * protocol version. The first and latest values are stored in the record; versions in between are
 * rescored on the fly from their stored text with the rule-based parser. Nothing is stored.
 */
export interface DesignHistoryRow {
  version: number;
  day: number;
  why: string;
  /** Fix id (FIXES in agents.py) when the version came from an approved fix, else null. */
  fix: string | null;
  u: number | null;
  u_sd: number | null;
  expected_bias_g: number | null;
  band: string | null;
  source: "stored" | "rescored" | "unavailable";
}

/** Short names for the approved fixes, for chart labels. The full title stays in the "why" text. */
export const FIX_SHORT: Record<string, string> = {
  central_raters: "central remote raters",
  blinding_questionnaire: "guess questionnaire",
  expectancy_measure: "expectancy measure",
  alternative_control: "low-dose comparator",
  stratify_prior_use: "stratified by prior use",
};

/** A short label for what changed in a version: the fix name, "initial draft", or the edit reason. */
export function versionChange(row: Pick<DesignHistoryRow, "fix" | "why" | "version">): string {
  if (row.fix && FIX_SHORT[row.fix]) return FIX_SHORT[row.fix];
  if (row.version === 1) return "initial draft";
  const why = (row.why || "").replace(/^.*?approved by [^:]+:\s*/i, "").trim();
  return why ? why.charAt(0).toLowerCase() + why.slice(1) : "edit";
}
