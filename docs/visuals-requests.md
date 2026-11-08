# Visuals requests

Append-only. Each builder writes under its own heading (docs/visuals-spec.md 4.6).

## Requests to CORE

### POSTDOSE

- **ChartFrame `role="img"` around interactive points** (`components/shared/ChartFrame.tsx`). EffectForest, MadrsByWeek and ReportAccuracy put tabbable points (tooltips on keyboard focus, arrow keys through releases) inside the chart body, which ChartFrame wraps in `role="img"`; assistive tech treats children of an img as presentational. Request: an optional `interactive?: boolean` prop that renders the body as `role="group"` with the same `aria-label`. Workaround: the full summary is in `ariaLabel` and every point has its own `aria-label`.
- **Shared SVG helpers.** POSTDOSE needed a width hook, a tap/hover/scroll-safe tooltip for hand-written SVG and nice ticks; they live in `module/charts/EffectForest.tsx` (`useWidth`, `useTip`, `ChartTip`, `niceTicks`) to stay inside POSTDOSE's files, which gives 5 react-refresh warnings. If CORE wants them, move them to `shared/` and POSTDOSE will import from there.

## Requests to teammates

### POSTDOSE (for `unblind/platform/postdose/module.py` `_charts`, Callum)

- **Effect estimates: planted truth as an explicit synthetic field.** The view writes `"Planted truth": -4.0` as a hard-coded constant on every row. Request: send it from the simulator config as a labelled field, e.g. `"refs": [{"y": <truth>, "label": "Planted truth (simulated)"}]`, so the chart cannot drift from the simulator. The frontend draws it now only because it is in the payload, labelled "simulated".
- **Mean MADRS by visit week: n and SD per week.** The view sends only the mean. The frontend recounts n and SD from `record.outcomes` and `record.followups` with the view's filter and shows them only when its mean matches. Request: add `n` and `sd` to each `data` row.
- **Rater accuracy in the report: counts and bounds.** The view sends cumulative `accuracy` only, carried forward between releases. Request: per point `n_correct`, `n_decisive`, `accuracy_lo`, `accuracy_hi` (already on the record rows), and the rater drift alert markers (`onset_day_estimate`, `day`, `action_day`, `resolved_day`). The frontend reads them from `record.blinding_metrics` and `record.alerts` today.

## CORE API notes

All of spec section 4 is implemented with the names and types given there. Additions and small clarifications
(all backwards compatible with the spec, nothing removed or renamed):

- `ChartTooltip`: `render` is optional (without it the legacy "name value" rows are shown). Use `render` for every new chart; it receives the hovered data row (`payload[0].payload`) and returns one sentence. Return `""` to show nothing.
- `EventMarkers`: each event is `{ day, label, detected? }`. Pass the label without the day: the component appends "D47" itself ("Alert" becomes "Alert D47"). `detected: true` adds the orange 4px tick on the axis. Inside recharts use `<Customized component={(p) => <EventMarkers events={ev} xAxisMap={p.xAxisMap} offset={p.offset} />} />`; in hand-written SVG pass `xScale`, `top`, `bottom`. Labels sit in rows above the plot area (never on the data), placed by their measured width so same-day and near-day events stack; one rule per day. Reserve the room with `chartMargin.top + eventsTopMargin(events.length)`. Labels in the right half end at their rule. Optional `lineHeight` (default 13).
- `EndLabel`: optional `anchor` ("start" default, "middle", "end") and `weight` (600 default, 400 for context series).
- `ChartFrame`: also exports `ChartDataTable` (the drawer table, reusable) and `LegendItem`. Cells print null as "n/a" and negatives with the Unicode minus. Columns with `derived: true` get "(derived)" in the header, and the drawer shows `note` (or a default sentence) under the table.
- `chartTheme`: extra presets `flagStyle()` (orange solid, the group of interest), `chanceLine` (graphite dashed 4 4), `thresholdLine` (graphite dotted 1 3), `zeroLine` (graphite solid 1px), `eventLine` (= `driftMarker`, graphite 1px). `refLabel(text, position)` now carries a halo. Legacy `chartColors.secondary/threshold/drift` are no longer orange (smoke, graphite, graphite).
- `chartFormat`: `formatPct(null)` and other null inputs return "n/a". `dayTicks(max, step)` returns 1, step, 2·step, ..., and the current day, dropping a regular tick that sits within a few days of it.
- `normalise.ts`: also exports `chartIdFor(title, id?)`, `splitSyntheticTitle(raw)` and `CHART_IDS`. Any parenthetical containing SYNTHETIC is stripped: "(blinded, SYNTHETIC)" gives `titleNote` "blinded", "(SYNTHETIC, information only)" gives "information only". `REF_LABEL` includes `truth`, so "Planted truth" lands in `refs` as `{ y, label: "Planted truth -4" }` (read `y`, not the label text).
- `module/index.ts` exports `ModuleChartComponentProps` and `GenericLineChart`.
- `useRecordSections` keeps the previous data while a refetch after a tick is in flight (`loading` true, `data` still set), so charts do not flash empty; `data` is null only before the first load.

## DOSING

### Requests to CORE (DOSING)

- `frontend/src/types.ts` (off limits to builders): add `simulated_truth?: { synthetic: boolean; label: "simulated"; drift_site: string; drift_onset_day: number } | null` to `TrialState`. The master now sends it (`Master.simulated_truth()`, `master/orchestrator.py`); `CusumChart` reads it through a local cast until then. Not blocking.
- Tooltip touch rule: `SiteSmallMultiples.tsx` exports `useTooltipDismiss()` (closes the recharts tooltip and active dot on scroll or a tap outside, reopens on mouse move inside). If CORE wants this in `ChartTooltip` for every chart, move it to `shared/`; not blocking.

### Requests to teammates (DOSING)

- R3 still open (dosing, Izzy): the Site B alert stays `action_approved` with `resolved_day: None` at D90 although the rolling value went back to about 50%, so no "Drift stopped" marker is drawn. Both dosing charts draw it as soon as `resolved_day` is set.
- R1 not needed: rolling counts are rebuilt from `window_correct`/`window_decisive` with the monitor's reset rule and match `rolling_accuracy` at every Site B point checked. Note for dosing: after a reset the first post-action batch (`window_from` equal to the action day) is excluded from later rolling windows (`window_from > reset_day`), so D56 Site B rolling is 2 of 4, not 5 of 9. Possibly an off-by-one; the chart reproduces it as recorded.

