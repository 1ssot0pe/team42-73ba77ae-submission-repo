/**
 * ChartFrame (docs/visuals-spec.md 1 and 4.1): the frame every chart renders in.
 *   <figure class="chart" data-chart={id}> with a takeaway title (h3), a one-line subtitle, a quiet "Synthetic"
 *   note top right (wraps under the title on phones), an optional status (dot plus word), the chart inside
 *   role="img" with an aria-label, footnotes, and a quiet "View data" text button that opens the right-hand
 *   Drawer with an accessible table of exactly what is plotted. `empty` replaces the chart (no axes).
 * Legacy props caption / legend / tag are still accepted so older call sites compile.
 */
import { useCallback, useId, useState, type ReactNode } from "react";
import { DetailsButton, Drawer } from "../projects/Drawer";
import { seriesStyle } from "./chartTheme";
import "../../styles/charts.css";

export type Cell = string | number | null;

export interface DataColumn {
  key: string;
  /** sentence case, with unit: "Accuracy (%)" */
  label: string;
  /** numbers right */
  align?: "left" | "right";
  /** marks frontend-computed columns; the drawer footnote explains */
  derived?: boolean;
}

export interface DataTable {
  columns: DataColumn[];
  rows: Array<Record<string, Cell>>;
  /** how derived columns were computed, data source */
  note?: string;
}

export interface ChartStatus {
  /** "Awaiting human sign-off" */
  label: string;
  /** dot plus word, never a filled pill */
  tone: "good" | "watch" | "alert" | "neutral";
}

export interface ChartEmpty {
  /** "Too few to show" */
  title: string;
  /** "Fewer than 5 guesses so far at any site." */
  body?: string;
}

export interface LegendItem {
  label: string;
  index: number;
}

export interface ChartFrameProps {
  /** chart id, e.g. "cusum-site"; rendered as data-chart */
  id: string;
  /** takeaway sentence computed from data */
  title: string;
  /** metric, unit, window */
  subtitle?: string;
  /** default true: quiet "Synthetic" note top right */
  synthetic?: boolean;
  status?: ChartStatus;
  /** full sentence summary for the role="img" wrapper */
  ariaLabel: string;
  /** enables the "View data" text button and drawer */
  dataTable?: DataTable;
  /** drawer title, default `Data: ${title}` */
  dataTitle?: string;
  /** under the chart, small, smoke */
  footnotes?: ReactNode;
  /** when set, replaces children (no axes) */
  empty?: ChartEmpty | null;
  children: ReactNode;
  /** heading element for the title (default 3); use 4 when the chart sits under its own section h3 */
  headingLevel?: 3 | 4;
  /** @deprecated legacy: rendered as a footnote */
  caption?: string;
  /** @deprecated legacy: a small swatch legend; prefer direct labels */
  legend?: LegendItem[];
  /** @deprecated legacy: replaces the "Synthetic" note text */
  tag?: string;
}

/** Legacy legend (only for charts with more than 4 series that cannot be labelled directly). */
export function ChartLegend({ items }: { items: LegendItem[] }) {
  return (
    <ul className="chart-legend" aria-label="Legend">
      {items.map((it) => {
        const s = seriesStyle(it.index);
        return (
          <li key={it.label} className="chart-legend__item">
            <span className={`chart-legend__swatch chart-legend__swatch--${s.pattern}`} style={{ borderTopColor: s.stroke }} aria-hidden="true" />
            {it.label}
          </li>
        );
      })}
    </ul>
  );
}

function formatCell(v: Cell): string {
  if (v === null || v === undefined || v === "") return "n/a";
  if (typeof v === "number") {
    if (!Number.isFinite(v)) return "n/a";
    const s = Number.isInteger(v) ? String(v) : String(Number(v.toFixed(4)));
    return s.startsWith("-") ? `−${s.slice(1)}` : s;
  }
  return v;
}

/** The accessible table shown in the "View data" drawer. Exported so other drawers can reuse it. */
export function ChartDataTable({ table, caption }: { table: DataTable; caption: string }) {
  const hasDerived = table.columns.some((c) => c.derived);
  return (
    <div className="chart-data">
      <div className="chart-data__scroll" tabIndex={0} role="region" aria-label={`Table: ${caption}`}>
        <table className="chart-data__table">
          <caption className="chart-data__caption">{caption}</caption>
          <thead>
            <tr>
              {table.columns.map((c) => (
                <th key={c.key} scope="col" className={c.align === "right" ? "is-num" : undefined}>
                  {c.label}{c.derived ? <span className="chart-data__derived" title="Derived in the browser"> (derived)</span> : null}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.length === 0 ? (
              <tr><td colSpan={Math.max(1, table.columns.length)} className="chart-data__none">No rows yet.</td></tr>
            ) : table.rows.map((r, i) => (
              <tr key={i}>
                {table.columns.map((c) => (
                  <td key={c.key} className={c.align === "right" ? "is-num" : undefined}>{formatCell(r[c.key] ?? null)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {table.note || hasDerived ? (
        <p className="chart-data__note">
          {table.note ?? "Columns marked derived are computed in the browser from the record."}
        </p>
      ) : null}
    </div>
  );
}

export function ChartFrame({
  id, title, subtitle, synthetic = true, status, ariaLabel, dataTable, dataTitle, footnotes, empty,
  children, caption, legend, tag, headingLevel = 3,
}: ChartFrameProps) {
  const Heading = headingLevel === 4 ? "h4" : "h3";
  const [open, setOpen] = useState(false);
  const close = useCallback(() => setOpen(false), []);
  const titleId = useId();
  const showData = !!dataTable;
  // Legacy caption "Synthetic data." duplicates the note; drop it.
  const legacyCaption = caption && !/^synthetic data\.?$/i.test(caption.trim()) ? caption : null;
  const noteText = tag ?? "Synthetic";

  return (
    <figure className="chart" data-chart={id} aria-labelledby={titleId}>
      <div className="chart__head">
        <div className="chart__heading">
          <Heading className="chart__title" id={titleId}>{title}</Heading>
          {subtitle ? <p className="chart__subtitle">{subtitle}</p> : null}
        </div>
        {synthetic ? <span className="chart__synthetic">{noteText}</span> : null}
      </div>
      {status ? (
        <p className={`chart__status chart__status--${status.tone}`}>
          <span className="chart__status-dot" aria-hidden="true" />
          {status.label}
        </p>
      ) : null}
      {empty ? (
        <div className="chart__empty" role="status">
          <p className="chart__empty-title">{empty.title}</p>
          {empty.body ? <p className="chart__empty-body">{empty.body}</p> : null}
        </div>
      ) : (
        <div className="chart__body" role="img" aria-label={ariaLabel || title}>{children}</div>
      )}
      {!empty && legend && legend.length > 0 ? <ChartLegend items={legend} /> : null}
      {footnotes || legacyCaption || showData ? (
        <figcaption className="chart__foot">
          {footnotes || legacyCaption ? (
            <div className="chart__footnotes">
              {footnotes}
              {legacyCaption ? <p>{legacyCaption}</p> : null}
            </div>
          ) : null}
          {showData ? (
            <DetailsButton className="chart__data-btn" aria-expanded={open} onClick={() => setOpen(true)}>View data</DetailsButton>
          ) : null}
        </figcaption>
      ) : null}
      {showData ? (
        <Drawer open={open} onClose={close} title={dataTitle ?? `Data: ${title}`} subtitle={subtitle} width={640}>
          <ChartDataTable table={dataTable} caption={title} />
        </Drawer>
      ) : null}
    </figure>
  );
}
