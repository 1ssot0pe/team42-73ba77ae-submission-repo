# Visuals audit: the trial workspace (before)

Auditor: AUDIT-TRIAL. Date: 2026-11-08. Branch `feat/visuals` (from origin/main 49fdef7). Read only; no product code changed.

## How the evidence was made

- Stack: backend on :8601 (`UNBLIND_STORE_DIR=/tmp/vis-audit/store`), vite on :5601.
- Trial: `POST /api/trials {"example":"example_psilocybin_trd.md","n_applicants":500,"seed":42,"auto_approve":false}`, giving trial `T-144534-5135`. It was seeded into `parallax.projects.v1` as project `p-audit01` and opened at `/trials/p-audit01/<stage>`.
- Walk, with every approval made by "Dr A. Auditor" through the API:
  1. Five design fixes approved in order: raters, guess questionnaire, expectancy, low-dose comparator, stratification.
  2. Clinician shortlist approved: 49 enrolled.
  3. Advanced to day 48. Literature and Site C reminder approvals were made along the way.
  4. Drift approval `a144919e` ("Move Site B raters to remote (central) assessment", raised D+47) was shot before the decision, then approved, so the action falls on D+48.
  5. Advanced to D+62 and shot, then to D+90 (closed; report signed D+90) and shot.
