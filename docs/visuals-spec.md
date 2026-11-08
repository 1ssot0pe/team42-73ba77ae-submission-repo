# Parallax visuals spec (presentation pass)

Branch `feat/visuals`. Inputs: `docs/design-v2.md` (overrides everything below where they differ), `docs/testing/visuals/audit-trial.md`, `docs/testing/visuals/audit-studio.md`, screenshots in `docs/testing/visuals/before/`. Paths are under `frontend/src/` unless stated.

## 0. Hard rules (every builder)

1. **No invented data.** Draw only values, intervals, thresholds and events that exist in the record, a view model or the Studio report. No clinically meaningful difference is defined anywhere, so none is drawn. If something is derived in the frontend (for example a Wilson interval from counts), the "View data" drawer says how.
2. **No change to statistics or module logic.** `unblind/platform/dosing/*` and `unblind/platform/postdose/*` are off limits. Anything they do not send is computed in the frontend from data that exists (mostly `api.record(trialId, [...])`, i.e. `GET /api/trials/{id}/record?sections=...`) or listed as a request (section 4). `unblind/platform/predose/module.py` `view()` may be extended by Builder PREDOSE only, to expose values already computable, storing nothing new.
3. **Design v2:** Open Sans (300/400/600), tabular numbers, warm off-white canvas, flat surfaces, glass only on the nav. Violet `--color-spark-violet` and orange `--color-spark-ember` appear only inside charts. Labels sentence case, 13px, smoke. No uppercase eyebrows, no "(SYNTHETIC)" in titles: one quiet "Synthetic" note per chart, set by `ChartFrame`.
4. **Writing:** UK English, sentence case, no em dashes (use a comma, colon or "to"), Unicode minus for negatives (`formatSigned`).
5. **Colour is never alone.** Every colour difference is backed by a line style, marker shape or a direct text label. Direct labels at line ends or panel titles replace legends. No legends unless a chart has more than 4 series that cannot be labelled.
6. **Step, not curve.** Vault data is carry-forward. All time series use `type: "stepAfter"`. No `monotone` anywhere.
7. **Small numbers.** The vault hides groups whose window holds fewer than 5 guesses (`suppressed`). A group with no released value shows "Too few to show". Wilson intervals are drawn only where n >= 8 (`stats.WILSON_MIN_N = 8`, `unblind/platform/dosing/stats.py:41`). Points with 5 <= n < 8 are drawn as hollow markers with no band, and the tooltip says "n = 6, too few for an interval".
8. **Reference lines only where true.** "Coin flip 50%" is drawn only where 50% is the real chance level: accuracy among decisive drug/control guesses under 1:1 block randomisation (`core.py:173`, block 4). It is not drawn on CUSUM, effects or MADRS. The "Expected with working blinding 0.6" line is relabelled "Alarm reference 60% (upper end of expected under working blinding)", because 0.6 is P0, the top of the 0.5 to 0.6 range (`stats.py:27-31`).
9. **Effects:** the axis always includes 0, with a "No effect" line at 0 and direction words under the axis.
10. **Tooltips in words**, e.g. "Day 47, Site B: 15 of 15 decisive guesses correct (100%), 95% interval 80% to 100%". Touch: tooltip opens on tap, closes on tap outside or scroll (no sticky tooltip at 390 px).
11. **Dark mode:** tokens only (`var(--...)`), no hex in components. Dark variants of violet and orange already exist in `styles/tokens.css:74,100`.
12. **390 px:** no horizontal scroll, 16px gutters, labels never overlap data (collide-check markers; stack or abbreviate to "D47").
13. **Reduced motion:** at most a 160 ms opacity fade on mount, only under `prefers-reduced-motion: no-preference`. No animated lines (`isAnimationActive: false`).

### Common visual grammar

| Role | Mark | Colour token | Line style |
|---|---|---|---|
| Group of interest (alerted site, adjusted estimate, focus series) | line or point | `chartTokens.flag` (orange) | solid 2px, filled circle |
| Primary series (reported estimate, other groups, single-series data) | line or point | `chartTokens.primary` (violet) | solid 2px, filled square for estimates |
| Context series (other sites on a shared plot) | line | `chartTokens.muted` (smoke) | dashed `6 4` / dotted `1 4`, each labelled at line end |
| Chance (50%) | rule | `chartTokens.reference` (graphite) | dashed `4 4`, label "Coin flip 50%" |
| Alarm reference / threshold from data | rule | graphite | dotted `1 3`, label with value |
| No effect (0) | rule | graphite | solid 1px, label "No effect" |
| Events (onset, alert, action) | vertical rule + label with day | graphite | solid 1px; detected event gets an orange 4px tick on the axis |
| Interval band | area | same hue as its line at 12% opacity | none |
| Derived or reset segments | line | same hue | dotted `2 3`, labelled |

## 1. ChartFrame (all charts)

Every chart renders inside `ChartFrame` (section 3): takeaway title (a sentence computed from data, never a static label), one-line subtitle stating the metric, units and window, a quiet "Synthetic" note top right, an optional status line, the chart in a `role="img"` wrapper with an `aria-label`, footnotes, and a quiet "View data" text button that opens the right-hand drawer with a table of exactly what is plotted (including derived columns and how they were derived). If the data is missing or empty, the frame shows the empty state instead of axes. A takeaway template whose inputs are missing falls back to the neutral subtitle wording, never to a guess.

