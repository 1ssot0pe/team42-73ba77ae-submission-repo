/**
 * ReportAccuracy: placeholder with the agreed signature (docs/visuals-spec.md section 4) so ModuleChart's dispatch
 * compiles. Builder POSTDOSE replaces this file; nobody else edits it.
 */
import type { Chart } from "../normalise";

export interface ModuleChartComponentProps {
  chart: Chart;
  trialId: string;
  height?: number;
}

export function ReportAccuracy({ chart }: ModuleChartComponentProps): JSX.Element {
  return <p className="t-body-sm">{chart.title}</p>;
}
