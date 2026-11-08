# Drift detection evaluation (SYNTHETIC)

20 simulated 90-day trials per scenario (seeds 0-19), real Master, World and dosing module. Planted truth: Site B (Manchester) raters start sitting in on sessions from day 28; rater accuracy about 0.59 before, about 0.89 after (world.py).

Detector: batched Bernoulli CUSUM, p0=0.6, p1=0.85, H=3.5, alarms per site. H chosen on calibration seeds 100-129, not on the reported seeds. The vault releases only batches of 5 or more guesses.

## Main result: 72 participants, 3 sites, 2 raters per site (plan scale)

| Rule | Drift detected | Median delay (days) | Delay IQR | False alarms per trial, no drift |
|---|---|---|---|---|
| CUSUM (live agent) | 18/20 | 13.5 | 9.0 to 20.0 | 0.3 |
| Wilson interval rule | 9/20 | 25 | 15.0 to 30.0 | 0.0 |
| End-of-trial check only | 14/20 | 62 | n/a | 0.0 |

CUSUM false alarms at other sites (or before onset) in drift runs: 0.15 per trial. Onset estimate error (agent's change-point vs planted day 28): median -0.5 days.

After a human approves remote raters: drift confirmed stopped in 16 of 20 trials; in 2 more, the last rater visits came before two post-action batches could confirm it; re-alerts 0. Pooled Site B (Manchester) rater accuracy after the action: 166 of 288 (58%, 95% interval 52% to 63%).

Operations (mean per trial): checkin completion pct 99.6, debriefs structured 72.0, adverse events captured 11.7, rater contact cues 6.2, primary lock day 63.0.

## Sensitivity: 24 participants, 3 sites, 1 rater per site (stub pre-dosing scale)

CUSUM detected 1/20 (median delay 22 days), false alarms per no-drift trial 0.0; end-of-trial check detected 2/20. Small trials produce too few rater guesses after onset for the vault to release, so drift cannot be confirmed while protecting allocation. More raters' guesses (or more participants per site) buy earlier detection.

## Limits

Synthetic data with one planted failure mode. The drift size is an assumption of the simulator. A released batch at 0% or 100% accuracy still reveals the arms of the people in it; adding noise in the vault is the next step. Auto-approval in run C stands in for a human deciding the same day.

## Threshold calibration (seeds 100-129, CUSUM, plan scale)

Rule: lowest false-alarm rate among thresholds that missed no drift (a false alarm costs one human review; a missed drift costs the trial).

| H | Median delay | Missed | False alarms per trial, no drift | Other sites, drift runs |
|---|---|---|---|---|
| 2.0 | 9.0 | 4 | 0.867 | 0.7 |
| 2.5 | 15 | 1 | 0.467 | 0.333 |
| 3.0 | 15.0 | 0 | 0.233 | 0.133 |
| 3.5 | 15.0 | 0 | 0.133 | 0.1 |
| 4.0 | 15 | 1 | 0.1 | 0.067 |
| 4.5 | 20.0 | 2 | 0.067 | 0.033 |
| 5.0 | 20 | 5 | 0.033 | 0.0 |
| 5.5 | 20 | 7 | 0.033 | 0.0 |
| 6.0 | 25 | 7 | 0.0 | 0.0 |
