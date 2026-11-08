/**
 * Frame: the Studio's chart frame. Interim local implementation of the CORE ChartFrame contract
 * (docs/visuals-spec.md 4.1), same props, so it can be replaced by a re-export of the shared ChartFrame.
 */
import { useState, type ReactNode } from "react";
import { Drawer } from "../projects/Drawer";
import { StatusDot } from "./FactDrawer";

export type Cell = string | number | null;
export interface DataColumn { key: string; label: string; align?: "left" | "right"; derived?: boolean }
export interface DataTable { columns: DataColumn[]; rows: Array<Record<string, Cell>>; note?: string }
export interface ChartStatus { label: string; tone: "good" | "watch" | "alert" | "neutral" }
export interface ChartEmpty { title: string; body?: string }
export interface ChartFrameProps {
  id: string;
  title: string;
  subtitle?: string;
  synthetic?: boolean;
  status?: ChartStatus;
  ariaLabel: string;
  dataTable?: DataTable;
  dataTitle?: string;
  footnotes?: ReactNode;
  empty?: ChartEmpty | null;
  children: ReactNode;
}

function cell(v: Cell): string {
  if (v === null || v === "") return "n/a";
  if (typeof v === "number") return String(v).replace(/^-/, "−");
  return v;
}

export function ChartFrame({ id, title, subtitle, synthetic = true, status, ariaLabel, dataTable, dataTitle, footnotes, empty, children }: ChartFrameProps) {
  const [open, setOpen] = useState(false);
  return (
    <figure className="chart st-frame" data-chart={id}>
      <header className="st-frame__head">
        <h4 className="st-frame__title">{title}</h4>
        {synthetic ? <span className="st-frame__synthetic">Synthetic</span> : null}
      </header>
      {subtitle ? <p className="st-frame__subtitle">{subtitle}</p> : null}
      {status ? <p className="st-frame__status"><StatusDot tone={status.tone}>{status.label}</StatusDot></p> : null}
      {empty ? (
        <div className="st-frame__empty">
          <p>{empty.title}</p>
          {empty.body ? <p className="studio-muted">{empty.body}</p> : null}
        </div>
      ) : (
        <div role="img" aria-label={ariaLabel} className="st-frame__body">{children}</div>
      )}
      {footnotes ? <figcaption className="st-frame__foot">{footnotes}</figcaption> : null}
      {dataTable && !empty ? (
        <>
          <button type="button" className="studio-text-btn st-frame__data" onClick={() => setOpen(true)}>View data</button>
          <Drawer open={open} title={dataTitle ?? `Data: ${title}`} onClose={() => setOpen(false)} width={640}>
            <table className="st-table">
              <caption>{title}</caption>
              <thead>
                <tr>{dataTable.columns.map((c) => <th key={c.key} scope="col" className={c.align === "right" ? "st-r" : ""}>{c.label}{c.derived ? " *" : ""}</th>)}</tr>
              </thead>
              <tbody>
                {dataTable.rows.map((r, i) => (
                  <tr key={i}>{dataTable.columns.map((c) => <td key={c.key} className={c.align === "right" ? "st-r" : ""}>{cell(r[c.key] ?? null)}</td>)}</tr>
                ))}
              </tbody>
            </table>
            {dataTable.note ? <p className="studio-small studio-muted">{dataTable.columns.some((c) => c.derived) ? "* " : ""}{dataTable.note}</p> : null}
          </Drawer>
        </>
      ) : null}
    </figure>
  );
}
