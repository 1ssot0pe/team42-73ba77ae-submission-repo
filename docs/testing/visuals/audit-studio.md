# Visuals audit: Evidence studio and Home (before)

Auditor: AUDIT-STUDIO. Branch `feat/visuals`. Run on 2026-11-08 against NCT03866174, local stack (API :8602, Vite :5602),
no `GEMINI_API_KEY` (rule-based mode). The live pipeline fetched from ClinicalTrials.gov without trouble (about 37 s).
The UI's own run path was also exercised end to end (`progress-steps-1440-light.png`, then the chart rendered).

Screenshots: `docs/testing/visuals/before/<id>-{1440-light,1440-dark,390}.png`. Dark mode is `color_scheme=dark` plus the
app's theme preference (`localStorage["unblind.theme"]="dark"`, which sets `<html data-theme="dark">`). 390 px is rendered at 2x DPR.
The report was seeded into `parallax.analyses.v1` and opened as `/studio?a=audit1`, so all three settings show the same report.
Other files in `before/` (fda-checklist, risk-scale, screening-funnel, version-history) belong to the other auditor.

**Home has no charts or data visuals.** It is a headline, two door links and recent-work lists (`pages/Home.tsx:59-116`).
Reference shots only: `home-page-{1440-light,1440-dark,390}.png`.

---

## What the Studio receives (NCT03866174)

`POST /api/evidence/run` (`backend/main.py:268`) returns `unblind/pipeline.py` `Report.to_json()`. The frontend reads it in
`components/studio/report.ts` (`effect()` at :152, `blinding()` at :171, `fixes()` at :183).

| Field | Value | Status / note |
|---|---|---|
| `facts.effect.value` | `{kind:"md", est:-12.3, lo:-17.5, hi:-7.2}` (MADRS change, psilocybin vs niacin, LS-means difference) | observed, quote audit pass |
| `facts.primary_endpoint` | MADRS, week 6 (Day 43) | observed |
| `facts.enrollment` | 347 (registry quote "Enrollment: 347") | observed. **Verify** (see below) |
| `facts.arm_ns` | [173, 174] | **imputed**: enrolment split evenly |
| `facts.g` | **0.502** | **imputed**. Note: "MD -12.3 (CI -17.5 to -7.2) -> SD 24.47 via arm sizes 173/174 (imputed); sign flipped because lower MADRS is better" |
| `facts.se_g` | 0.109 | imputed (from CI width / 3.92 and the imputed arms) |
| `facts.u` | 0.669 | **imputed** from design (comparator active_placebo, prior exposure unknown) |
| `facts.u_sd` | 0.312 | imputed |
| `facts.guess_acc_participants`, `guess_acc_raters` | null | unknown (blinding assessment was planned, no result found) |
| `facts.comparator_type` / `rater_placement` | active_placebo / central_remote | observed |
| `correction` | `bias 0.573, corrected -0.071, lo -0.753, hi 0.610, sd 0.348, extrapolated false, u_status "imputed"` | |
| `fit_primary` (meta-regression) | k=15 trials with observed blinding, tau2 0, u range 0.34 to 0.83; intercept 0.213 [-0.142, 0.568]; **u slope 0.857 [0.225, 1.489]**; central -0.031 [-0.324, 0.261]; reference effect (u=0, central) 0.181 [-0.262, 0.625] | |
| `fit_sensitivity` | k=36 (incl. imputed blinding); u slope 0.591 [0.147, 1.036]; reference effect 0.269 [-0.052, 0.59] | |
| `calibration` | "SYNTHETIC calibration set (data/calibration_synthetic.csv). Not real-world performance." | |
| `status` | "AWAITING HUMAN SIGN-OFF: instrument reading, not a verdict" | **not rendered anywhere in the Studio** |
| `counterfactuals` | low-dose comparator: bias 0.573 to 0.489 (reduction 0.084, feasibility 0.8, score 0.068); psychedelic-naive: 0.573 to 0.488 (0.086, 0.6, 0.051) | |

**Units and sign:** Hedges' g, standardised mean difference. Positive favours the drug. The pipeline flips the MD sign
because lower MADRS is better (`pipeline.py:98-121`). If a paper reports a standardised effect directly, it is "used as
reported (assumes positive = favours the drug)".

**Intervals:**
- Reported interval: not in the report. The frontend builds it as `g ± 1.96·se_g` = **0.29 to 0.72** (`report.ts:158-159`).
  It is a real 95% CI only to the extent that `se_g` is right, and `se_g` rests on the imputed 173/174 arms.
