# Statistician review of the visuals pass

Reviewer: independent statistician (did not build any chart). Scope: statistical honesty only, not style.
Branch `feat/visuals`, diff `7351ca8..HEAD -- frontend/src unblind backend`.

How I checked:
- I ran the app on my own (API 8721, vite 5721, store `/tmp/vis-stat/store`).
- Trial A (seed 42, 500 applicants, manual approvals) was walked to day 50 and then to day 90.
- Trial B was walked to day 47, which leaves the Site B drift approval pending. I took the screenshot `/tmp/vis-stat/cusum-d47-pending.png` there.
- I compared the record (`blinding_metrics`, `alerts`, `actions`, `outcomes`, `followups`, `protocol_versions`, `design_review`, `report`) with what each chart computes.
- For the Studio charts I used the stored report `tests/e2e/visuals/studio_report_NCT03866174.json`.

## Findings

| id | severity | chart | what is wrong | evidence | exact fix |
|---|---|---|---|---|---|
| S-1 | major | cusum-site | **The simulated ground truth acts as an oracle for the human approval.** "Drift began (simulated) D28" and "19 days from simulated drift start to alert" appear as soon as any drift alert exists at the planted site, including while that alert's approval is still pending. The reviewer deciding "Move Site B raters to remote" is shown that the alert is a true positive. The reverse also leaks: an alert at any other site gets no marker, so a missing marker tells the reviewer it is a false alarm. No future data leaks: the day is only exposed once `rec.day >= 28`. Allocation does not leak either: the payload is only site and day. | Trial B at day 47: `/state` gives `simulated_truth = {drift_site: Site B, drift_onset_day: 28}`. Pending approval "Move Site B raters to remote (central) assessment", day 47. The chart shows the marker and the callout (`/tmp/vis-stat/cusum-d47-pending.png`). Code: `CusumChart.tsx:177` (`simDay` only checks that the site matches `flaggedSite` and `day <= today`, not the alert status). | Draw the marker and the delay callout only once the alert is decided (`alert.status` in `action_approved`, `resolved`, `dismissed`, `superseded`), or only after close (`state.phase === "closed"`). Apply the same gate on the server in `orchestrator.py:343` `simulated_truth()`: return None while the site has an `open` rater_drift alert, or until `rec["day"] >= CLOSE_DAY`. Keep the "simulated" label and footnote, which are clear. |
| S-2 | minor | cusum-site (API) | `GET /state` sends the planted drift site and day from day 28, 19 days before the monitor detects it. Nothing draws it before an alert, but the ground truth is in the payload any client sees during the blinded monitoring period. | `orchestrator.py:352` gates only on `rec["day"] < day`. Trial A: day 50 state shows the field. By that code it is sent on every day from 28 onwards, i.e. before the alert on day 47. | Same server gate as S-1: expose it only after the alert is decided, or after close. |
| S-3 | major | rater-accuracy-by-rater | **The title "R-B2 drives the Site B alert (5 of 5 correct)" claims more than the data supports.** (1) `per_rater` covers 5 of the 15 decisive guesses behind the alert (15 of 15 since onset). R-B1 is missing from `per_rater` only because its post-onset guesses arrived in a batch whose window began on day 21, before the onset on day 28. (2) n = 5 is below `WILSON_MIN_N` = 8, so no interval exists. (3) The simulator plants the drift at site level for every rater at Site B (`world.py:166`), so "drives" is factually wrong for this synthetic trial. The panel colouring repeats the claim: R-B2 is orange ("named in a drift alert") and R-B1 is violet ("no alert"), because `flagged` is true only for raters listed in `per_rater`. | Alert evidence: `correct_since_onset 15, n_since_onset 15, per_rater {R-B2: 5/5}`. R-B1 batch on day 34 covers days 21 to 34: 3 of 5. Site B batches since onset cover days 28-31, 32-37 and 38-47, each 5 of 5. Code: `SiteSmallMultiples.tsx:440` (title), `:456` (flagged). Screenshot: `after/rater-accuracy-by-rater-1440-light.png`. | Title: `Site B raters flagged for drift on day 47 (15 of 15 correct since estimated onset); per rater, R-B2 5 of 5 (too few for an interval)`. List every rater in `per_rater` with its n, and say that guesses in batches that started before the onset are not attributed. Colour the panels of every rater at the alerted site the same way, or label a rater "Named in alert evidence (n = 5)" rather than implying the other raters are cleared. |
| S-4 | major | blinding-meter | **The "Synthetic" note is missing though the value comes from synthetic data.** `ReportView.tsx:134` hard-codes `synthetic={false}`. When u is imputed, it comes from the design model fitted on the calibration set, and here that set is the SYNTHETIC calibration. | Report: `u.status imputed`, note "IMPUTED from design ... fitted on 15 trials with observed blinding". `calibration: "SYNTHETIC calibration set"`. `design_model: "fitted on 15 trials ..."`. Screenshot `after/blinding-meter-1440-light.png`: no Synthetic note. | Use `synthetic={synthetic && bl.status === "imputed"}` with the note text "Synthetic calibration" (ChartFrame `tag`), or always show it when the calibration is synthetic and u is imputed. |
| S-5 | major | blinding-meter | **The title states a verdict for an imputed estimate whose own uncertainty spans two of the three words.** "Largely unblinded: u 0.67 (imputed from design)". The ± 1 SD range is 0.36 to 0.98; ± 2 SD covers almost the whole 0 to 1 scale. The subtitle admits the spread, but the takeaway does not. | u 0.669, u_sd 0.312, status imputed (report facts). `BlindingMeter.tsx:36-38`. | When the ± 1 SD range crosses a cut-off, title it `Imputed u 0.67 (± 1 SD 0.36 to 0.98): partly to largely unblinded`. Keep the single word only when the whole ± 1 SD range sits in one band and u is observed. |
| S-6 | major | blinding-meter vs risk-scale | **Two different threshold systems are drawn for the same quantity u.** The meter draws cut-offs at 0.25 and 0.55, defined only in the frontend (`report.ts:188` `BLINDING_BANDS`); nothing in `unblind/` defines them. The pre-dose risk-scale draws the backend's bands at 0.35 and 0.6 (`predose/agents.py:369`). So u = 0.55 is "Largely unblinded" in Studio and "Medium" on the Pre-dose page. | `report.ts:188-192`; `agents.py:369`. Screenshots `after/blinding-meter-1440-light.png` (ticks 0.25 and 0.55) and `after/risk-scale-1440-light.png` (ticks 0.35 and 0.6, "u 0.55 Medium band"). | Use one source: either draw the backend's 0.35 and 0.6 bands (Low, Medium, High) on the meter, or drop the drawn cut-offs and keep the word in text only, with a note saying it is a display convention, not a model threshold. Do not draw 0.25 and 0.55 as rules. |
| S-7 | minor | effect-forest | The single "Synthetic" note covers the whole plot, but the Reported row is the published trial's own result (MD −12.3, CI −17.5 to −7.2, converted to g). Only the calibration behind the adjustment is synthetic. | `ReportView.tsx:103` `synthetic={synthetic}` with the default note text "Synthetic". Screenshot `after/effect-forest-1440-light.png`. | Pass `tag="Synthetic calibration"` (the ChartFrame `tag` prop), as the readout tile already says. |
| S-8 | minor | design-fixes | (1) Feasibility weights are values from the assumption table (`model.py` `counterfactuals`: `feas.get(name, 0.7)` from priors), but the chart shows "feasibility 0.8" as if measured. (2) The ranking rests on a 0.002 g difference in bias reduction (0.084 vs 0.086). The counterfactual rows carry `u_sd` 0.31 and 0.21, which are not shown, so "ranks first" reads firmer than the model allows. (3) "cuts slightly more" is hard-coded and would be wrong for a large gap. | Counterfactuals in the report JSON; `FixesChart.tsx:28`. Screenshot `after/design-fixes-1440-light.png`. | Label the weight as "feasibility (assumed weight 0.8)". Add the footnote "Feasibility weights are assumptions, not data; the two changes differ by 0.002 g in expected bias reduction, well inside the model's uncertainty (u SD 0.31 and 0.21)". Compute the qualifier from the gap (for example "slightly" only when the gap is under 0.01 g) or drop it. |
| S-9 | minor | design-fixes | The x domain is forced to start at 0 (`niceTicks(0, max)`), so a negative expected bias (possible: `b*u - c*(1-central)`) would be drawn off the axis. The current data does not hit this. | `FixesChart.tsx:66`; `model.py:224-226`. | Domain `[min(0, all before/after), max(...)]`, with a "No bias" rule at 0 when the domain goes below 0. |
| S-10 | minor | generic fallback (ModuleChart) | With no `y_domain` in the payload, the y axis is `["auto","auto"]`, so a proportion or effect chart falling back here can get a truncated axis that exaggerates change. | `ModuleChart.tsx:144`. | Default to `[0, "auto"]` for non-negative data, and to a domain that includes 0 when any value is negative. |