## 2. Charts

### Studio (Builder STUDIO)

**effect-forest** (`studio/EffectChart.tsx`, mounted at `ReportView.tsx:89`). *Question:* how much of the reported benefit survives once functional unblinding is accounted for, and does the adjusted interval still exclude no effect? *Encoding:* hand-written SVG forest plot, two rows (Reported, Bias-adjusted), x = Hedges' g, domain = nice-rounded `[min(0, all lo), max(0, all hi)]`, consistent 1-decimal ticks with Unicode minus. Reported: violet filled square, 2px CI bar; Bias-adjusted: orange filled circle, CI bar. Right-hand column (right-aligned, tabular): "0.50 [0.29, 0.72]" and "−0.07 [−0.75, 0.61]". A faint 1px smoke connector with a small arrowhead runs from the reported point to the adjusted point, labelled "Estimated bias 0.57" above it. *Reference:* "No effect" solid graphite line at 0. Under the axis, left "Favours control", right "Favours drug" (positive g favours the drug: `pipeline.py:98-121` flips MD sign because lower MADRS is better; if the source effect was standardised it is "used as reported", same convention). Axis title "Hedges' g (standardised mean difference)". *Provenance:* where `reportedStatus === "imputed"` the reported marker is hollow and the label reads "Reported (imputed)"; the interval label says "95% CI from imputed SE" because `report.ts:158-159` builds it as g ± 1.96·se_g and se_g rests on imputed arm sizes. Where `correction.u_status` is "imputed" the adjusted row label reads "Bias-adjusted (u imputed)". Status line: `report.status` rendered in sentence case as "Awaiting human sign-off" with a watch dot. *Title:* `"Reported g {rep}; adjusted {adj}, interval {crosses|does not cross} 0"`. *Subtitle:* "Adjusted estimate is conservative, under stated assumptions". *Footnote:* the five assumptions from the audit in one sentence each (synthetic calibration, imputed u, extrapolation to u = 0, tau² 0, reverse causation) and "Synthetic calibration" when `calibration` says so. No reference effect or sensitivity row is drawn (not in the brief; the sensitivity adjusted value is not in the report). *Empty:* either estimate null: draw the row that exists, the other row reads "Not available" in the right column. *Tooltip:* point focus (tabbable `<g>`): "Bias-adjusted: −0.07, 95% interval −0.75 to 0.61, standardised mean difference". *View data:* Row, Estimate, 95% low, 95% high, Source (observed / imputed / model), Note. *aria:* `"Forest plot, Hedges' g. Reported {rep} (95% CI {lo} to {hi}{, imputed}). Bias-adjusted {adj} ({lo} to {hi}). Positive favours the drug. Awaiting human sign-off."` *390:* row labels above bars, estimate column moves under each bar, direction words stay at both ends. *Dark:* tokens only; halo uses `--color-eggshell`.

**effect-readout tiles** (`ReportView.tsx:61-87`). *Question:* the three numbers at a glance. *Encoding:* three tiles in one readout row: "Reported g 0.50 (0.29 to 0.72)", "Bias-adjusted g −0.07 (−0.75 to 0.61)", "Estimated bias 0.57 g, towards the drug". Unit "g" on each tile. An "Imputed" word (dot plus word, not a pill) attached to the Reported tile when imputed; "Awaiting human sign-off" under the adjusted tile; "Synthetic calibration" under it when synthetic. No colour on values. *Title:* none (tiles); the section heading stays. *Empty:* "Not reported" in smoke. *aria:* a `<dl>`; no figure role. *390:* tiles stack. *Dark:* tokens.

**blinding-meter** (`ReportView.tsx:94-126`). *Question:* how well was the trial blinded? *Encoding:* a 0 to 1 horizontal scale "Share who could tell the arm (u)", ticks 0, 0.25, 0.5, 0.75, 1; ends labelled "0: guessing at chance" and "1: everyone knew". Estimate as a violet circle (hollow when imputed) with a ± 1 SD bar labelled "± 1 SD (0.31)"; this is the SD in the data, not a confidence interval, and the label says so. The word boundaries already used by `report.ts:177-180` (0.25 and 0.55) are drawn as faint ticks with the three words under their spans ("Well blinded", "Partly", "Largely unblinded"), so the verdict has visible boundaries. Participant and rater guess accuracy rows below: "Not reported" in smoke when null. *Title:* `"{word}: u {u} ({status})"`, e.g. "Largely unblinded: u 0.67 (imputed from design)". When the SD bar crosses a boundary add to the subtitle: "the ± 1 SD range spans {words}". *Empty:* u null: "Blinding not assessed in the source" with no scale. *Tooltip:* none needed beyond labels. *View data:* u, SD, status, note, participant and rater accuracy. *aria:* `"Unblinding u {u}, SD {sd}, {status}. {word}."` *390:* full-width scale, words under ticks wrap to two lines. *Dark:* tokens.

