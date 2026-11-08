/**
 * Formatting helpers shared by every component and page. Numbers are shown with units and context.
 * No em dashes anywhere in UI copy.
 */

/** Trial day stamp: -1 -> "D−1", 0 -> "D+0", 23 -> "D+23". */
export function formatDay(day: number | null | undefined): string {
  if (day === null || day === undefined || Number.isNaN(day)) return "D?";
  return day < 0 ? `D−${Math.abs(day)}` : `D+${day}`;
}

/** Number for a readout: integers as-is, otherwise up to `digits` decimals, trailing zeros trimmed. */
export function formatNumber(v: number | string | null | undefined, digits = 2): string {
  if (v === null || v === undefined || v === "") return "n/a";
  if (typeof v === "string") return v;
  if (!Number.isFinite(v)) return "n/a";
  if (Number.isInteger(v)) return v.toLocaleString("en-GB");
  return v.toLocaleString("en-GB", { maximumFractionDigits: digits });
}

/** Human-readable module name. */
export const MODULE_LABELS: Record<string, string> = {
  predose: "Pre-dosing",
  dosing: "Dosing",
  postdose: "Post-dosing",
  master: "Master",
  approvals: "Approvals",
};
export function moduleLabel(m: string | null | undefined): string {
  if (!m) return "";
  return MODULE_LABELS[m] ?? m;
}

/** "sentence_to_add" -> "Sentence to add" */
export function humanise(key: string): string {
  const s = key.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Join parts with the mid-dot separator used in eyebrows: "PREDOSE · AGENT · D−1". */
export function dotJoin(...parts: Array<string | number | null | undefined | false>): string {
  return parts.filter((p) => p !== null && p !== undefined && p !== false && p !== "").join(" · ");
}
