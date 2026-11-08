/**
 * Shapes returned by the UNBLIND API (backend/main.py) and the shared TrialRecord sections
 * (plan.md Section 3, MODULE_CONTRACT.md). The API strips every key that starts with "_".
 * Record sections owned by dosing and postdose are typed loosely because their owners may extend them.
 */

/* ------------------------------------------------------------------ basics */
export type ModuleId = "predose" | "dosing" | "postdose";
/** Modules plus the senders that appear in events and messages. */
export type AgentModule = ModuleId | "master" | "approvals" | string;
export type Phase = "design" | "recruitment" | "dosing" | "follow-up" | "close-out" | "closed";
export const PHASES: Phase[] = ["design", "recruitment", "dosing", "follow-up", "close-out", "closed"];
export type ModuleStatus = "real" | "stub";
export type Json = string | number | boolean | null | Json[] | { [k: string]: Json };

/* ------------------------------------------------------------------ meta */
export interface Health {
  ok: boolean;
  gemini: boolean;
  trials: string[];
}

export interface Bottleneck {
  id: string;
  module: ModuleId | string;
  title: string;
  number: string;
  source: string;
  url: string;
  how_we_tackle: string;
  metric: string;
}
export interface BottlenecksFile {
  bottlenecks: Bottleneck[];
}

export interface ProtocolSummary {
  name: string;
  title: string;
}
export interface ProtocolText {
  name: string;
  text: string;
}

/* ------------------------------------------------------------------ trial state (Master.state()) */
export interface TrialCounts {
  applicants: number;
  enrolled: number;
  schedule: number;
  checkins: number;
  alerts: number;
  events: number;
  messages: number;
}

export interface TrialState {
  trial_id: string;
  synthetic: boolean;
  /** -1 during setup, then 1 to close_day */
  day: number;
  phase: Phase;
  close_day: number;
  primary_lock_day: number | null;
  module_status: Record<string, ModuleStatus | string>;
  /** Why the clock cannot advance, or null */
  blocked: string | null;
  counts: TrialCounts;
  pending_approvals: number;
  auto_approve: boolean;
  gemini: boolean;
  /** FDA blinding report sign-off. Optional: older backends do not send it. */
  report_status?: ReportStatus;
  /** The simulator's planted drift (synthetic truth, display only). Null when there is no drift or no simulator. */
  simulated_truth?: SimulatedTruth | null;
}

export interface SimulatedTruth {
  synthetic: boolean;
  label: "simulated";
  drift_site: string;
  drift_onset_day: number;
}

export type ReportStatusKind = "none" | "collecting" | "waiting_for_signoff" | "changes_requested" | "signed";

export interface ReportStatus {
  status: ReportStatusKind;
  signed_by: string | null;
  signed_day: number | null;
  /** plain-language sentence from the server, e.g. "Waiting for sign-off" */
  label: string;
}

export interface CreateTrialBody {
  protocol_text?: string;
  example?: string;
  seed?: number;
  n_applicants?: number;
  auto_approve?: boolean;
}

export interface StepResult {
  advanced: boolean;
  blocked?: string;
  day: number;
  phase?: Phase;
  state: TrialState;
}

/* ------------------------------------------------------------------ events, approvals, messages */
export type EventLevel = "info" | "decision" | "warn" | "human";

export interface TrialEvent {
  /** position in rec.events; use as `since` for incremental fetches */
  idx: number;
  day: number;
  /** unix seconds */
  t: number;
  agent: string;
  module: AgentModule;
  level: EventLevel;
  text: string;
  data: unknown;
}

export interface EventsQuery {
  since?: number;
  module?: string;
  level?: EventLevel | "";
  limit?: number;
}

/** "expired": a pre-dosing fix that was still pending when dosing started (event "expired: dosing started"). */
export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";

export interface Approval {
  id: string;
  day: number;
  agent: string;
  module: AgentModule;
  title: string;
  rationale: string;
  /** what will happen if approved, e.g. {type: "apply_fix", fix: "central_raters"} */
  action: { type?: string; [k: string]: unknown };
  /** free-form: strings, lists, or objects such as {sentence_to_add}, {diff: string[]}, {flagged: Applicant[]} */
  evidence: unknown;
  status: ApprovalStatus;
  reviewer: string | null;
  comment: string;
  decided_day: number | null;
  auto_policy: string | null;
}

export interface DecideResult {
  approval: Approval;
  state: TrialState;
}

export interface Message {
  id: string;
  day: number;
  from: string;
  to: string;
  kind: string;
  payload: unknown;
  text: string;
  delivered: boolean;
  routed_by?: string;
}

export interface MessageEdge {
  from: string;
  to: string;
  count: number;
}

