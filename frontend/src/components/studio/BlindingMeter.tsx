/**
 * BlindingMeter (blinding-meter): the unblinding u on a 0 to 1 scale with its ± 1 SD bar.
 * The band cut-offs are the backend's (report.ts BLINDING_BANDS, from predose/agents.py: 0.35 and 0.6),
 * so Studio and Pre-dose classify u the same way. When the ± 1 SD range crosses a cut-off, no single band is claimed. The bar is the SD the report carries, not a confidence interval.
 */
import type { Blinding } from "./report";
import { BLINDING_BANDS, bandWord, fmt } from "./report";
import { useWidth } from "./PointTip";

const VIOLET = "var(--color-spark-violet)";
const TICKS = [0, 0.25, 0.5, 0.75, 1];

/** Greedy word wrap by an approximate glyph width; good enough for short labels at a known font size. */
export function wrap(text: string, maxPx: number, charPx = 6.6): string[] {
  const words = text.split(" ");
  const lines: string[] = [];
  let cur = "";
  for (const w of words) {
    const next = cur ? `${cur} ${w}` : w;
    if (cur && next.length * charPx > maxPx) { lines.push(cur); cur = w; } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}

export function statusPhrase(status: string): string {
  if (status === "imputed") return "imputed from design";
  if (status === "derived") return "derived from guess data";
  return status || "status unknown";
}

function sdRange(b: Blinding): [number, number] | null {
  return b.u !== null && b.uSd !== null ? [Math.max(0, b.u - b.uSd), Math.min(1, b.u + b.uSd)] : null;
}

/** Bands the ± 1 SD range touches (or the estimate's band when there is no SD). */
export function spannedBands(b: Blinding): typeof BLINDING_BANDS {
  const r = sdRange(b);
  if (!r) return b.u === null ? [] : BLINDING_BANDS.filter((band) => b.u! >= band.from && b.u! < band.below);
  return BLINDING_BANDS.filter((band) => r[1] >= band.from && r[0] < band.below);
}

export function blindingTitle(b: Blinding): string {
  const r = sdRange(b);
  const spanned = spannedBands(b);
  const prefix = b.observed ? "Observed" : "Imputed";
  if (r && spanned.length > 1) {
    const words = `${spanned[0].band} to ${spanned[spanned.length - 1].band} unblinding`;
    return `${prefix} u ${fmt(b.u)} (± 1 SD ${fmt(r[0])} to ${fmt(r[1])}): ${words}`;
  }
  return `${b.word}: u ${fmt(b.u)} (${statusPhrase(b.status)})`;
}

export function blindingSubtitle(): string {
  return "Share who could tell their arm (u), 0 to 1. The bar is ± 1 SD, not a confidence interval. Bands at 0.35 and 0.6 are the ones the Pre-dose risk check uses.";
}

export function blindingAria(b: Blinding): string {
  const sp = spannedBands(b);
  const verdict = sp.length > 1 ? `The ± 1 SD range spans ${sp.map((x) => x.band).join(" to ")} unblinding` : b.word;
  return `Unblinding u ${fmt(b.u)}, SD ${fmt(b.uSd)}, ${statusPhrase(b.status)}. ${verdict}.`;
}

export function BlindingMeter({ b }: { b: Blinding }) {
  const { ref, w: W } = useWidth(620);
  const u = b.u ?? 0;
  const hollow = !b.observed;
  const L = 12, R = 12;
  const x = (v: number) => L + v * (W - L - R);
  const r = sdRange(b);
  const trackY = 50;
  const tickY = trackY + 22;
  const wordY = tickY + 26;
  const bandLines = BLINDING_BANDS.map((band) => wrap(band.word, x(Math.min(1, band.below)) - x(band.from) - 8, 6.2));
  const endY = wordY + (Math.max(...bandLines.map((l) => l.length)) - 1) * 13 + 24;
  const H = endY + 6;
  const valueText = `u ${fmt(b.u)}${b.uSd !== null ? `, ± 1 SD ${fmt(b.uSd)}` : ""}`;
  const valueX = Math.max(L + 70, Math.min(W - R - 70, x(u)));
  const cuts = BLINDING_BANDS.slice(1).map((band) => band.from);

  return (
    <div ref={ref} className="st-meter">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} focusable="false">
        {/* band spans with their words, cut-offs as faint dotted rules */}
        {BLINDING_BANDS.map((band, bi) => {
          const a = x(band.from), z = x(Math.min(1, band.below));
          const lines = bandLines[bi];
          return (
            <text key={band.word} x={(a + z) / 2} y={wordY} textAnchor="middle" className="st-sub">
              {lines.map((ln, i) => <tspan key={i} x={(a + z) / 2} dy={i ? 13 : 0}>{ln}</tspan>)}
            </text>
          );
        })}
        {cuts.map((c) => (
          <g key={c}>
            <line x1={x(c)} x2={x(c)} y1={trackY - 16} y2={wordY + 16} className="st-cut" />
            {TICKS.includes(c) ? null : (
              <text x={x(c)} y={trackY - 20} textAnchor="middle" className="st-label st-label--small">{fmt(c)}</text>
            )}
          </g>
        ))}
        <line x1={L} x2={W - R} y1={trackY} y2={trackY} className="st-track" />
        {TICKS.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={trackY + 4} y2={trackY + 8} className="st-axis" />
            <text x={x(t)} y={tickY} textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"} className="st-tick">
              {t === 0 ? "0" : t === 1 ? "1" : String(t)}
            </text>
          </g>
        ))}
        {r ? (
          <g>
            <line x1={x(r[0])} x2={x(r[1])} y1={trackY} y2={trackY} strokeWidth={3} style={{ stroke: VIOLET, opacity: 0.8 }} />
            <line x1={x(r[0])} x2={x(r[0])} y1={trackY - 6} y2={trackY + 6} strokeWidth={2} style={{ stroke: VIOLET }} />
            <line x1={x(r[1])} x2={x(r[1])} y1={trackY - 6} y2={trackY + 6} strokeWidth={2} style={{ stroke: VIOLET }} />
          </g>
        ) : null}
        {b.u !== null ? (
          <circle
            cx={x(u)} cy={trackY} r={7}
            style={hollow ? { fill: "var(--color-eggshell)", stroke: VIOLET, strokeWidth: 2.5 } : { fill: VIOLET, stroke: "var(--color-eggshell)", strokeWidth: 1.5 }}
          />
        ) : null}
        <text x={valueX} y={14} textAnchor="middle" className="st-value">
          {valueText}{hollow ? <tspan className="st-flag"> (imputed)</tspan> : null}
        </text>
        <text x={L} y={endY} className="st-label st-label--small">0: guessing at chance</text>
        <text x={W - R} y={endY} textAnchor="end" className="st-label st-label--small">1: everyone knew</text>
      </svg>
    </div>
  );
}