- Screenshots: `docs/testing/visuals/before/<id>-{1440-light,1440-dark,390}.png`. These are element crops at 1440x900 light, 1440x900 dark (`color_scheme: dark` plus the app's own `unblind.theme=dark`, which sets `data-theme`), and 390x844 at 2x. All files are under 400 KB.
- Charts that are not the "key chart" only render inside the "View all charts" drawer. They were shot there (`[role=dialog] figure.chart`).

## Cross-cutting problems (all `ModuleChart` charts)

These apply to every chart built by `frontend/src/components/module/ModuleChart.tsx` and themed by `shared/chartTheme.ts`.

1. **Wrong interpolation.**
   - The cause is `type: "monotone"` (chartTheme.ts:71).
   - The vault data is carry-forward: one value per release, held until the next one. The right shape is a step line.
   - Monotone draws curved ramps between releases, with S-curves and overshoot. Examples: the Site A dip at D+12 to D+14 in `rater-accuracy-site-*`, and the Site C bumps in `cusum-site-*`. These imply values on days nothing was measured.
2. **Colour collisions.**
   - Series 1 is ember (chartTheme.ts:55-61). The threshold line, the "Expected" line and every event marker are also ember.
   - On the rater charts, Site B (the drifting site) is ember dashed, the same colour and dash as "Expected with working blinding 0.6". At D+28 to D+37 the two are indistinguishable (`rater-accuracy-site-1440-light.png`).
   - The palette also gives graphite to series 2 and series 4, and ash to series 3. Those are grey on grey in dark mode.
3. **Legend instead of direct labels.**
   - Every chart has a bottom legend (ChartParts.tsx:39-50), and Site A/B/C are only separable by colour and dash.
   - No series is labelled at its line end.
4. **Synthetic tagging said three times.**
   - Each chart says "(SYNTHETIC)" in the title (from the backend), plus a "Synthetic" tag, plus a "Synthetic data." caption. That is noisy, and the title text is in upper case.
   - At 390 the "Synthetic" tag is clipped at the right edge (`risk-scale-390.png`, `rater-accuracy-site-390.png`).
5. **No axis titles or units.**
   - Y is unlabelled (0, 0.25 … 1). It should read "share of decisive guesses correct" or %.
   - X ticks are uneven: D+1, D+21, D+41, D+62 at D+62; D+1, D+26, D+51, D+90 at D+90. They come from `domain ["dataMin","dataMax"]` with recharts' automatic ticks.
   - There are no week gridlines and no axis title "Trial day".
6. **No uncertainty and no n.**
   - Chart rows carry a single number per group. Counts are dropped in `dosing/module.py:301-334` `_chart`.
   - The tooltip (ChartParts.tsx:76-92) prints three decimals ("3.484"), with no n and no interval.
7. **Marker labels collide.**
   - "Alert" (D+47) and "Remote raters" (D+48) are one day apart. `groupMarkers` only merges equal x (ModuleChart.tsx:24-33), so at 390 the labels "Onset (est.)", "Alert" and "Remote raters" pile up over the data.
   - Marker labels carry no day number ("Alert", not "Alert D+47").
8. **Tooltip on touch sticks.**
   - At 390 the tooltip opened on scroll and covered the plot (`cusum-site-d90-390.png`).
9. **Margins.** `chartMargin.left = -12` (chartTheme.ts:107) pulls the Y ticks to the frame edge.
10. **Accessibility.** The recharts SVGs have no `role="img"` or `aria-label`, and there is no data-table alternative linked from the chart. Tables do exist in the "View all tables" drawer but are not tied to the charts. Meaning is carried by colour plus dash, which helps, but the dash patterns are tiny in the legend swatch.
11. **Only one chart is visible per stage.**
    - The key chart is `model.charts[0]` (ModulePage.tsx:78,128). The CUSUM chart, which is the actual detection statistic, sits behind "View all charts" (ModulePage.tsx:143).

---

## Charts

### 1. `risk-scale`: predicted unblinding (blinding-risk line)

- **Where.** `/trials/:id/design-review`, Design review. `components/predose/UnblindingSphere.tsx:55` (`UnblindingScale`) inside `RiskCard` (:133), rendered from `pages/Predose.tsx:139`.
- **Question.** How likely are participants and raters to guess the arm under this protocol, and did the fixes help enough?
- **Data.**
  - `design_review.risk {u, u_sd, expected_bias_g, band, calibration, design_model}` and `baseline_risk` (same shape). `risk_at_enrolment` is absent here; it is frozen at enrolment.
  - Real values: baseline u 0.786, g 0.705, band high. Now u 0.55, g 0.472, band medium, u_sd 0.212.
  - Calibration: "SYNTHETIC calibration set … 15 trials".
- **Earlier values: which fix moved it.**
  - The record keeps only the baseline and the current value. `protocol_versions[]` holds the text but no risk.
  - Rescored offline per version (ProtocolParser plus ProtocolCoDesigner.risk on each `protocol_versions[i].text`):

    | v | fix | u | g | band |
    |---|---|---|---|---|
    | 1 | initial draft | 0.786 | 0.705 | high |
    | 2 | central remote raters | 0.786 | 0.674 | high |
    | 3 | guess questionnaire | 0.786 | 0.674 | high |
    | 4 | expectancy timing | 0.786 | 0.674 | high |
    | 5 | **low-dose comparator** | **0.570** | 0.489 | medium |
    | 6 | **stratify by prior use** | **0.550** | 0.472 | medium |

  - So the comparator fix did almost all the work on u. The rater fix moved only g.
  - The visual cannot show this: it has two markers, "Before fixes 0.79" and the current one. A per-version series needs the backend to store `risk` on each version, or the frontend to keep it.
- **What is wrong.**
  - **Before any fix**, it reads "Before fixes 0.79 u, now 0.79 u · no change" (`risk-scale-baseline-1440-light.png`). That fact row makes no sense before a fix exists.
  - The current marker is labelled **"Before enrolment"**, which reads as a past value. It should say "Now" or "After fixes".
  - **The ± 0.21 sd is not drawn.** The interval spans about 0.34 to 0.76, and it crosses both band boundaries. The large "u = 0.55 Medium" overstates precision.
  - **Band cut-offs are not on the scale**, so "Medium" has no visible boundaries.
  - The 0 end is labelled "coin flip". u = 0 means guessing at chance, but the axis words never say "share who can tell".
  - At 390 the `SpecimenTag` is clipped (`risk-scale-390.png`).
  - Dark mode is fine (`risk-scale-1440-dark.png`).
  - Good: `role="img"` with a full aria-label, and the arrows carry text.
- **Shots.** `risk-scale-{1440-light,1440-dark,390}.png` (after the 5 fixes) and `risk-scale-baseline-*.png` (before).

### 2. `screening-funnel`: screening funnel

- **Where.** `/trials/:id/screening`, Screening. `components/predose/Screening.tsx:17-49`, rendered from `pages/Predose.tsx:158`.
- **Question.** How many applicants made it to enrolment, where were they lost, and why?
- **Data.**
  - `recruitment.funnel {applied: 500, auto_eligible: 49, auto_excluded: 395, needs_clinician: 56, enrolled: 49}`.
  - Also available but **not shown** in the funnel: `applicants[].screening {decision, reasons[], criteria_hit, evidence}`.
  - Top exclusion reasons (of 395 excluded plus 56 flagged):

    | n | reason |
    |---|---|
    | 110 | sertraline washout |
    | 74 | only 1 failed antidepressant |
    | 63 | diagnosis anxiety |
    | 58 | diagnosis none |
    | 56 | non-UK mobile |
    | 51 | escitalopram |
    | 50 | 0 failed antidepressants |
    | 48 | venlafaxine |
    | 44 | lithium |
    | 44 | cannot attend visits |
    | 37 | psychosis or bipolar |
    | 29 | free-text safety risk |

  - `recruitment.strata` and `enrolled[].stratum` give the randomisation cells (site × prior use): A experienced 10, A naive 6, B naive 9, B experienced 7, C experienced 10, C naive 7. Cells are 6 to 10 people.
  - `recruitment.fairness`: age band and country.
- **What is wrong.**
  - **It is not a funnel.** Eligible 49, Excluded 395 and Needs clinician 56 are a partition of Applied (49 + 395 + 56 = 500), yet they are drawn as sequential stages. Enrolled 49 then reads as coming from "Needs clinician 56".
  - The truth is all 49 auto-eligible were enrolled and 0 of 56 flagged were enrolled. This should be Applied → {eligible, flagged, excluded} → enrolled, with the flagged outcome explicit.
  - All percentages are relative to Applied, so "Enrolled 9.8 %" hides "100 % of eligible".
  - **No exclusion reasons and no strata.** The single most useful breakdown (the reasons above) is only in the ledger drawer, and only for flagged people.
  - **Colour only.** Excluded is a pink tint, Needs clinician cream, Enrolled solid black. The solid-black Enrolled bar is the heaviest mark on the page. "Excluded = bad" is colour-only.
  - The bars use a 1 % minimum width, so 0 vs 1 is not distinguishable.
  - The synthetic note is written as "SYNTHETIC applicants…" in caps, not the shared tag.
  - At 390 the label sits above the bar (OK). Dark mode is OK.
- **Shots.** `screening-funnel-*.png`.
- **Related table: `fairness`.**
  - Drawer: `Screening.tsx:73`, "Fairness: eligibility by group".
  - The summary line says "eligibility is even across all 2 groupings". Yet age 65+ is 0 / 118 eligible (0 %) and France, Germany and US are 0 of 56 combined, all UK-only by design (mobile rule).
  - The 20-point spread rule calls 0 % vs 13.5 % "even". That is honest per the rule but misleading without the reason.

### 3. `rater-accuracy-site`: blinding monitor, rater guess accuracy by site (key chart on Dosing)

- **Where.** `/trials/:id/dosing`. `ModuleChart.tsx`, via `pages/ModulePage.tsx:128` (key chart). Built by `unblind/platform/dosing/module.py:201-205` and `_chart` at :301.
- **Question.** At each site, are raters guessing the arm more often than working blinding allows, and since when?
- **Data sent to the chart.**
  - 90 rows (D+1 … D+90): `{day, "Site A", "Site B", "Site C", "Expected with working blinding": 0.6}`, where the site values are `rolling_accuracy` over the last 3 vault batches, carried forward, `null` before the first release.
  - `markers: [{x:28,"Onset (est.)"},{x:47,"Alert"},{x:48,"Remote raters"}]`, `y_domain [0,1]`.
- **Counts: are they available for a Wilson interval?**
  - **Not in the chart payload.** They are in the record (`GET /record?sections=blinding_metrics`): every row has `n_decisive, n_correct, accuracy, accuracy_lo, accuracy_hi` (Wilson 95 %, cumulative), plus `window_n, window_correct, window_decisive, window_accuracy, rolling_accuracy, cusum, threshold, suppressed, dont_know`.
  - Example for Site B:

    | day | rolling | cumulative | Wilson 95 % | cusum |
    |---|---|---|---|---|
    | D+13 | 2/5 | | | |
    | D+31 | 0.688 | 16/26 | 0.43 to 0.78 | 1.742 |
    | D+37 | 0.80 | 21/31 | 0.50 to 0.81 | 3.484 |
    | D+47 | 1.0 (15/15) | 26/36 | 0.56 to 0.84 | 5.226 |

  - The rolling value is over about 15 guesses (3 batches of 5 or 6), so `rolling_correct/rolling_n` can be derived from the last 3 `window_*` rows. The frontend could compute Wilson if the view passed `window_correct/window_decisive` per point, or `rolling_n`/`rolling_correct`.
  - Per-site cells: 5 to 6 guesses per batch, rolling n about 15, cumulative n 36 to 45 by D+59.
- **"Too few" rule.**
  - The vault releases a group only when its window holds **5 or more guesses** (`suppressed`, module.py docstring).
  - The Wilson alarm needs **n ≥ 8** (`stats.WILSON_MIN_N = 8`, `WILSON_THRESHOLD 0.75`).
  - The rater table prints "under 5 / suppressed".
  - The chart shows **nothing** for this. Lines simply start at D+10 to D+13 (null before), with no "too few guesses yet" state, and a 2/5 = 0.4 point is drawn with the same weight as 26/36.
- **What is wrong.**
  - **The plotted value swings between 0.4 and 1.0 on n = 5 to 15 with no interval.** At D+47 Site B shows 1.0, the honest "15 of 15, 95 % 0.80 to 1.00", while the cumulative is 0.72.
  - "Last 3 vault batches" is in the title but not explained.
  - Site B and the expected line share ember and dash (cross-cutting 2).
  - Curved ramps between releases (1). No n in the tooltip (6). Legend only (3).
  - Marker labels have no days, and "Alert"/"Remote raters" collide at 390 (7).
  - The expected line is labelled "Expected with working blinding 0.6". In fact 0.6 is P0, the *top* of the expected 0.5 to 0.6 range (stats.py:27-31). There is no 0.5 chance line.
  - **No "drift stopped" marker.** The alert stays `action_approved` with `resolved_day: None` at D+90, although Site B's rolling value went back to 0.5 by about D+60. The chart never closes the story.
- **Shots.**
  - `rater-accuracy-site-predecision-*.png` (D+48, decision pending)
  - `rater-accuracy-site-*.png` (D+62, on page)
  - `drawer-rater-accuracy-site-*.png` (D+62, in drawer)
  - `rater-accuracy-site-d90-*.png`

### 4. `rater-accuracy-by-rater`: rater accuracy at the focus site, by rater

- **Where.** Dosing, "View all charts" drawer. `ModuleChart.tsx`; built at `dosing/module.py:205-208`.
- **Question.** Which rater(s) at the drifting site drive the alarm?
- **Data.**
  - `{day, "R-B1", "R-B2", "Expected with working blinding": 0.6}`, rolling over 3 batches, with the same markers.
  - Per-rater `window_n` is 5 (24 rows) or 6 (3 rows).
  - Alert evidence: `per_rater {"R-B2": 5/5}`. The rater table has Wilson intervals as text ("95% interval").
- **What is wrong.**
  - n per point is about 5 to 15 with no interval. R-B1 moves 0.2 → 0.4 → 0.75 on single batches.
  - Same colour clash: R-B2 is ember dashed, the same as the expected line.
  - The title changes with state ("at Site B"), but nothing says why this site was chosen (`_focus_site`, :255).
  - The data has the interval as text in a table but not on the chart.
- **Shots.** `rater-accuracy-by-rater-*.png`.

### 5. `cusum-site`: drift score (CUSUM) by site

- **Where.** Dosing, drawer only. `ModuleChart.tsx`; built at `dosing/module.py:209-211`.
- **Question.** When did the cumulative evidence of rater unblinding cross the alarm, how far past it, and did the action reset it?
- **Data.**
  - `{day, Site A, Site B, Site C, "Alarm line": 3.5}`, `y_domain [0, ceil(max(3.5*1.4, peak*1.1))] = [0,6]`.
  - Statistic: batched Bernoulli CUSUM, p0 0.60, p1 0.85, H 3.5 (`stats.py:31-33`; evidence `rule`).
  - Site B path: 0 → 1.742 (D+31) → 3.484 (D+37, just under the line, held 10 days) → **5.226 (D+47, alert)** → forced to 0 the day after approval (`resets`, module.py:320-325).
  - Drift onset estimate D+28 (`evidence.onset_day_estimate`). **Detection day D+47. Action approval D+48** (`actions[].day`).
  - `correct_since_onset 15 / n_since_onset 15`, `ci_since_onset [0.796, 1.0]`.
  - KPI "Days from drift onset to alert" 19 (baseline 62).
- **What is wrong.**
  - **The reset to 0 is synthetic display, not data.** The view writes 0.0 from the day after approval, and the chart draws it as a curved drop like a measurement. It should be a broken line or labelled "reset after action".
  - **Site C's bumps (0.412, 0.064) are smoothed into hills** that dip below 0 visually (monotone).
  - Onset, Alert and Remote raters are ember verticals, the same colour as Site B and the alarm line. On this chart everything important is the same orange (`cusum-site-1440-light.png`). At 390 they merge into one thick bar.
  - "Alarm line 3.5" has no explanation of what 3.5 means (false-alarm rate 0.3 per trial). The y axis has no unit ("log-likelihood score").
  - The detection crossing (3.484 → 5.226) is not marked as a point, only by the "Alert" vertical.
  - This is the actual statistic behind the decision, but it is hidden in a drawer while the noisier rolling accuracy is the key chart.
- **Shots.** `cusum-site-*.png` (D+62) and `cusum-site-d90-*.png`. The 390 shot at D+90 also shows the stuck touch tooltip.

### 6. `participant-accuracy-site`: participant guess accuracy by site (information only)

- **Where.** Dosing, drawer. Built at `dosing/module.py:212-213`.
- **Question.** How well do participants guess their arm? This is the classic functional-unblinding signal: psilocybin vs inert placebo.
- **Data.**
  - `{day, Site A, Site B, Site C}`, using the cumulative `accuracy` field. No reference line.
  - Latest: Site C 53/61 = 0.869 (Wilson 0.76 to 0.93), and Site A about 0.92. Counts and `accuracy_lo/hi` are in the record but not the chart.
- **What is wrong.**
  - **No chance (0.5) or expected line**, so 0.87 to 0.92, which means participants are almost fully unblinded, reads as just a high flat line.
  - "Information only" is not explained on the chart.
  - No n and no interval. Cumulative is not stated on the axis. Legend only.
  - Y starts at 0 (correct for a proportion) but there are no units.
- **Shots.** `participant-accuracy-site-*.png`.

### 7. `effect-estimates`: effect estimates (Follow-up key chart)

- **Where.** `/trials/:id/follow-up`, key chart. `ModuleChart.tsx`; built at `postdose/module.py:213-225`.
- **Question.** How big is the drug effect on MADRS once expectancy and unblinding are accounted for, and how sure are we?
- **Data.**
  - 2 rows, x categorical `estimate`:

    | estimate | md | 95 % CI |
    |---|---|---|
    | Reported | -6.41 | -9.56 to -3.25 |
    | Cross-trial calibration | -2.95 | -7.22 to 1.33 |

    Both rows also carry `"Planted truth": -4.0`.
  - The two "Within-trial" estimates are null here, so they are dropped.
  - Real intervals exist.
- **What is wrong (the worst chart).**
  - **The wrong chart type.** Separate estimates are drawn as a line chart: "Estimate", "95% CI low" and "95% CI high" are three lines *connecting* "Reported" to "Cross-trial calibration". They imply a trend between two unrelated methods.
  - It needs a forest plot: one row per estimate, a point with a horizontal CI bar, a 0 (no effect) line and the planted truth line.
  - **CI bounds are plotted as series** with a legend ("95% CI low" ember dashed, "95% CI high" grey dotted), so the colour of the "low" bound collides with the threshold colour.
  - **There is no 0 / no-effect reference.** The reader must see that the adjusted CI (-7.22 to 1.33) crosses 0 and the reported one does not. That is the key finding, and it is invisible.
  - "Planted truth" is drawn as a constant series, picked up as a ref line only because the label regex misses "truth" (normalise.ts:91). So it is in the legend as a line.
  - The X axis shows only the two end labels. Interior categories would vanish.
  - The y domain is auto (-12 to 4), which is fine as it includes 0, but the units "MADRS points" are only in the title.
- **Shots.** `effect-estimates-*.png` (drawer) and `followup-key-chart-*.png` (page).

### 8. `madrs-by-week`: mean MADRS by visit week, pooled

- **Where.** Follow-up drawer. Built at `postdose/module.py:226-237`.
- **Question.** How does the depression score evolve in the blinded trial as a whole?
- **Data.**
  - `{week, "All participants"}`: week 1 24.5, 3 21.7, 6 22.2, 8 21.7, 12 22.6. `y_domain [0,60]`.
  - **n per week, not sent:** 48, 49, 49, 49, **18**.
  - No SD or SE is sent; the record has individual `madrs` values, so they could be.
- **What is wrong.**
  - Week 12 has n = 18 against 49 elsewhere, yet it is drawn identically.
  - No error bars. No baseline (week 0) point.
  - The x axis is numeric with auto ticks (1, 4, 7, 12), not the visit weeks (1, 3, 6, 8, 12). Points are not marked, so visits are not visible on a smoothed line.
  - y 0 to 60 is defensible (the MADRS range) but flattens the change; label "MADRS total (0 to 60)" is missing.
  - A single series still gets a legend.
- **Shots.** `madrs-by-week-*.png`.

### 9. `report-rater-accuracy-site`: rater accuracy by site "as recorded in the report"

- **Where.** Follow-up drawer. Built at `postdose/module.py:238-249`.
- **Question.** What blinding evidence goes into the FDA report?
- **Data.**
  - `{day, Site A, Site B, Site C}`, using **cumulative** `accuracy`, rows only on release days (23 rows, D+11 … D+61). `y_domain [0,1]`.
- **What is wrong.**
  - It uses a different metric (cumulative) and a different x range (D+11 to D+61) from the Dosing chart with almost the same title (rolling, D+1 to D+90). A reviewer comparing the two sees different Site B peaks (0.72 vs 1.0) with no explanation.
  - No expected line, no drift markers and no action marker, so the report's own chart omits the drift and the fix.
  - No intervals, although `accuracy_lo/hi` exist on every row.
  - The x axis starts at D+11 rather than D+1.
- **Shots.** `report-rater-accuracy-site-*.png`.

### Report stage

- `/trials/:id/report` (`components/projects/ReportPanel.tsx`) has **no visual at all**: status text and a sign-off list only (`report-page-*.png`).
- The signed FDA blinding report has no chart of blinding over time, no effect forest plot and no drift timeline. They live on the Follow-up drawer instead.

---

## Non-chart data visuals (brief)

- **`dosing-readouts` / `followup-readouts`.** `ReadoutGrid`, `shared/Readout.tsx:85`.
  - Big numbers with "before X → now Y" and an arrow.
  - The values sit at different vertical positions in each tile (19 / 0.3 / 100 / 49 not baseline-aligned) because the notes above differ in length (`dosing-readouts-predecision-1440-dark.png`).
  - The arrow tone is guessed by regex (`LOWER_BETTER`, Readout.tsx:12). "Reported vs expectancy-adjusted effect -6.41 → -2.95" shows a green up arrow, which implies the effect "improved" when it shrank.
  - The baselines are a mix of real-literature, simulation and assumption, with the provenance only in small notes.
  - Predose readouts (`Predose.tsx:121`) did not render on any of the "only=" stage views, so the predose KPIs (u, checklist) only show as the risk card and checklist.
- **`fda-checklist`.** `predose/FdaChecklist.tsx`.
  - Readout "0 / 8 → 4 / 8 items met" plus rows with a dot and "Present" or "Missing". Status is dot plus word (good).
  - The "0 / 8 →" part is tiny grey and easy to miss.
  - Shots: `fda-checklist-*.png`. The selector matched the wrapper, so the crop shows the risk card and the checklist side by side; the sticky glass nav overlaps the top edge.
- **`version-history`.** `LedgerTable` from `BlindingSection.tsx` (v1 to v6, "D−1", first changed line). There is no risk column, which is where the per-fix u above belongs. Shots: `version-history-*.png`.
- **Recruitment ads** (`RecruitmentAds.tsx`). The Flesch score readout (79.6 / 84.1 / 72.9) plus "3 / 3 checks" with dots. Fine; the number has a band word.
- **Screening ledger and fairness table** (drawers). See 2.
- **Dosing tables** (drawer, from `dosing/module.py:240-249`):
  - Drift timeline: Day, Event, Detail.
  - Alerts.
  - Blinding by rater: Guesses, Accuracy, "95% interval" text, Drift score.
  - Check-ins, debriefs, missing data, literature.
  - The "Blinding by rater" table is the only place a Wilson interval is shown.
- **Stepper and TrialClock** (`stepper/VerticalStepper.tsx`, `projects/TrialClock.tsx`). Status dots plus words; not a data chart.
- **Studio `EffectChart`** (`components/studio/EffectChart.tsx`) is outside the trial walk and was not audited here.
