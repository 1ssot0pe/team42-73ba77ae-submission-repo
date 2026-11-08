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