export function blindingTable(b: Blinding, participants: number | null, raters: number | null) {
  const r = sdRange(b);
  return {
    columns: [
      { key: "item", label: "Item" },
      { key: "value", label: "Value", align: "right" as const },
      { key: "note", label: "Note" },
    ],
    rows: [
      { item: "Unblinding u (0 to 1)", value: b.u, note: `${statusPhrase(b.status)}. ${b.note}`.trim() },
      { item: "SD of u", value: b.uSd, note: "Standard deviation, not a confidence interval" },
      { item: "± 1 SD range", value: r ? `${fmt(r[0])} to ${fmt(r[1])}` : null, note: "u ± SD, clipped to 0 to 1 (computed in the browser)" },
      { item: "Band of the estimate", value: b.u !== null ? bandWord(b.u) : null, note: "Backend bands (predose/agents.py): u below 0.35 low, below 0.6 medium, else high" },
      { item: "Bands within ± 1 SD", value: spannedBands(b).map((x) => x.band).join(" to ") || null, note: "No single band is claimed when this spans more than one" },
      { item: "Participant guess accuracy", value: participants, note: participants === null ? "Not reported" : "" },
      { item: "Rater guess accuracy", value: raters, note: raters === null ? "Not reported" : "" },
    ],
    note: "From the report's facts u, u_sd and guess_acc_*. Band cut-offs duplicated from the backend's risk bands.",
  };
}