**design-fixes** (`ReportView.tsx:150-169`). *Question:* which design change would cut expected bias most, once feasibility is weighed? *Encoding:* dot plot, one row per counterfactual, x = expected bias (g), domain `[0, max(before)]` nice-rounded. Hollow smoke circle at "before", violet filled circle at "after", 1px connector with arrowhead, right column "0.573 to 0.489 (−0.084), feasibility 0.8". Rows ordered by `score` (reduction × feasibility) as the data already ranks them; subtitle states "Ranked by bias reduction × feasibility". `report.ts` `fixes()` must also read `feasibility` and `score` (they exist in `counterfactuals`). *Title:* `"{top change} cuts expected bias most once feasibility is weighed ({before} to {after} g)"`. *Empty:* "No design changes proposed". *Tooltip:* "Low-dose comparator: expected bias 0.573 to 0.489 g, reduction 0.084, feasibility 0.8". *View data:* Change, Before, After, Reduction, Feasibility, Score. *aria:* `"Design changes ranked by bias reduction times feasibility: {change} {before} to {after}; ..."` *390:* numeric column moves below each row. *Dark:* tokens.

### Trial: pre-dose (Builder PREDOSE)

**risk-scale** (E; `predose/UnblindingSphere.tsx` `RiskCard`/`UnblindingScale`, from `pages/Predose.tsx:139`). *Question:* how likely is the arm to be guessed under this protocol, and which fix moved it? *Encoding:* 0 to 1 line "Predicted unblinding u (share who can tell the arm)". The current value is a violet filled circle with its ± 1 SD bar (`u_sd`) labelled "± 1 SD"; earlier protocol versions form a short trail of small hollow smoke circles on the same line, each labelled under the line with the fix that moved it and its version, e.g. "v5 low-dose comparator 0.57". Only versions whose u differs from the previous one by >= 0.005 get a label; the others are counted in a footnote ("v2 to v4 did not change u; v2 moved expected bias 0.705 to 0.674 g"). Band cut-offs from `ProtocolCoDesigner.risk` (`agents.py:369`: low < 0.35, medium < 0.6, high) are faint ticks with the band words. Marker for the current value reads "Now (v6)", never "Before enrolment"; once frozen it reads "At enrolment (v6)". Expected bias in g is a secondary line of text, not a second axis. *Data:* the trail comes from a new `design_history` list in the predose view (section 3.4): per version `{version, day, why, u, u_sd, expected_bias_g, band, source}`. *Title:* with history: `"Predicted unblinding {u0} to {uNow}; {why of largest drop} moved it most ({delta})"`; with one version: `"Predicted unblinding u {u}, {band}"` and no "before/after" row. *Empty:* no risk: "Risk appears after the first design review". *Tooltip:* per version "Version 5, day −1, low-dose comparator: u 0.57 ± 0.21, expected bias 0.489 g". *View data:* Version, Day, Change, u, SD, Expected bias g, Band, Source ("stored" or "rescored, rule-based parse"). *aria:* `"Predicted unblinding by protocol version: v1 {u}, ..., now {u} ({band}). Largest change: {why}."` *390:* trail labels become numbered dots with a list below; the Synthetic note wraps under the title, never clipped. *Dark:* tokens. Styles in `styles/risk.css`.

**screening-funnel** (D; `predose/Screening.tsx` `ScreeningFunnel`, from `pages/Predose.tsx:158`). *Question:* how many applicants reached enrolment, where were the rest lost, and why? *Encoding:* CONSORT-style flow, not a funnel (eligible + excluded + flagged is a split of 500). Top box "Applied 500". It splits into three boxes side by side: "Eligible (automatic) 49", "Needs clinician 56", "Excluded (automatic) 395", each with its share of applied. Below, "Enrolled 49" with its sources stated: "49 of 49 eligible, 0 of 56 flagged" (computed from `enrolled[]` ids against `applicants[].screening.decision`). Boxes are hairline outlines with a count; no colour fills, no solid black bar. Right of Excluded: "Top reasons" list, the 6 most frequent `applicants[].screening.reasons` over excluded plus flagged, as a mini horizontal bar list (graphite bars, count at bar end, reason text left), then "and {k} more reasons" linking to View data. At the bottom: strata row from `recruitment.strata` / `enrolled[].stratum`, one small cell per site × prior use with its count (e.g. "Site A, experienced 10"). An applicant can have several reasons: the footnote says "Reasons can overlap; counts are mentions, not people". *Title:* `"{enrolled} of {applied} applicants enrolled: {e} of {eligible} eligible, {f} of {flagged} flagged"`. *Empty:* no funnel: "Screening starts after the recruitment adverts are approved". Zero counts print "0" with no bar (no 1% minimum width). *View data:* all reasons with counts, decisions by count, strata cells. *aria:* `"Screening flow: {applied} applied; {eligible} eligible, {flagged} flagged, {excluded} excluded; {enrolled} enrolled. Top exclusion reason {reason} ({n})."` *390:* the three split boxes stack vertically with a left rail connector; reasons list moves below. *Dark:* tokens. Styles in a new `styles/screening.css` (PREDOSE).

### Trial: dosing (Builder DOSING)