## Passed

- **effect-forest (Studio)**
  - The axis includes 0, with a "No effect" rule.
  - "Favours control" and "Favours drug" are correct for g, where positive favours the drug.
  - The reported interval is g ± 1.96 × se_g, the same z as `model.correct`. It is labelled "from imputed SE", and the marker is hollow because it is imputed.
  - The adjusted value and interval are the report's own (−0.071, −0.753 to 0.61).
  - The bias connector equals reported minus adjusted (0.502 − (−0.071) = 0.573 = `correction.bias`).
  - "Interval crosses 0" is true. "u imputed" is flagged.
- **effect-readout:** "Imputed", "Awaiting human sign-off" and "Synthetic calibration" all match the report. The direction words come from the sign of the bias.
- **blinding-meter:** the bar is labelled ± 1 SD and "not a confidence interval" in the subtitle, the drawer and the footnote. The marker is hollow because u is imputed. The scale is the full 0 to 1. (Findings S-4 to S-6 still apply.)
- **design-fixes:** the before and after values, reduction, feasibility and score match the report's counterfactuals, and the order matches the report's ranking by score. No interval is invented.
- **risk-scale**
  - `design_history` rescoring reproduces the stored v1 (0.786, 0.705 g) and v6 (0.55, 0.472 g) exactly. I re-ran `codesigner.risk(parser._rules(text))` on all six versions.
  - Versions in between are marked "rescored, rule-based parse" in the drawer.
  - ± 1 SD is labelled "not a confidence interval".
  - The 0.35 and 0.6 bands come from `agents.py:369`.
  - "low-dose comparator moved it most (−0.22)" is correct: 0.786 to 0.57, the largest step.
  - The note "v2 to v4 did not change u; v2 moved expected bias 0.705 to 0.674" is correct.