export interface MessagesResponse {
  edges: MessageEdge[];
  recent: Message[];
}

/* ------------------------------------------------------------------ KPIs */
export interface Kpi {
  label: string;
  value: number | string | null;
  baseline?: number | string | null;
  unit?: string;
  note?: string;
  bottleneck_id?: string | null;
}
/** GET /kpis returns {module: Kpi[]} */
export type KpiMap = Record<string, Kpi[]>;

/* ------------------------------------------------------------------ view model (MODULE_CONTRACT.md) */
export type CardTone = "info" | "warn" | "good" | "bad";

export interface ViewCard {
  title: string;
  body: string;
  tone?: CardTone;
}

export interface ViewChartSeries {
  key: string;
  label: string;
}

export interface ViewChart {
  title: string;
  /** key of the x value inside each data row */
  x: string;
  series: ViewChartSeries[];
  data: Array<Record<string, number | string | null>>;
  /** optional extras a module may add */
  y_label?: string;
  threshold?: number;
}

export type Cell = string | number | boolean | null;

export interface ViewTable {
  title: string;
  columns: string[];
  rows: Cell[][];
}

export interface ViewFormField {
  name: string;
  label: string;
  type: "text" | "number" | "select" | "textarea" | "checkbox" | string;
  options?: string[];
  placeholder?: string;
  default?: string | number | boolean;
}

export interface ViewForm {
  id: string;
  title: string;
  action: string;
  fields: ViewFormField[];
  submit_label?: string;
}

export interface ViewModel {
  module: string;
  title: string;
  /** added by the master: "real" or "stub" */
  status?: ModuleStatus | string;
  kpis?: Kpi[];
  cards?: ViewCard[];
  charts?: ViewChart[];
  tables?: ViewTable[];
  forms?: ViewForm[];
  error?: string;
}

/** POST /modules/{m}/actions/{action} */
export interface ActionResult<R = ModuleActionResult> {
  result: R;
  state: TrialState;
}
export interface ModuleActionResult {
  ok?: boolean;
  message?: string;
  error?: string;
  [k: string]: unknown;
}

/* ------------------------------------------------------------------ record sections: predose */
export interface Protocol {
  title?: string;
  drug?: string;
  indication?: string;
  comparator?: string;
  rater_model?: string;
  prior_use_policy?: string;
  sites?: string[];
  n_target?: number;
  primary_endpoint?: { scale: string; week: number };
  eligibility?: { inclusion: string[]; exclusion: string[] };
  has_blinding_questionnaire?: boolean;
  has_expectancy_measure?: boolean;
  design_flags?: Record<string, unknown>;
  /** field -> quote from the protocol text */
  evidence?: Record<string, string>;
  text: string;
}

export interface ProtocolVersion {
  version: number;
  day: number;
  digest: string;
  why: string;
  changes: string[];
  text: string;
}

export type RiskBand = "low" | "medium" | "high";

export interface Risk {
  u: number;
  u_sd: number;
  expected_bias_g: number;
  band: RiskBand;
  calibration: string;
  design_model: string;
}

export interface ChecklistItem {
  id: string;
  item: string;
  present: boolean;
  evidence: string;
  note: string;
}

export interface DesignReview {
  risk: Risk;
  checklist: ChecklistItem[];
  model_fixes: unknown[];
  proposed_fixes: string[];
  rejected_fixes?: string[];
  blinding_section_md: string;
  baseline_risk: Risk;
  baseline_checklist_ok: number;
  /** Frozen copy of risk taken when enrolment completed. Optional: absent before enrolment and on older backends. */
  risk_at_enrolment?: Risk | null;
  /** Set when the primary endpoint week falls outside the 90-day simulation window. Optional. */
  window_note?: string | null;
}

export interface RecruitmentAd {
  id: string;
  text: string;
  reading_ease: number;
  checks: Record<string, boolean>;
}

export interface Funnel {
  applied: number;
  auto_eligible: number;
  auto_excluded: number;
  needs_clinician: number;
  enrolled: number;
}

export interface FairnessRow {
  group: string;
  n: number;
  eligible: number;
  rate_pct: number;
}
export interface FairnessGroup {
  by: string;
  rows: FairnessRow[];
  spread_pts: number;
  flag: boolean;
  driver: string | null;
  note: string;
}

export interface Recruitment {
  ads: RecruitmentAd[];
  channels: unknown[];
  parked: unknown;
  funnel: Funnel;
  fairness: FairnessGroup[];
  strata: Record<string, number>;
}

export type ScreeningDecision = "eligible" | "excluded" | "needs_clinician";

export interface Screening {
  decision: ScreeningDecision;
  reasons: string[];
  criteria_hit: string[];
  evidence: Array<{ criterion: string; quote: string }>;
}

