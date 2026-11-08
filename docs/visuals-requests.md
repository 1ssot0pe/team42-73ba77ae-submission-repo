# Visuals requests

Append-only. Each builder writes under its own heading (docs/visuals-spec.md 4.6).

## Requests to CORE

## Requests to teammates

## CORE API notes

All of spec section 4 is implemented with the names and types given there. Additions and small clarifications
(all backwards compatible with the spec, nothing removed or renamed):

- `ChartTooltip`: `render` is optional (without it the legacy "name value" rows are shown). Use `render` for every new chart; it receives the hovered data row (`payload[0].payload`) and returns one sentence. Return `""` to show nothing.
- `EventMarkers`: each event is `{ day, label, detected? }`. Pass the label without the day: the component appends "D47" itself ("Alert" becomes "Alert D47"). `detected: true` adds the orange 4px tick on the axis. Inside recharts use `<Customized component={(p) => <EventMarkers events={ev} xAxisMap={p.xAxisMap} offset={p.offset} />} />`; in hand-written SVG pass `xScale`, `top`, `bottom`. Labels in the right half anchor to the left of their rule. Optional `lineHeight` (default 13).
- `EndLabel`: optional `anchor` ("start" default, "middle", "end") and `weight` (600 default, 400 for context series).
- `ChartFrame`: also exports `ChartDataTable` (the drawer table, reusable) and `LegendItem`. Cells print null as "n/a" and negatives with the Unicode minus. Columns with `derived: true` get "(derived)" in the header, and the drawer shows `note` (or a default sentence) under the table.
- `chartTheme`: extra presets `flagStyle()` (orange solid, the group of interest), `chanceLine` (graphite dashed 4 4), `thresholdLine` (graphite dotted 1 3), `zeroLine` (graphite solid 1px), `eventLine` (= `driftMarker`, graphite 1px). `refLabel(text, position)` now carries a halo. Legacy `chartColors.secondary/threshold/drift` are no longer orange (smoke, graphite, graphite).
- `chartFormat`: `formatPct(null)` and other null inputs return "n/a". `dayTicks(max, step)` returns 1, step, 2·step, ..., and the current day, dropping a regular tick that sits within a few days of it.
- `normalise.ts`: also exports `chartIdFor(title, id?)`, `splitSyntheticTitle(raw)` and `CHART_IDS`. Any parenthetical containing SYNTHETIC is stripped: "(blinded, SYNTHETIC)" gives `titleNote` "blinded", "(SYNTHETIC, information only)" gives "information only". `REF_LABEL` includes `truth`, so "Planted truth" lands in `refs` as `{ y, label: "Planted truth -4" }` (read `y`, not the label text).
- `module/index.ts` exports `ModuleChartComponentProps` and `GenericLineChart`.
- `useRecordSections` keeps the previous data while a refetch after a tick is in flight (`loading` true, `data` still set), so charts do not flash empty; `data` is null only before the first load.
