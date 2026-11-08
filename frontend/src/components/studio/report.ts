/**
 * Defensive readers for the UNBLIND evidence report (unblind/pipeline.py Report.to_json).
 * The shape is not fixed in types.ts, so every reader tolerates missing or oddly typed keys.
 */
import type { EvidenceReport } from "../../types";

export type Obj = Record<string, unknown>;

export function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
export function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}
export function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
export function fmt(v: number | null, digits = 2): string {
  if (v === null) return "n/a";
  // Unicode minus so negative numbers line up in tabular figures
  return v.toFixed(digits).replace(/^-/, "−");
}

export interface FactRow {
  key: string;
  label: string;
  value: string;
  status: string;
  quote: string;
  note: string;
  audit: string;
  agent: string;
  sourceId: string;
  sourceUrl: string;
  sourceTitle: string;
}

export interface Effect {
  reported: number | null;
  reportedLo: number | null;
  reportedHi: number | null;
  reportedStatus: string;
  adjusted: number | null;
  adjustedLo: number | null;
  adjustedHi: number | null;
  bias: number | null;
  extrapolated: boolean;
  /** correction.u_status: whether the unblinding u behind the adjustment was observed or imputed. */
  uStatus: string;
  /** facts.se_g, the standard error the reported interval is built from (g ± 1.96·se). */
  se: number | null;
  seStatus: string;
}

export interface Blinding {
  u: number | null;
  uSd: number | null;
  status: string;
  observed: boolean;
  word: string;
  tone: "good" | "watch" | "alert" | "neutral";
  note: string;
}

export interface Fix {
  change: string;
  reduction: number | null;
  before: number | null;
  after: number | null;
  /** counterfactuals[].feasibility_weight, 0 to 1. */
  feasibility: number | null;
  /** counterfactuals[].score = reduction × feasibility; the pipeline ranks by it. */
  score: number | null;
}

export interface TraceRow {
  agent: string;
  action: string;
  detail: string;
  level: string;
}

const LABELS: Record<string, string> = {
  primary_endpoint: "Primary endpoint",
  enrollment: "Enrolment",
  effect: "Reported effect",
  comparator_type: "Comparator",
  rater_placement: "Raters",
  prior_exposure: "Prior psychedelic use",
  blinding_assessment_planned: "Blinding assessment planned",
  guess_acc_participants: "Participant guess accuracy",
  guess_acc_raters: "Rater guess accuracy",
  arm_ns: "Arm sizes",
  g: "Standardised effect (g)",
  se_g: "Standard error of g",
  u: "Unblinding",
  u_sd: "Unblinding uncertainty",
};

export function humanise(key: string): string {
  if (LABELS[key]) return LABELS[key];
  const s = key.replace(/[_-]+/g, " ").trim();
  return s ? s[0].toUpperCase() + s.slice(1) : key;
}

export function valueText(v: unknown): string {
  if (v === null || v === undefined || v === "") return "Not found";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return String(v);
  if (typeof v === "string") return v.replace(/_/g, " ");
  if (Array.isArray(v)) return v.map(valueText).join(", ");
  if (isObj(v)) {
    if ("est" in v) {
      const lo = num(v.lo), hi = num(v.hi);
      const kind = str(v.kind) === "md" ? "Mean difference " : "";
      return `${kind}${valueText(v.est)}${lo !== null && hi !== null ? ` (${lo} to ${hi})` : ""}`;
    }
    if ("scale" in v || "week" in v) {
      const parts = [str(v.scale), num(v.week) !== null ? `week ${v.week}` : ""].filter(Boolean);
      return parts.join(", ") || str(v.measure) || "Not found";
    }
    return Object.entries(v).map(([k, x]) => `${humanise(k)}: ${valueText(x)}`).join("; ");
  }
  return String(v);
}

export function title(r: EvidenceReport, fallback = ""): string {
  return str(r.title) || str(r.nct) || fallback;
}