**rater-accuracy-site** (B; key chart on Dosing). *Question:* at each site, are raters guessing the arm better than chance, and since when? *Encoding:* small multiples, one panel per site (A, B, C) in a row, shared x (trial day, ticks every 7 days "D7, D14 ..." and the current day) and shared y (0% to 100%, ticks 0, 50, 100, axis title "Correct among decisive guesses"). Line: the view's `rolling_accuracy` (last 3 vault batches), step-after, violet; the panel of any site with a `rater_drift` alert is orange and its title carries "Drift alert day {d}". Band: Wilson 95% on the rolling counts, computed in the frontend: for each released row, sum `window_correct` and `window_decisive` over the last `ROLLING_BATCHES = 3` released rows of that group from `record.blinding_metrics` (filter `module === "dosing"`, `who === "rater"`, `by === "site"`), check the ratio matches `rolling_accuracy` within 0.001 (if not, no band for that point), and draw the band only where n >= 8. *Reference:* "Coin flip 50%" dashed; "Alarm reference 60%" dotted. *Annotations:* onset estimate, alert and action from the dosing view `markers` (same as `alerts[]`: `evidence.onset_day_estimate`, `day`, `action_day`, `resolved_day`), drawn only in the panel of their site, labelled with day: "Onset est. D28", "Alert D47", "Remote raters D48". Labels within 3 days of each other stack. *Too few:* a site with no released row shows a panel with axes and centred "Too few to show (fewer than 5 guesses so far)". Before a site's first release the panel is blank, not a line at 0. *Title:* if any drift alert: `"{site} raters flagged for drift on day {alert}; remote raters approved day {action}"` (drop the action clause if none); else `"No rater drift alert at any site to day {today}"`. *Tooltip:* "Day 47, Site B: 15 of 15 decisive guesses correct in the last 3 batches (100%), 95% interval 80% to 100%". *View data:* Day, Site, Correct, Decisive, Rolling accuracy, 95% low, 95% high (derived), Cumulative correct/decisive, Cumulative Wilson (from the record). *aria:* `"Rater guess accuracy by site, last 3 vault batches. {site}: {latest}% of {n} ({lo} to {hi}). ... Coin flip 50%. {events}."` *390:* panels stack vertically, each 140px high, shared axis ticks repeated. *Dark:* tokens.

