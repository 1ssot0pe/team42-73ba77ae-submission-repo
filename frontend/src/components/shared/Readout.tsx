/**
 * ReadoutTile and ReadoutGrid (design.md 8.5). The KPI unit: every number in Geist Mono, tabular, with a unit.
 * ReadoutTile props: kpi (a Kpi from the API: label, value, unit, baseline, note);
 *   lowerIsBetter (optional; otherwise guessed from the label and unit, e.g. "u", "reviews needed");
 *   baselineLabel (default "before").
 *   Shows "before X → now Y" with a status-tinted arrow when a baseline exists, and footnote chips:
 *   ASSUMPTION (neutral) when the note says so, EVAL vs SYNTHETIC TRUTH (watch) for evaluation figures.
 * ReadoutGrid props: kpis (Kpi[]); empty (message when there are none). 4 columns, 2 at 720px, 1 at 420px.
 */
import type { Kpi } from "../../types";
import { formatNumber } from "./format";
import { StatusPill } from "./Pills";

const LOWER_BETTER = /unblind|bias|reviews needed|missing|days from|drift|time to|error|lag|minutes/i;

/** Split "of 500" style units so the readout reads "56 of 500". */
function unitText(unit?: string): string {
  return (unit ?? "").trim();
}

function asNumber(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export interface ReadoutTileProps {
  kpi: Kpi;
  lowerIsBetter?: boolean;
  baselineLabel?: string;
}

export function ReadoutTile({ kpi, lowerIsBetter, baselineLabel = "before" }: ReadoutTileProps) {
  const unit = unitText(kpi.unit);
  const value = asNumber(kpi.value);
  const base = asNumber(kpi.baseline);
  const lower = lowerIsBetter ?? (LOWER_BETTER.test(kpi.label) || unit === "u");
  const note = kpi.note ?? "";
  const isAssumption = /assumption/i.test(note);
  const isEval = /synthetic (ground )?truth/i.test(note);

  let arrow: { glyph: string; tone: "good" | "alert" | "neutral" } | null = null;
  if (value !== null && base !== null) {
    if (value === base) arrow = { glyph: "=", tone: "neutral" };
    else {
      const up = value > base;
      const good = lower ? !up : up;
      arrow = { glyph: up ? "↑" : "↓", tone: good ? "good" : "alert" };
    }
  }
  const showBaseline = kpi.baseline !== undefined && kpi.baseline !== null && kpi.baseline !== "";

  return (
    <article className="readout" aria-label={kpi.label}>
      <div className="readout__label">{kpi.label}</div>
      <div className="readout__value">
        <span className="readout__num">{formatNumber(kpi.value)}</span>
        {unit ? <span className="readout__unit">{unit}</span> : null}
      </div>
      {showBaseline ? (
        <div className="readout__delta">
          <span>{baselineLabel} {formatNumber(kpi.baseline)} &rarr; now {formatNumber(kpi.value)}</span>
          {arrow ? (
            <span className={`readout__arrow readout__arrow--${arrow.tone}`}
              aria-label={arrow.tone === "good" ? "moved the right way" : arrow.tone === "alert" ? "moved the wrong way" : "no change"}>
              {arrow.glyph}
            </span>
          ) : null}
        </div>
      ) : null}
      {isAssumption || isEval ? (
        <div className="readout__chips">
          {isAssumption ? <StatusPill tone="neutral">Assumption</StatusPill> : null}
          {isEval ? <StatusPill tone="watch">Eval vs synthetic truth</StatusPill> : null}
        </div>
      ) : null}
      {note ? <p className="readout__note">{note.replace(/\bSYNTHETIC\b/g, "synthetic")}</p> : null}
    </article>
  );
}

export interface ReadoutGridProps {
  kpis: Kpi[] | null | undefined;
  empty?: string;
}

export function ReadoutGrid({ kpis, empty = "Readouts appear once the agents have run." }: ReadoutGridProps) {
  if (!kpis || kpis.length === 0) return <p className="t-body-sm c-smoke">{empty}</p>;
  return (
    <div className="readout-grid">
      {kpis.map((k, i) => <ReadoutTile key={`${k.label}-${i}`} kpi={k} />)}
    </div>
  );
}