export function facts(r: EvidenceReport): FactRow[] {
  const f = isObj(r.facts) ? r.facts : {};
  const sources = isObj(r.sources) ? r.sources : {};
  const out: FactRow[] = [];
  for (const [key, raw] of Object.entries(f)) {
    if (!isObj(raw)) continue;
    const sourceId = str(raw.source_id);
    const src = isObj(sources[sourceId]) ? (sources[sourceId] as Obj) : {};
    out.push({
      key,
      label: humanise(str(raw.name) || key),
      value: valueText(raw.value),
      status: str(raw.status) || "unknown",
      quote: str(raw.quote),
      note: str(raw.note),
      audit: str(raw.audit),
      agent: str(raw.agent),
      sourceId,
      sourceUrl: str(src.url),
      sourceTitle: str(src.title),
    });
  }
  return out;
}

function fact(r: EvidenceReport, key: string): Obj | null {
  const f = isObj(r.facts) ? r.facts : {};
  return isObj(f[key]) ? (f[key] as Obj) : null;
}

export function effect(r: EvidenceReport): Effect | null {
  const g = fact(r, "g");
  const seFact = fact(r, "se_g");
  const se = num(seFact?.value);
  const c = isObj(r.correction) ? r.correction : null;
  const reported = num(g?.value);
  if (reported === null && !c) return null;
  return {
    reported,
    reportedLo: reported !== null && se !== null ? reported - 1.96 * se : null,
    reportedHi: reported !== null && se !== null ? reported + 1.96 * se : null,
    reportedStatus: str(g?.status),
    adjusted: num(c?.corrected),
    adjustedLo: num(c?.lo),
    adjustedHi: num(c?.hi),
    bias: num(c?.bias),
    extrapolated: c?.extrapolated === true,
    uStatus: str(c?.u_status),
    se,
    seStatus: str(seFact?.status),
  };
}

/**
 * Word boundaries for the unblinding u, exactly as the verdict uses them (u < 0.25, u < 0.55, else).
 * The blinding meter draws these cut-offs so the verdict has visible boundaries.
 */
export const BLINDING_BANDS: { word: string; tone: Blinding["tone"]; from: number; below: number }[] = [
  { word: "Blinding largely held", tone: "good", from: 0, below: 0.25 },
  { word: "Partly unblinded", tone: "watch", from: 0.25, below: 0.55 },
  { word: "Largely unblinded", tone: "alert", from: 0.55, below: Infinity },
];

export function bandWord(v: number): string {
  return (BLINDING_BANDS.find((b) => v < b.below) ?? BLINDING_BANDS[BLINDING_BANDS.length - 1]).word;
}

/** Guess accuracy facts (0 to 1) when reported, else null. */
export function guessAccuracy(r: EvidenceReport, who: "participants" | "raters"): number | null {
  const f = fact(r, `guess_acc_${who}`);
  return f && str(f.status) !== "unknown" ? num(f.value) : null;
}

/**
 * report.status in sentence case for a status line: "AWAITING HUMAN SIGN-OFF: instrument reading, not a verdict"
 * becomes label "Awaiting human sign-off" and detail "instrument reading, not a verdict".
 */
export function signOff(r: EvidenceReport): { label: string; detail: string } | null {
  const raw = str(r.status).trim();
  if (!raw) return null;
  const [head, ...rest] = raw.split(":");
  const h = head.trim().toLowerCase();
  return { label: h ? h[0].toUpperCase() + h.slice(1) : raw, detail: rest.join(":").trim() };
}

/** fit_primary summary used in footnotes: number of calibration trials and tau². */
export function fitPrimary(r: EvidenceReport): { k: number | null; tau2: number | null; slope: number | null } {
  const f = isObj(r.fit_primary) ? r.fit_primary : {};
  const u = isObj(f.u) ? (f.u as Obj) : {};
  return { k: num(f.k), tau2: num(f.tau2), slope: num(u.est) };
}

export function blinding(r: EvidenceReport): Blinding | null {
  const u = fact(r, "u");
  const value = num(u?.value);
  if (!u || value === null) return null;
  const status = str(u.status);
  const observed = status === "derived" || status === "observed";
  const band = BLINDING_BANDS.find((b) => value < b.below) ?? BLINDING_BANDS[BLINDING_BANDS.length - 1];
  const { word, tone } = band;
  return { u: value, uSd: num(fact(r, "u_sd")?.value), status, observed, word, tone, note: str(u.note) };
}

