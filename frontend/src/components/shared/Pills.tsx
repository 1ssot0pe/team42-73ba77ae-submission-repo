/**
 * StatusPill and DecisionPill (design.md 8.15, Section 3 status tints).
 * StatusPill props: tone "good" | "watch" | "alert" | "neutral" | "outline" | "ink" (default neutral);
 *                   size "md" | "lg"; children is the word (colour is never the only signal).
 * DecisionPill props: decision "eligible" | "excluded" | "needs_clinician"; size.
 * SpecimenTag props: label (default "SYNTHETIC"): the hatched-specimen tag for charts and cards.
 * toneForStatus(word) maps common states (approved, pending, missing, high...) to a tone.
 */
import type { ReactNode } from "react";
import type { ScreeningDecision } from "../../types";

export type Tone = "good" | "watch" | "alert" | "neutral" | "outline" | "ink";

export interface StatusPillProps {
  tone?: Tone;
  size?: "md" | "lg";
  children: ReactNode;
  title?: string;
  className?: string;
}

/** Pill in label style with a status tint. */
export function StatusPill({ tone = "neutral", size = "md", children, title, className = "" }: StatusPillProps) {
  return (
    <span className={`pill pill--${tone}${size === "lg" ? " pill--lg" : ""} ${className}`.trim()} title={title}>
      {children}
    </span>
  );
}

const DECISION: Record<ScreeningDecision, { tone: Tone; word: string }> = {
  eligible: { tone: "good", word: "Eligible" },
  needs_clinician: { tone: "watch", word: "Needs clinician" },
  excluded: { tone: "alert", word: "Excluded" },
};

export interface DecisionPillProps {
  decision: ScreeningDecision | string;
  size?: "md" | "lg";
}

/** ELIGIBLE (good), NEEDS CLINICIAN (watch), EXCLUDED (alert). Follow it with the reasons. */
export function DecisionPill({ decision, size = "md" }: DecisionPillProps) {
  const d = DECISION[decision as ScreeningDecision] ?? { tone: "neutral" as Tone, word: decision.replace(/_/g, " ") };
  return <StatusPill tone={d.tone} size={size}>{d.word}</StatusPill>;
}

/** The SYNTHETIC specimen tag (top-right of every chart). */
export function SpecimenTag({ label = "SYNTHETIC" }: { label?: string }) {
  return <StatusPill tone="outline">{label}</StatusPill>;
}

/** Map a status word to a tint. Unknown words are neutral. */
export function toneForStatus(word: string | null | undefined): Tone {
  const w = (word || "").toLowerCase();
  if (["present", "eligible", "approved", "signed", "done", "good", "real", "low", "pass", "ok", "complete", "completed"].includes(w)) return "good";
  if (["pending", "needs_clinician", "needs clinician", "medium", "warn", "watch", "scheduled", "waiting"].includes(w)) return "watch";
  if (["missing", "excluded", "high", "rejected", "alert", "bad", "critical", "drift", "fail", "failed", "missed"].includes(w)) return "alert";
  return "neutral";
}
