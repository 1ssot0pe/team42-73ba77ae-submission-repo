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