export function fixes(r: EvidenceReport): Fix[] {
  const list = Array.isArray(r.counterfactuals) ? r.counterfactuals : [];
  return list.filter(isObj).map((c) => ({
    change: str(c.change) || "Unnamed change",
    reduction: num(c.bias_reduction),
    before: num(c.expected_bias_before),
    after: num(c.expected_bias_after),
    feasibility: num(c.feasibility_weight ?? c.feasibility),
    score: num(c.score),
  }));
}

export function trace(r: EvidenceReport): TraceRow[] {
  const list = Array.isArray(r.trace) ? r.trace : [];
  return list.filter(isObj).map((e) => ({
    agent: str(e.agent),
    action: str(e.action),
    detail: str(e.detail),
    level: str(e.level) || "info",
  }));
}

export function strings(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string" && x.trim() !== "") : [];
}

export function isSynthetic(r: EvidenceReport): boolean {
  return /synthetic/i.test(str(r.calibration));
}

/** Plain-text protocol outline seeded from the report, for a new trial's Draft stage. */
export function draftOutline(r: EvidenceReport, input: string): string {
  const drugs = strings(r.drug);
  const v = (k: string) => {
    const f = fact(r, k);
    return f && f.value !== null && f.value !== undefined && f.value !== "" ? valueText(f.value) : "";
  };
  const name = title(r, input);
  const fx = fixes(r);
  const lines = [
    `Protocol outline informed by ${name}${str(r.nct) && str(r.nct) !== name ? ` (${str(r.nct)})` : ""}`,
    "",
    "Drug",
    drugs.length ? drugs.join(", ") : "To be decided",
    "",
    "Comparator",
    v("comparator_type") || "To be decided. Consider an active placebo or a low dose of the same drug.",
    "",
    "Raters",
    v("rater_placement") || "Central, remote raters who are blind to allocation.",
    "",
    "Population",
    v("prior_exposure") ? `Prior psychedelic use in the source trial: ${v("prior_exposure")}` : "To be decided.",
    "",
    "Primary outcome",
    v("primary_endpoint") || "To be decided.",
    "",
    "Blinding plan",
    "Ask participants and raters to guess allocation at each primary timepoint and report the results.",
    "",
    "Design fixes from the evidence studio, highest ranked first",
    ...(fx.length ? fx.map((f) => `- ${f.change}`) : ["- No ranked fixes were returned."]),
  ];
  return lines.join("\n");
}

/** Acronyms that stay in capitals even though they are four letters or more. */
const ACRONYMS = new Set([
  "NCT", "FDA", "EMA", "DOI", "MADRS", "HAMD", "HAM", "PTSD", "MDMA", "CAPS", "QIDS", "BDI", "PCL",
  "CONSORT", "NICE", "NIH", "SSRI", "SNRI", "ANCOVA", "MMRM", "LOCF", "RCT", "ITT", "JAMA", "NEJM",
  "BMJ", "PLOS", "GRADE", "PRISMA", "SPIRIT", "UNBLIND", "OCD", "GAD", "TRD", "MDD", "AUD", "LSD",
  "DMT", "API", "JSON", "CSV", "PDF", "HTML", "PMID", "PMC", "ISRCTN", "EUCTR",
]);
/** Short shouty words that the vowel test below would miss. */
const SHOUTY = new Set(["ONLY", "NOTE", "REAL", "DEMO", "TEST", "STUB", "MOCK", "FAKE", "WARN", "TRUE", "FALSE"]);

/**
 * Display text for warnings, notes and trace lines: turns shouty all-caps words ("SYNTHETIC")
 * into sentence case and leaves acronyms (FDA, NCT, MADRS, DOI) alone. A word counts as shouty when
 * it has four or more letters, is not a known acronym, and reads like a word (two or more vowels).
 */
export function tidy(text: string): string {
  return text.replace(/\b[A-Z]{4,}\b/g, (w, offset: number, all: string) => {
    if (ACRONYMS.has(w)) return w;
    const vowels = (w.match(/[AEIOU]/g) ?? []).length;
    if (vowels < 2 && !SHOUTY.has(w)) return w;
    const before = all.slice(0, offset).trimEnd();
    const startsSentence = before === "" || /[.!?:]$/.test(before);
    const lower = w.toLowerCase();
    return startsSentence ? lower[0].toUpperCase() + lower.slice(1) : lower;
  });
}