**rater-accuracy-by-rater** (drawer). Same component and rules as rater-accuracy-site, one panel per rater at the focus site (`group` = rater id, `by === "rater"`). Subtitle explains the choice: "Raters at {site}, the site with the latest drift alert" or "the highest current drift score" (both are the view's `_focus_site` rule; the frontend infers which from `alerts[]`). *Title:* if the alert evidence has `per_rater`: `"{rater} drives the {site} alert ({k} of {n} correct)"`; else `"Rater accuracy at {site}, by rater"`. Too few: per-rater windows are often 5 to 6, so most points are hollow with no band; the footnote says "Per-rater groups are small; intervals appear once a rater has 8 or more guesses in the window". *aria:* as above per rater.

**participant-accuracy-site** (drawer). Same small multiples, using cumulative `accuracy` with the record's own Wilson bounds `accuracy_lo`/`accuracy_hi` (n = `n_decisive`, band only where n >= 8). "Coin flip 50%" line; no alarm line (participants do not alarm). Subtitle: "Cumulative; information only, no alarm is set on participant guesses". *Title:* `"Participants guess their arm correctly {min}% to {max}% of the time (day {d})"` from the latest values across sites. *Tooltip:* "Day 61, Site C: 53 of 61 correct (87%), 95% interval 76% to 93%, cumulative". *aria:* per site latest value and interval.

**cusum-site** (C; drawer, `CusumChart`). *Question:* when did the cumulative evidence of rater unblinding cross the alarm, how long after drift onset, and was it acted on? *Encoding:* one plot, x = trial day (shared tick rule), y = drift score (CUSUM, log-likelihood ratio), domain from the view's `y_domain`. Lines from the record's raw `cusum` per release (`by === "site"`), step-after; alerted site orange solid, others smoke dashed and dotted, each labelled at its line end. *Threshold:* the alarm value from the data (the view's constant "Alarm line" series, today 3.5), dotted graphite rule labelled "Alarm line 3.5", and the region above it shaded with orange at 6%. *Annotations:* "Drift onset (estimated) D28" from `evidence.onset_day_estimate`; the label "Drift began (simulated)" is used only if the true simulated drift day is exposed (request R2; it is not in the record today). "Detected D47": an orange filled circle at the first release where the alerted site's score >= the threshold, plus a vertical rule. "Action approved D48" from `action_day`. A delay callout bracket between onset and detection: "19 days from estimated onset to alert" (alert day minus onset). *Reset:* the view writes 0.0 from the day after approval (`dosing/module.py:320-325`); this is a display reset, not a measurement. Draw it as a dotted vertical drop at the action day labelled "Reset after action", then a dotted flat line at 0 until the next real release, then solid again. Use the record's raw rows so the drawn reset never looks like data. *Title:* `"{site} drift score crossed the alarm line on day {detect}, {delay} days after estimated onset; action approved day {action}"`; no alert: `"No site's drift score has reached the alarm line ({H}) to day {today}"`. *Too few:* sites with no released rows are named in a footnote "No released guesses yet: {sites}". *Tooltip:* "Day 47, Site B: drift score 5.23, above the alarm line 3.5". *View data:* Day, Site, Drift score, Released or reset (derived), Threshold, Event. Footnote: "Batched Bernoulli CUSUM, p0 0.60, p1 0.85, alarm 3.5 (from the alert evidence rule)" only if `evidence.rule` carries them. *aria:* `"Drift score by site. Alarm line {H}. {site} crossed on day {d}; estimated onset day {o}; action day {a}; reset after action."` *390:* events labels become "Onset D28", "Alert D47", "Action D48" stacked at the top; callout moves under the plot. *Dark:* tokens.

### Trial: follow-up (Builder POSTDOSE)

**effect-estimates** (Follow-up key chart, `EffectForest`). *Question:* how big is the drug effect on MADRS under each analysis, and does each interval exclude no effect? *Encoding:* forest plot, one row per estimate row in the view (`estimate`, `md`, `lo`, `hi`; only rows present), x = MADRS points, domain nice-rounded `[min(0, lo, truth), max(0, hi, truth)]`. Reported row violet square, adjusted rows orange circles, CI bars, right-hand column "−6.41 [−9.56, −3.25]". *Reference:* "No effect" at 0. "Planted truth (simulation) −4.0" as a dotted graphite vertical, taken from the data's "Planted truth" value (it is a simulator constant in the view; label says so). Under the axis: left "Favours drug", right "Favours control" (negative MD favours the drug: the view title says "negative favours the drug"). *Title:* `"Reported {r} MADRS points; after {name} {a}, interval {crosses|does not cross} 0"` for the last adjusted row. *Empty:* no rows: "Effect estimates appear once the primary endpoint is locked". *Tooltip:* "Cross-trial calibration: −2.95 MADRS points, 95% CI −7.22 to 1.33". *View data:* Estimate, Mean difference, 95% low, 95% high, Planted truth. *aria:* `"Effect on MADRS, negative favours the drug. {row}: {md} ({lo} to {hi}); ... Planted truth −4.0."` *390:* estimate column under each row. *Dark:* tokens.

**madrs-by-week** (drawer, `MadrsByWeek`). *Question:* how does the pooled, still-blinded depression score evolve by visit? *Encoding:* points at each visit week (filled violet circle) joined by a thin step-free straight segment (visits are discrete, not carry-forward). x ticks exactly at the visit weeks present ("Wk 1, 3, 6, 8, 12"); y "MADRS total (0 to 60)", domain the view's `[0, 60]`. Under each tick "n = 48"; n per week computed from `record.outcomes` and `record.followups` (rows with `madrs` and `visit_week`, the same filter as `postdose/module.py:226-237`). Mean is checked against the view value; error bars are SD only if the frontend computes it from those same values and the subtitle says "± 1 SD"; otherwise none. A week with n < half the largest n gets a hollow marker and a note "Week 12: n = 18 (visits still due)". No arm split (blinded). Week 0 drawn only if present in the data. *Title:* `"Mean MADRS {first} at week {w1} and {last} at week {wk} (n = {n}), both arms pooled"`. *Empty:* "No MADRS visits yet". *Tooltip:* "Week 12: mean MADRS 22.6, n = 18, SD 7.1". *View data:* Week, n, Mean, SD. *aria:* list of week, mean, n. *390:* n labels shrink to 11px under ticks. *Dark:* tokens.

**report-rater-accuracy-site** (drawer, `ReportAccuracy`). *Question:* what blinding evidence goes into the FDA report? *Encoding:* same small multiples as rater-accuracy-site, but the metric the report uses: cumulative `accuracy` with the record's `accuracy_lo/hi` band (n >= 8), x domain from day 1 to today (not from the first release), so it lines up with the Dosing chart. "Coin flip 50%" line. Events from `record.alerts` (onset, alert, action, resolved) as on the Dosing chart. Subtitle states the difference: "Cumulative since day 1. The Dosing chart shows the last 3 batches, so peaks differ". *Title:* `"In the report, {site} raters reach {peak}% correct (cumulative, {k} of {n}) by day {d}"` for the alerted site, else latest range across sites. *Too few / tooltip / View data / aria / 390 / dark:* as rater-accuracy-site, with cumulative counts.

## 3. File ownership map

No two builders edit the same file. Off limits to all builders: `unblind/platform/dosing/*`, `unblind/platform/postdose/*`, `unblind/stats*`, `backend/`, `api/`, `frontend/src/api.ts`, `frontend/src/trial.tsx`, `frontend/src/types.ts` (import only), `vercel.json`, `requirements*.txt`. Any file not listed is read-only. `docs/visuals-requests.md` is append-only for everyone, each builder under its own heading.

| Owner | Files |
|---|---|
| CORE | `components/shared/ChartParts.tsx`, `components/shared/chartTheme.ts`, `components/shared/ChartFrame.tsx` (new), `components/shared/useRecordSections.ts` (new), `components/shared/chartFormat.ts` (new), `components/shared/index.ts`, `components/module/ModuleChart.tsx`, `components/module/normalise.ts`, `components/module/index.ts`, `pages/ModulePage.tsx` (pass `trialId`, nothing else), `styles/charts.css` (new), `styles/components.css` (chart rules lines 328-347 only), `styles/module.css` (`.mcharts`, `.mchart__*`), `styles/drawer.css` (`.pdr .mcharts`), `styles/tokens.css` (only if a chart token is missing) |
| STUDIO | `components/studio/*` (`EffectChart.tsx`, `ReportView.tsx`, `report.ts`, `FactDrawer.tsx`, `ProgressSteps.tsx`), `pages/Studio.tsx`, `styles/studio.css` |
| DOSING | `components/module/charts/SiteSmallMultiples.tsx` (new), `components/module/charts/CusumChart.tsx` (new), `components/module/charts/dosing.css` (new) |
| POSTDOSE | `components/module/charts/EffectForest.tsx` (new), `components/module/charts/MadrsByWeek.tsx` (new), `components/module/charts/ReportAccuracy.tsx` (new), `components/module/charts/postdose.css` (new) |
| PREDOSE | `components/predose/UnblindingSphere.tsx`, `components/predose/Screening.tsx`, `components/predose/ScreeningResult.tsx`, `components/predose/BlindingSection.tsx` (optional risk column in version history), `components/predose/types.ts`, `pages/Predose.tsx` (call sites of `RiskCard` and `ScreeningFunnel`, plus fetching the predose view for `design_history`), `styles/risk.css`, `styles/predose.css` (`.risk*`, `.funnel*`), `styles/screening.css` (new), `unblind/platform/predose/module.py` (`view()` and private helpers it calls, nothing else), `tests/platform/test_predose_view.py` (new) |

Notes on reality: the existing `ChartFrame` lives in `shared/ChartParts.tsx:38-58`; CORE moves it to `shared/ChartFrame.tsx` and re-exports it from `ChartParts.tsx` and `shared/index.ts` so imports keep working. The side drawer is `components/projects/Drawer.tsx` (`Drawer`, `DetailsDrawer`); it stays read-only and CORE imports it inside `ChartFrame`. `ReportAccuracy` reuses DOSING's `SiteSmallMultiples` only by import after DOSING lands it; until then POSTDOSE renders its own panels (no shared edits). `ViewLineChart` in `ChartParts.tsx` is unused; CORE may delete it.

## 4. Interface contract

### 4.1 ChartFrame (`components/shared/ChartFrame.tsx`, CORE)

```ts
import type { ReactNode } from "react";

export type Cell = string | number | null;

export interface DataColumn {
  key: string;
  label: string;           // sentence case, with unit: "Accuracy (%)"
  align?: "left" | "right"; // numbers right
  derived?: boolean;       // marks frontend-computed columns; drawer footnote explains
}

export interface DataTable {
  columns: DataColumn[];
  rows: Array<Record<string, Cell>>;
  note?: string;           // how derived columns were computed, data source
}

export interface ChartStatus {
  label: string;           // "Awaiting human sign-off"
  tone: "good" | "watch" | "alert" | "neutral"; // dot plus word, never a filled pill
}

export interface ChartEmpty {
  title: string;           // "Too few to show"
  body?: string;           // "Fewer than 5 guesses so far at any site."
}

export interface ChartFrameProps {
  id: string;              // chart id, e.g. "cusum-site"; rendered as data-chart
  title: string;           // takeaway sentence computed from data
  subtitle?: string;       // metric, unit, window
  synthetic?: boolean;     // default true: quiet "Synthetic" note top right
  status?: ChartStatus;
  ariaLabel: string;       // full sentence summary for the role="img" wrapper
  dataTable?: DataTable;   // enables the "View data" text button and drawer
  dataTitle?: string;      // drawer title, default `Data: ${title}`
  footnotes?: ReactNode;   // under the chart, small, smoke
  empty?: ChartEmpty | null; // when set, replaces children (no axes)
  children: ReactNode;
  /** @deprecated legacy props, still accepted so old call sites compile */
  caption?: string;
  legend?: { label: string; index: number }[];
  tag?: string;
}

export function ChartFrame(props: ChartFrameProps): JSX.Element;
```

Behaviour: `<figure class="chart" data-chart={id}>`; header with `<h3>` title and `<p>` subtitle; the "Synthetic" note never clips at 390 (wraps under the title); body wrapped in `<div role="img" aria-label={ariaLabel}>`; "View data" opens `Drawer` with an accessible `<table>` (caption = title, `<th scope="col">`). Fade-in 160 ms only under `prefers-reduced-motion: no-preference`. No glass, no card fill beyond the existing flat chart surface.

### 4.2 Normalised chart (`components/module/normalise.ts`, CORE)

`Chart` gains three fields; all existing fields keep their names.

```ts
export type ChartId =
  | "rater-accuracy-site" | "rater-accuracy-by-rater" | "cusum-site" | "participant-accuracy-site"
  | "effect-estimates" | "madrs-by-week" | "report-rater-accuracy-site" | "generic";

export interface Chart {
  id: ChartId;          // from c.id if present, else matched on the backend title (below)
  title: string;        // backend title with "(SYNTHETIC...)" removed
  titleNote: string;    // text that was inside the parentheses after SYNTHETIC, e.g. "information only"
  synthetic: boolean;   // true when the backend title said SYNTHETIC
  x: string;
  series: ChartSeries[];
  data: Array<Record<string, number | string | null>>;
  refs: RefLine[];      // constant reference series ("Alarm line", "Expected with working blinding") land here with their value
  markers: Marker[];
  yDomain: [number, number] | null;
  yLabel: string;
}
```

Id matching (first match wins): `/^Rater guess accuracy by site, last/` rater-accuracy-site; `/^Rater guess accuracy (at .+, )?by rater/` rater-accuracy-by-rater; `/^Drift score \(CUSUM\)/` cusum-site; `/^Participant guess accuracy by site/` participant-accuracy-site; `/^Effect estimates/` effect-estimates; `/^Mean MADRS by visit week/` madrs-by-week; `/as recorded in the report/` report-rater-accuracy-site; else generic. "Planted truth" must land in `refs` (add `truth` to `REF_LABEL`) so the generic path does not draw it as a series; `EffectForest` reads it from `refs`.

### 4.3 Module chart components (DOSING, POSTDOSE)

```ts
import type { Chart } from "../normalise";

export interface ModuleChartComponentProps {
  chart: Chart;
  trialId: string;
  height?: number;      // plot height per chart (or per panel for small multiples)
}

// components/module/charts/SiteSmallMultiples.tsx (DOSING)
export function SiteSmallMultiples(p: ModuleChartComponentProps): JSX.Element;
// components/module/charts/CusumChart.tsx (DOSING)
export function CusumChart(p: ModuleChartComponentProps): JSX.Element;
// components/module/charts/EffectForest.tsx (POSTDOSE)
export function EffectForest(p: ModuleChartComponentProps): JSX.Element;
// components/module/charts/MadrsByWeek.tsx (POSTDOSE)
export function MadrsByWeek(p: ModuleChartComponentProps): JSX.Element;
// components/module/charts/ReportAccuracy.tsx (POSTDOSE)
export function ReportAccuracy(p: ModuleChartComponentProps): JSX.Element;
```

Each component declares `ModuleChartComponentProps` locally (structurally identical) so it does not wait for CORE; CORE also exports the same interface from `module/index.ts`. Each component renders its own `ChartFrame`. `SiteSmallMultiples` reads `chart.id` to choose metric and grouping (rolling + rater site, rolling + rater rater, cumulative + participant site).

First commit for DOSING and POSTDOSE, within the first few minutes: stub files with these exact names and signatures that return `<p className="mchart__empty">{chart.title}</p>`, so CORE's dispatch compiles from the start.

Dispatch (CORE, `ModuleChart.tsx`):

```ts
export interface ModuleChartProps { chart: Chart; trialId: string; height?: number }

export function ModuleChart({ chart, trialId, height }: ModuleChartProps) {
  switch (chart.id) {
    case "rater-accuracy-site":
    case "rater-accuracy-by-rater":
    case "participant-accuracy-site": return <SiteSmallMultiples chart={chart} trialId={trialId} height={height} />;
    case "cusum-site": return <CusumChart chart={chart} trialId={trialId} height={height} />;
    case "effect-estimates": return <EffectForest chart={chart} trialId={trialId} height={height} />;
    case "madrs-by-week": return <MadrsByWeek chart={chart} trialId={trialId} height={height} />;
    case "report-rater-accuracy-site": return <ReportAccuracy chart={chart} trialId={trialId} height={height} />;
    default: return <GenericLineChart chart={chart} height={height} />; // CORE: today's chart, stepAfter, direct labels, ChartFrame
  }
}
```

`pages/ModulePage.tsx` passes `trialId` from `useTrial()` to both call sites (lines 128 and 143). Key chart stays `charts[0]`.

### 4.4 Shared helpers CORE exports (from `components/shared/index.ts`)

```ts
// chartTheme.ts
export const chartTokens: {
  primary: string;   // "var(--color-spark-violet)"
  flag: string;      // "var(--color-spark-ember)"
  muted: string;     // "var(--color-smoke)"
  reference: string; // "var(--color-graphite)"
  grid: string;      // "var(--chart-grid)"
  axis: string;      // "var(--color-smoke)"
  halo: string;      // "var(--color-eggshell)"
  bandOpacity: 0.12;
  alarmFillOpacity: 0.06;
};
export const lineStyles: { solid: undefined; dashed: "6 4"; dotted: "1 4"; reference: "4 4"; threshold: "1 3"; derived: "2 3" };
export const stepType: "stepAfter";
export function seriesStyle(i: number): SeriesStyle;   // kept; now stepAfter, i=0 violet solid, i>=1 smoke with dash patterns (orange no longer automatic)
export const axisProps, gridProps, chartMargin;        // chartMargin.left >= 8, font Open Sans not mono

// chartFormat.ts
export function formatPct(p: number | null, digits?: 0 | 1): string;          // 0.6875 -> "69%"
export function formatSigned(v: number | null, digits?: number): string;      // Unicode minus: "−0.07"
export function formatInterval(lo: number | null, hi: number | null, unit?: "%" | "g" | ""): string; // "0.29 to 0.72"
export function formatBracket(est: number, lo: number, hi: number, digits?: number): string;        // "0.50 [0.29, 0.72]"
export function formatDayTick(d: number): string;                              // "D47"
export function dayTicks(maxDay: number, step?: number): number[];            // 1, 7, 14, ..., maxDay
export function niceDomain(values: number[], includeZero: boolean): [number, number];
export function wilson(k: number, n: number): [number, number] | null;         // z 1.959964, same formula as stats.py; null when n < 8
export const WILSON_MIN_N = 8;  // mirrors stats.py:41
export const VAULT_MIN_N = 5;   // vault release rule
export const ROLLING_BATCHES = 3; // mirrors stats.py

// useRecordSections.ts
export function useRecordSections<K extends RecordSectionName>(
  trialId: string, sections: K[],
): { data: Partial<Pick<RecordSections, K>> | null; loading: boolean; error: string | null };
// wraps api.record, refetches on useTrial().tick, caches per (trialId, tick, sections) so several charts share one fetch

// ChartParts.tsx
export function ChartTooltip(props: { active?: boolean; payload?: unknown[]; label?: unknown; render: (row: Record<string, unknown>) => string }): JSX.Element | null; // one sentence in words
export function EndLabel(props: { x: number; y: number; text: string; color: string }): JSX.Element; // direct label with halo
export function EventMarkers(props: { events: { day: number; label: string }[]; minGapPx?: number }): JSX.Element; // collision-stacked labels with day
```

`wilson` is only for counts that lack bounds (rolling windows). Where the record already has `accuracy_lo/hi`, use those. CORE adds a unit test-by-example in a comment: `wilson(26, 36)` must match the record's Site B D47 bounds (0.56 to 0.84).

### 4.5 Predose view extension (PREDOSE)

`PredoseModule.view()` adds `design_history: [{version, day, why, u, u_sd, expected_bias_g, band, source}]`, computed on the fly: for each `rec["protocol_versions"][i]`, parse `text` with `self.parser._rules(text)` (rule-based, no LLM, no ctx, no events) and score with `self.codesigner.risk(p)`. Nothing is written to `rec`. For the first version use the stored `design_review.baseline_risk` and for the last the stored `design_review.risk` (`source: "stored"`); middle versions are `source: "rescored"`. If the rescored last version differs from the stored risk, keep the stored value and note the gap in the test. `tests/platform/test_predose_view.py` checks: the list length equals the number of versions, the view does not mutate the record (deep-copy compare), and a fixture walk reproduces the audit table (v5 u 0.570, v6 0.550). The page fetches it with `api.view(trialId, "predose")`.

### 4.6 Requests

- A builder that needs a change in a CORE file writes it under `## Requests to CORE` in `docs/visuals-requests.md` (who, file, exact change, why) and carries on with a local workaround. CORE answers inline with "done" or "declined: reason".
- Data that only `dosing/` or `postdose/` (or the master) can send goes under `## Requests to teammates`, for the orchestrator to copy into `TEAMMATE_PATCHES.md`.

## 5. Data gaps for teammates (draw nothing until supplied)

- **R1, dosing view: rolling counts.** Not blocking: the frontend derives `rolling_correct/rolling_n` from `window_correct/window_decisive`. A `rolling_n`/`rolling_correct` pair per point in `_chart` would remove the derivation.
- **R2, simulated drift onset.** "Drift began (simulated)" needs the simulator's true drift day (`world.py:67`, `drift_day`), which is private and never in the record. Until the master view exposes it as an explicit synthetic-truth field, the CUSUM shows only "Drift onset (estimated)".
- **R3, drift resolution.** Alerts stay `action_approved` with `resolved_day: None` at D90 although Site B's rolling value returned to about 0.5. No "Drift stopped" marker is drawn until dosing sets `resolved_day`.
- **R4, Studio meta-regression points.** The report carries fit coefficients but not the per-trial (g, u) points behind the correction, so no meta-regression chart is drawn.
- **R5, Studio enrolment check.** NCT03866174 uses enrolment 347 from the registry; the published analysis had about 104 participants. If confirmed, g and the adjusted estimate shift by about 0.4. Pipeline fix, not a chart fix.
- **R6, threshold consistency.** Studio blinding words use 0.25 / 0.55 (`report.ts`), predose bands use 0.35 / 0.6 (`agents.py:369`). Both are drawn as they are; aligning them is a logic decision for the owners.

## 6. Orchestrator amendments
- R2 is in scope after all: `unblind/platform/master/orchestrator.py` is Danny's file and its view code may expose data that already exists. Builder DOSING owns `master/orchestrator.py` (view/state exposure only, no logic change) plus `tests/platform/test_master_view.py`, to expose the simulator's drift onset day (from `world.py`, read-only) so the CUSUM can mark "Drift began (simulated)". Nothing new is stored; the field is labelled simulated.
- `TEAMMATE_PATCHES.md` lives at `docs/testing/TEAMMATE_PATCHES.md`. The orchestrator copies the "Requests to teammates" there.
- The stubs for the five module chart components are committed on `feat/visuals` before the builders start. Each builder works in its own worktree and branch (`vis/core`, `vis/studio`, `vis/dosing`, `vis/postdose`, `vis/predose`), and the orchestrator merges them one at a time with the full suite run after each merge.