- **screening-funnel:** reviewed in the code only. Counts are computed from `applicants[].screening`, `enrolled[]` and `recruitment.funnel`, and shares are against the right denominators. The Synthetic note is on. I did not recount independently.
- **rater-accuracy-site**
  - The rolling counts the frontend rebuilds reproduce the record's `rolling_accuracy` on all 79 released rater rows at day 90 (0 mismatches). The reset rule matches `monitor.py:106-107`.
  - Wilson matches `stats.py`. For example, 15 of 15 gives 0.796 to 1, the same as the alert's `ci_since_onset`. It is drawn only where n >= 8, and smaller n gets a hollow marker.
  - Coin flip 50% and "Alarm reference 60%" (P0) are correctly placed and labelled.
  - The title "Site B raters flagged for drift on day 47; remote raters approved day 48" matches the alert (day 47, `action_day` 48).
  - Suppressed rows are excluded. The axis is 0 to 100%. Steps are `stepAfter`.
- **rater-accuracy-by-rater:** the same mechanics as above all pass. Only the title and the flag colouring fail (S-3).
- **cusum-site**
  - Scores are the record's `cusum`.
  - The alarm line 3.5 comes from the row `threshold`.
  - "Detected D47" is the first release >= H (day 37 is 3.484 < 3.5, day 47 is 5.226).
  - The estimated onset of 28 matches `cusum_onset`.
  - The reset is a dotted drop labelled "Reset after action", and the drawer marks it "Reset after action (display)", so it is not drawn as a measurement.
  - The y axis starts at 0. No coin-flip line is drawn.
  - The simulated marker is clearly labelled "(simulated)", with a footnote explaining it is synthetic ground truth. Only its timing fails (S-1).
- **participant-accuracy-site:** uses the record's own cumulative Wilson bounds, only where n >= 8. It is labelled information only, with no alarm line.
- **effect-estimates (post-dose)**
  - Values match the view at day 90: Reported −6.41 (−9.56 to −3.25); Cross-trial −2.95 (−7.22 to 1.33).
  - The axis includes 0. "Negative favours the drug" is read from the payload's sign convention (`report.effect.sign` = "drug minus control; negative favours the drug").
  - "Favours drug" sits on the left.
  - The planted truth −4.0 is labelled "simulated" and matches `WorldConfig.true_effect` = 4 at week 6 (the ramp is complete by day 21).
  - Estimates that are not estimable are footnoted with the vault reason.
- **madrs-by-week:** the frontend n, mean and SD match my recount at day 90 (week 1: n 48, mean 24.5, SD 7.3; weeks 3, 6 and 8: n 49; week 12: n 18 with 31 visits after close, hollow and footnoted). Whiskers are labelled "± 1 SD of individual scores, not an interval". Arms are pooled, so nothing about allocation is revealed. The axis is 0 to 60, units are stated, and there is no threshold.
- **report-rater-accuracy-site:** cumulative values and bounds come from the record and are checked against the view. Bands appear only where n >= 8. The title peak is taken only from points with n >= 8. Coin flip 50% is drawn.
- **version-history:** a ledger table, not a chart. It has no statistical content to check.
- **generic fallback:** step lines, threshold lines only from payload values, and the Synthetic note taken from the title (apart from S-10).
