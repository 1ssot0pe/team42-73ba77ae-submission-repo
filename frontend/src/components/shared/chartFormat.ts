/**
 * chartFormat: number and axis helpers shared by every chart (docs/visuals-spec.md 4.4).
 * Unicode minus for negatives, "to" for intervals, "D47" day ticks, nice domains, and the Wilson interval
 * for counts that arrive without bounds (rolling windows). Where the record already carries accuracy_lo/hi,
 * use those instead of wilson().
 */

/** Mirrors unblind/platform/dosing/stats.py:41 (WILSON_MIN_N). No interval is drawn below this n. */
export const WILSON_MIN_N = 8;
/** Vault release rule: a group whose window holds fewer than 5 guesses is suppressed. */
export const VAULT_MIN_N = 5;
/** Rolling accuracy uses the last 3 released vault batches (dosing stats). */
export const ROLLING_BATCHES = 3;

const MINUS = "−";
const Z95 = 1.959964;

const finite = (v: number | null | undefined): v is number => typeof v === "number" && Number.isFinite(v);

/** Replace a leading hyphen-minus with the Unicode minus sign. */
function uminus(s: string): string {
  return s.startsWith("-") ? MINUS + s.slice(1) : s;
}

/** 0.6875 -> "69%" (digits 0) or "68.8%" (digits 1). Null or NaN -> "n/a". */
export function formatPct(p: number | null, digits: 0 | 1 = 0): string {
  if (!finite(p)) return "n/a";
  const v = p * 100;
  // Avoid "-0%".
  const s = (Math.abs(v) < 0.5 / 10 ** digits ? 0 : v).toFixed(digits);
  return `${uminus(s)}%`;
}

/** Signed number with the Unicode minus: -0.07 -> "−0.07". No plus sign for positives. */
export function formatSigned(v: number | null, digits = 2): string {
  if (!finite(v)) return "n/a";
  const s = v.toFixed(digits);
  // "-0.00" prints as "0.00".
  if (Number(s) === 0) return (0).toFixed(digits);
  return uminus(s);
}

/**
 * Interval in words: formatInterval(0.29, 0.72) -> "0.29 to 0.72"; with unit "%" the inputs are proportions,
 * formatInterval(0.8, 1, "%") -> "80% to 100%"; with unit "g", "0.29 to 0.72 g".
 */
export function formatInterval(lo: number | null, hi: number | null, unit: "%" | "g" | "" = ""): string {
  if (!finite(lo) || !finite(hi)) return "n/a";
  if (unit === "%") return `${formatPct(lo)} to ${formatPct(hi)}`;
  const body = `${formatSigned(lo)} to ${formatSigned(hi)}`;
  return unit === "g" ? `${body} g` : body;
}

/** Estimate with bracketed interval: "0.50 [0.29, 0.72]", "−0.07 [−0.75, 0.61]". */
export function formatBracket(est: number, lo: number, hi: number, digits = 2): string {
  return `${formatSigned(est, digits)} [${formatSigned(lo, digits)}, ${formatSigned(hi, digits)}]`;
}

/** Trial day tick: 47 -> "D47". */
export function formatDayTick(d: number): string {
  return finite(d) ? `D${uminus(String(Math.round(d)))}` : "";
}

/** Day ticks: 1, then every `step` days (7, 14, ...), then maxDay itself when it is not already a tick. */
export function dayTicks(maxDay: number, step = 7): number[] {
  if (!finite(maxDay) || maxDay < 1) return [];
  const out = [1];
  for (let d = step; d <= maxDay; d += step) out.push(d);
  const last = Math.round(maxDay);
  // Drop a regular tick that sits too close to the current day, so labels do not collide.
  if (out[out.length - 1] !== last) {
    if (out.length > 1 && last - out[out.length - 1] < Math.max(2, step / 3)) out.pop();
    out.push(last);
  }
  return out;
}

function niceStep(span: number): number {
  const raw = span / 5;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const r = raw / mag;
  const nice = r <= 1 ? 1 : r <= 2 ? 2 : r <= 2.5 ? 2.5 : r <= 5 ? 5 : 10;
  return nice * mag;
}

/** Nice-rounded [lo, hi] covering every finite value, optionally forced to include 0. */
export function niceDomain(values: number[], includeZero: boolean): [number, number] {
  const vs = values.filter(finite);
  if (includeZero) vs.push(0);
  if (vs.length === 0) return [0, 1];
  let lo = Math.min(...vs);
  let hi = Math.max(...vs);
  if (lo === hi) {
    const pad = lo === 0 ? 1 : Math.abs(lo) * 0.1;
    lo -= pad;
    hi += pad;
  }
  const step = niceStep(hi - lo);
  const nlo = Math.floor(lo / step + 1e-9) * step;
  const nhi = Math.ceil(hi / step - 1e-9) * step;
  // Trim floating noise such as 0.30000000000000004.
  const clean = (v: number) => Number(v.toFixed(10));
  return [clean(nlo), clean(nhi)];
}

/**
 * Wilson score 95% interval for k successes in n trials, same formula as stats.py (z = 1.959964).
 * Returns null when n < WILSON_MIN_N (no interval is drawn for small groups) or the input is invalid.
 * Check by example: wilson(26, 36) gives about [0.56, 0.84], the record's Site B D47 cumulative bounds.
 */
export function wilson(k: number, n: number): [number, number] | null {
  if (!finite(k) || !finite(n) || n < WILSON_MIN_N || k < 0 || k > n) return null;
  const p = k / n;
  const z2 = Z95 * Z95;
  const denom = 1 + z2 / n;
  const centre = (p + z2 / (2 * n)) / denom;
  const half = (Z95 * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / denom;
  return [Math.max(0, centre - half), Math.min(1, centre + half)];
}