- Adjusted interval: from the backend (`unblind/model.py:187-200`). `corrected = g − b·u` (here `0.502 − 0.857·0.669 = −0.071`),
  with `var = se_g² + u²·se_b² + b²·u_sd²` (+ the central-rater term when raters are on site). That gives **−0.75 to 0.61**.

**What the adjusted estimate assumes:** (1) a linear meta-regression of g on unblinding u across 15 trials, here
**synthetic**; (2) this trial's u = 0.669, **imputed from design**, not observed; (3) the zero point is u = 0 with central
blinded raters, the extrapolation region where the intercept is least certain; (4) tau² = 0, so no between-trial
heterogeneity term; (5) the reverse-causation caveat: improvers guess "drug", so the corrected value is a conservative
bound (from `limitations`).

**Data-quality flag (not a chart bug, but it drives the chart):** enrolment 347 comes from the registry record. The −12.3
(−17.5 to −7.2) MADRS difference matches Raison et al., JAMA 2023, which analysed about 104 participants (about 51/53).
That figure is from memory; verify it. With those arms, the same MD gives g ≈ 0.91, not 0.50. If so, the reported dot
sits about 0.4 g too low and the adjusted estimate moves up by the same amount.

---

## Charts and data visuals

### 1. `effect-forest`: reported vs bias-adjusted forest plot (the main chart)
- **Where:** `/studio?a=<id>`, `components/studio/EffectChart.tsx:36-117`, mounted at `components/studio/ReportView.tsx:89`.
  Inline SVG, not Recharts. It does not use `chartTheme.ts` or `ChartFrame`.
- **Question it should answer:** "How much of this trial's reported benefit survives once functional unblinding is
  accounted for, and is the adjusted effect still distinguishable from no effect?"
- **Data:** `Effect{reported 0.502, reportedLo 0.288, reportedHi 0.716, adjusted −0.071, adjustedLo −0.753, adjustedHi 0.610}`.
  `note = "Synthetic calibration"`.
- **Screens:** `effect-forest-1440-light.png`, `effect-forest-1440-dark.png`, `effect-forest-390.png`.
  In context: `effect-readout-*.png`, `studio-report-page-*.png`.
