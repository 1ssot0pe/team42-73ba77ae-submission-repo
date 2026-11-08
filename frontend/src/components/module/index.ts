/** Parts of the generic module page (dosing and post-dosing). Rendered from a module's view model. */
export { ModuleChart, GenericLineChart } from "./ModuleChart";
export type { ModuleChartProps, ModuleChartComponentProps } from "./ModuleChart";
export { ViewCards } from "./ViewCards";
export { ViewForm } from "./ViewForm";
export type { ViewFormProps } from "./ViewForm";
export { ViewTables } from "./ViewTables";
export { chartIdFor, splitSyntheticTitle, CHART_IDS, readCards, readCharts, readForms, readKpis, readTables, toPayload, toScalar } from "./normalise";
export type { Card, Chart, ChartId, ChartSeries, Form, FormField, Marker, RefLine, Table } from "./normalise";