export interface Applicant {
  id: string;
  name: string;
  age: number;
  phone?: string;
  country?: string;
  nearest_site?: string;
  self_reported_diagnosis?: string;
  failed_antidepressants?: number;
  current_medication?: string;
  history_psychosis?: boolean;
  history_bipolar?: boolean;
  cardiovascular_condition?: boolean;
  pregnant_or_breastfeeding?: boolean;
  prior_psychedelic_use?: string;
  months_since_last_psychedelic?: number | null;
  can_attend_8_visits?: boolean;
  consents_to_chatbot_checkins?: boolean;
  consents_to_data_sharing?: boolean;
  free_text?: string;
  applied_day?: number;
  screening: Screening;
  [k: string]: unknown;
}

export interface Enrolled {
  id: string;
  name: string;
  site: string;
  stratum: string;
  prior_psychedelic_use: string;
  dosing_day: number;
  consents: { checkins: boolean; data_sharing: boolean; [k: string]: boolean };
}

export interface Instrument {
  id: string;
  who: string;
  questions: string[];
  /** Integer days relative to dosing day (-1, 0, 1, 7, ...). Older plans hold label strings here. */
  timepoints_days: Array<number | string>;
  /** Human labels parallel to timepoints_days ("before randomisation", "week 1"). Optional. */
  timepoints?: string[];
  purpose: string;
}

export interface MeasurementPlan {
  standard: "UNBLIND-BLIND-1" | string;
  instruments: Instrument[];
  primary_week: number;
}

export type ScheduleKind =
  | "dosing_session"
  | "monitor_debrief"
  | "participant_checkin"
  | "rater_assessment"
  | "followup"
  | "research_question";

export interface ScheduleItem {
  id: string;
  participant: string;
  site: string;
  day: number;
  kind: ScheduleKind;
  owner: "dosing" | "postdose" | string;
  instrument: string;
  status: string;
  rater_id?: string;
  visit_week?: number;
}

/* ------------------------------------------------------------------ record sections: dosing (contract rows) */
export interface Checkin {
  participant: string;
  site: string;
  day: number;
  who: "participant" | "rater" | "monitor";
  rater_id?: string;
  guess: "drug" | "control" | "dont_know";
  confidence: number;
  expectancy?: number;
  channel?: "text" | "voice";
  [k: string]: unknown;
}

export interface Outcome {
  participant: string;
  site: string;
  day: number;
  visit_week: number;
  madrs: number;
  rater_id: string;
  rater_guess: string;
  patient_guess: string;
  [k: string]: unknown;
}

export interface BlindingMetric {
  day: number;
  who: string;
  by: "overall" | "site" | "rater";
  group: string;
  n: number;
  accuracy: number | null;
  accuracy_lo: number | null;
  accuracy_hi: number | null;
  u: number | null;
  bang_drug: number | null;
  suppressed: boolean;
  [k: string]: unknown;
}

export interface Alert {
  id: string;
  day: number;
  module: string;
  severity: "info" | "warn" | "critical";
  title: string;
  explanation: string;
  evidence: unknown;
  approval_id: string | null;
  [k: string]: unknown;
}

/* ------------------------------------------------------------------ GET /record */
/** Every section name the API allows in ?sections= */
export type RecordSectionName =
  | "protocol" | "protocol_versions" | "design_review" | "recruitment" | "applicants" | "enrolled"
  | "measurement_plan" | "schedule" | "sessions" | "checkins" | "debriefs" | "outcomes" | "blinding_metrics"
  | "alerts" | "actions" | "missing_data" | "literature" | "followups" | "research_questions" | "exports"
  | "report" | "approvals" | "kpis";

export interface RecordSections {
  protocol: Protocol | null;
  protocol_versions: ProtocolVersion[];
  design_review: DesignReview | null;
  recruitment: Recruitment | null;
  applicants: Applicant[];
  enrolled: Enrolled[];
  measurement_plan: MeasurementPlan | null;
  schedule: ScheduleItem[];
  sessions: Array<Record<string, unknown>>;
  checkins: Checkin[];
  debriefs: Array<Record<string, unknown>>;
  outcomes: Outcome[];
  blinding_metrics: BlindingMetric[];
  alerts: Alert[];
  actions: Array<Record<string, unknown>>;
  missing_data: Array<Record<string, unknown>>;
  literature: Array<Record<string, unknown>>;
  followups: Array<Record<string, unknown>>;
  research_questions: Array<Record<string, unknown>>;
  exports: Array<Record<string, unknown>>;
  report: Record<string, unknown> | null;
  approvals: Approval[];
  kpis: unknown;
}

/** POST /api/evidence/run returns the existing UNBLIND pipeline report; shape not fixed here. */
export type EvidenceReport = Record<string, unknown>;