- **What is wrong:**
  - Zero is always in the domain (`EffectChart.tsx:49` includes `0`), and there is a dashed null line at 0 (`:80`). It has
    **no on-chart label**: the meaning ("dashed line no effect") is only in the caption sentence.
  - **No direction labels on the axis.** "Positive favours the drug" appears only in the paragraph above
    (`ReportView.tsx:84`). An FDA reviewer reading the figure alone cannot tell the direction. It needs
    "← favours placebo | favours psilocybin →" under the axis.
  - **No numbers on the chart.** The estimates and CIs are only in the readout above. An exported or copied figure loses them.
    Direct value labels at the row end are missing (for example "0.50 [0.29, 0.72]").
  - **Interval wording and provenance.** The caption says "95% range", not "95% CI". The reported interval is
    frontend-derived from an imputed SE, and the chart draws it the same as an observed one. There is no hollow marker or
    "imputed" mark on the reported row, although `reportedStatus === "imputed"`.
  - **The bias shift is not drawn.** Estimated bias 0.57 is a readout tile only. An arrow or connector from reported to
    adjusted would show what the tool actually did.
  - **Synthetic / sign-off labelling is too weak.** "Synthetic calibration" is a muted caption line. There is no
    "Synthetic" tag in the chart header (unlike `ChartFrame` in `shared/ChartParts.tsx:46`). `report.status` ("AWAITING
    HUMAN SIGN-OFF") is never shown. The adjusted row looks just as authoritative as the reported row.
  - **No reference marks:** no `fit_primary.reference_effect` (0.18 [−0.26, 0.63]) and no sensitivity-fit adjusted estimate
    (with the k=36 slope 0.591 it would be 0.502 − 0.591·0.669 ≈ 0.11), so the robustness of the adjustment is invisible.
  - The legend duplicates the direct row labels. It is harmless, but it costs a line at 390. Colours (violet vs ember) are
    not the only cue, because the rows are labelled.
  - **No tooltip or `<title>`.** The SVG has a good `aria-label`: "Forest plot of Hedges' g. Reported 0.50 (0.29 to 0.72),
    bias-adjusted −0.07 (−0.75 to 0.61)." The individual marks are not focusable.
  - **Ticks:** "0" vs "−1.0"/"0.5" have inconsistent decimals (`:56`). That is minor.
  - **Dark mode:** renders correctly (`effect-forest-1440-dark.png`). The row-label halo stroke uses `--color-eggshell`,
    which adapts.
  - **390 px:** row labels move above the intervals, with no clipping (`effect-forest-390.png`). The caption wraps to 3 lines.

### 2. `meta-regression` (missing visual)
- There is **no chart of the meta-regression** that justifies the correction: g vs u across the calibration trials, with
  the fitted slope and this trial's imputed u = 0.669 ± 0.31 marked. The report carries only the coefficients
  (`fit_primary`, `fit_sensitivity`), not the per-trial points. The points exist in `data/calibration_synthetic.csv` (36
  rows: `g, se_g, u, u_sd, u_status, central, comparator_type`), all `SYNTHETIC`. An FDA reviewer will ask for exactly
  this plot. Exposing it needs a backend field, which is out of scope for this audit.

### 3. `effect-readout`: three big-number tiles
- **Where:** `ReportView.tsx:61-87`. Screens: `effect-readout-{1440-light,1440-dark,390}.png`.
- **Data:** Reported 0.50 (0.29 to 0.72), Bias-adjusted −0.07 (−0.75 to 0.61), Estimated bias 0.57.
- **What is wrong:** there is no unit on the tiles ("g" appears only in the paragraph). "Estimated bias 0.57" has no sign
  meaning (inflation toward the drug). The "imputed" caveat is a trailing sentence, not attached to the Reported tile.
  Nothing marks the adjusted tile as synthetic or awaiting sign-off.

### 4. `blinding-meter`: "How blinded it was" (not actually a meter)
- **Where:** `ReportView.tsx:94-126`. Screens: `blinding-meter-{1440-light,1440-dark,390}.png`.
- **Data:** u = 0.67 ± 0.31 (imputed), tone "Largely unblinded" (thresholds 0.25 / 0.55 hard-coded in `report.ts:177-180`),
  participant and rater guess accuracy "Not reported".
- **What is wrong:** it is a number and a coloured dot, with no 0 to 1 scale. The ± is an SD, not an interval, and is not
  labelled as such. ±0.31 spans "partly" to "largely" unblinded, but the verdict word is stated flatly. The thresholds are
  invisible. The tone dot is red, but the word carries the meaning, so this is not colour-only. A 0 to 1 bar with the
  estimate, the ±1.96·SD band and the threshold bands would answer the question directly.

### 5. `source-facts`: fact table with status badges
- **Where:** `ReportView.tsx:128-148`. Badges come from `FactDrawer.tsx:17-35`. Screens: `source-facts-*.png`.
- **What is wrong:** the reported effect uses an ASCII hyphen ("Mean difference -12.3 (-17.5 to -7.2)",
  `report.ts:104-107`), while the readouts use a Unicode minus, so the two are inconsistent. The MD has no unit or
  direction ("MADRS points, negative = more improvement"). The badge column is right-aligned far from the values at 1440.
  The status dots are green for Observed, and the word is present. The quote audit ("checked against the source") is
  only visible inside the drawer.

### 6. `fact-drawer`: quote and audit badge panel
- **Where:** `FactDrawer.tsx:37-101`. Screens: `fact-drawer-{1440-light,1440-dark,390}.png` (opened on Primary endpoint).
- Fine as a document. The audit pass is a muted inline phrase, not a badge. There are no issues for this pass.

### 7. `design-fixes`: ranked counterfactual list
- **Where:** `ReportView.tsx:150-169`. Screens: `design-fixes-*.png`.
- **What is wrong:** it is headed "best first", but the shown reductions read 0.084 and then 0.086. The ranking uses
  `score = reduction × feasibility` (0.068 vs 0.051), and feasibility is never shown, so it looks mis-sorted.
  Before/after expected bias (0.573 to 0.489 / 0.488) is available but not shown. The units ("g") are missing.
  A small dot plot (before vs after per lever) would fit here.

### 8. `studio-mode-badge` and `progress-steps`
- `Studio.tsx:177-182` (AI assistance on / Rule-based mode, status dot plus word). Screens: `studio-mode-badge-*.png`.
- `ProgressSteps.tsx` (timer-driven, says so honestly). Screen: `progress-steps-1440-light.png`.
- There are no data issues here.

## Cross-cutting
- The Studio does not use the shared chart system (`chartTheme.ts`, `ChartFrame`, "Synthetic" tag). EffectChart has its
  own CSS (`styles/studio.css:94-106`).
- "Synthetic" and "awaiting sign-off" provenance is the biggest presentation risk. The calibration is synthetic and u is
  imputed, so the adjusted −0.07 is a method demo. Yet the readout and chart present it with the same weight as the
  observed MD.
- Dark mode and 390 px are visually sound for everything in the Studio. There are no overflow or contrast failures in the
  screenshots.
