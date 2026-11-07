# Synthetic recovery: can UNBLIND find a planted drug effect?

**SYNTHETIC DATA. These numbers are not real-world performance.** Every trial below is simulated by
`unblind.synthetic.make_trials` (rows labelled `provenance=SYNTHETIC`). They test the statistics, not the agents.

Setup: true effect at zero unblinding `true_g = 0.35`, planted bias slope `b_true = 0.6` per unit of
unblinding, on-site raters inflate g by `r_onsite = 0.10` (truth is the central-rater, zero-unblinding effect; the estimator is the fitted a + c), 35% of trials report blinding data. 300 replicate
meta-analyses per row, each with its own seed. Bias, RMSE and coverage are measured against `true_g` and computed
only over fits that succeeded. "± MC 95%" is Monte Carlo error from the finite number of replicates.

* **Naive pooled mean (baseline)**: DerSimonian-Laird random-effects mean of reported g over all k trials, ignoring
  blinding. What a standard meta-analysis would report.
* **UNBLIND primary**: `model.fit_metareg` intercept, trials with observed blinding only (about 0.35 x k trials).
* **UNBLIND sensitivity**: same, adding trials whose unblinding was imputed from design.

## Main scenarios

| scenario | k | estimator | mean bias (± MC 95%) | median bias | RMSE | 95% CI coverage (± MC 95%) | median CI width | fits failed |
|---|---|---|---|---|---|---|---|---|
| expectancy | 15 | Naive pooled mean (baseline) | +0.428 ± 0.007 | +0.427 | 0.432 | 0% ± 0 | 0.23 | 0% |
| expectancy | 15 | UNBLIND primary (observed u) | +0.052 ± 0.090 | -0.011 | 0.644 | 100% ± 0 | 2.61 | 35% |
| expectancy | 15 | UNBLIND sensitivity (+ imputed u) | -0.035 ± 0.027 | -0.015 | 0.244 | 99% ± 1 | 1.14 | 0% |
| expectancy | 30 | Naive pooled mean (baseline) | +0.431 ± 0.005 | +0.434 | 0.433 | 0% ± 0 | 0.17 | 0% |
| expectancy | 30 | UNBLIND primary (observed u) | -0.017 ± 0.032 | -0.014 | 0.284 | 99% ± 1 | 1.26 | 1% |
| expectancy | 30 | UNBLIND sensitivity (+ imputed u) | -0.055 ± 0.022 | -0.041 | 0.200 | 99% ± 1 | 0.75 | 0% |
| expectancy | 60 | Naive pooled mean (baseline) | +0.432 ± 0.004 | +0.432 | 0.433 | 0% ± 0 | 0.12 | 0% |
| expectancy | 60 | UNBLIND primary (observed u) | -0.005 ± 0.019 | -0.000 | 0.167 | 98% ± 2 | 0.73 | 0% |
| expectancy | 60 | UNBLIND sensitivity (+ imputed u) | -0.057 ± 0.013 | -0.050 | 0.129 | 97% ± 2 | 0.47 | 0% |
| reverse_causation | 15 | Naive pooled mean (baseline) | +0.062 ± 0.006 | +0.061 | 0.082 | 77% ± 5 | 0.20 | 0% |
| reverse_causation | 15 | UNBLIND primary (observed u) | -0.099 ± 0.101 | -0.101 | 0.748 | 100% ± 0 | 3.23 | 31% |
| reverse_causation | 15 | UNBLIND sensitivity (+ imputed u) | -0.059 ± 0.027 | -0.043 | 0.247 | 99% ± 1 | 1.07 | 0% |
| reverse_causation | 30 | Naive pooled mean (baseline) | +0.065 ± 0.004 | +0.062 | 0.075 | 60% ± 6 | 0.14 | 0% |
| reverse_causation | 30 | UNBLIND primary (observed u) | -0.158 ± 0.051 | -0.114 | 0.476 | 96% ± 2 | 1.48 | 0% |
| reverse_causation | 30 | UNBLIND sensitivity (+ imputed u) | -0.081 ± 0.023 | -0.069 | 0.221 | 94% ± 3 | 0.77 | 0% |
| reverse_causation | 60 | Naive pooled mean (baseline) | +0.064 ± 0.003 | +0.065 | 0.070 | 32% ± 5 | 0.10 | 0% |
| reverse_causation | 60 | UNBLIND primary (observed u) | -0.150 ± 0.024 | -0.151 | 0.261 | 91% ± 3 | 0.83 | 0% |
| reverse_causation | 60 | UNBLIND sensitivity (+ imputed u) | -0.083 ± 0.017 | -0.079 | 0.174 | 89% ± 3 | 0.55 | 0% |
| confounded | 15 | Naive pooled mean (baseline) | +0.339 ± 0.009 | +0.336 | 0.349 | 3% ± 2 | 0.32 | 0% |
| confounded | 15 | UNBLIND primary (observed u) | -0.325 ± 0.075 | -0.408 | 0.626 | 97% ± 2 | 3.01 | 34% |
| confounded | 15 | UNBLIND sensitivity (+ imputed u) | -0.525 ± 0.032 | -0.488 | 0.595 | 74% ± 5 | 1.39 | 0% |
| confounded | 30 | Naive pooled mean (baseline) | +0.331 ± 0.006 | +0.335 | 0.335 | 0% ± 0 | 0.23 | 0% |
| confounded | 30 | UNBLIND primary (observed u) | -0.444 ± 0.047 | -0.401 | 0.606 | 80% ± 5 | 1.29 | 0% |
| confounded | 30 | UNBLIND sensitivity (+ imputed u) | -0.514 ± 0.022 | -0.513 | 0.549 | 30% ± 5 | 0.83 | 0% |
| confounded | 60 | Naive pooled mean (baseline) | +0.331 ± 0.005 | +0.330 | 0.334 | 0% ± 0 | 0.16 | 0% |
| confounded | 60 | UNBLIND primary (observed u) | -0.454 ± 0.021 | -0.451 | 0.491 | 35% ± 5 | 0.72 | 0% |
| confounded | 60 | UNBLIND sensitivity (+ imputed u) | -0.551 ± 0.016 | -0.547 | 0.568 | 2% ± 1 | 0.51 | 0% |

## What this means

When its assumptions hold (expectancy), the naive meta-analysis overstates the drug effect by +0.43 g and its intervals almost never contain the truth (0% coverage at k=60). The UNBLIND primary estimate (a + c) is close to unbiased (-0.005 g; sensitivity fit -0.057 g) and contains the truth 98% of the time, but its intervals are several times wider because the fit extrapolates to zero unblinding, and with 15 trials its RMSE (0.64) is worse than the naive one (0.43): too few trials report blinding for the correction to pay for its own noise. Under reverse causation we planted no expectancy bias at all, so the naive mean is nearly right (bias +0.064, the averaged on-site rater inflation) and the correction over-subtracts (bias -0.150, coverage 91%): this is the method's key failure mode, and why the report calls the corrected value a conservative bound. Under cross-trial confounding both are wrong in opposite directions (naive +0.33, primary -0.45), and the correction is the worse of the two because the confounder lines up exactly with blinding quality. With 15 trials only about 5 report blinding, so the primary fit fails in 35% of runs. These are synthetic results: they show the method works when its assumptions hold and how it breaks when they do not. They are not real-world performance.

## Stress tests (k = 30, local wrappers in `eval/synthetic_recovery.py`)

* `noisy_guess`: the expectancy scenario, but observed unblinding is *measured* from a binomial count of correct
  guesses instead of being the exact true value. `make_trials` gives the model noiseless u, which flatters it.
* `mixed`: reverse causation **plus** a real expectancy bias of 0.3 x u. Arguably the most realistic case:
  the naive mean is too high and the correction too low, so the truth lies between them.

| scenario | k | estimator | mean bias (± MC 95%) | median bias | RMSE | 95% CI coverage (± MC 95%) | median CI width | fits failed |
|---|---|---|---|---|---|---|---|---|
| noisy_guess | 30 | Naive pooled mean (baseline) | +0.435 ± 0.005 | +0.431 | 0.438 | 0% ± 0 | 0.17 | 0% |
| noisy_guess | 30 | UNBLIND primary (observed u) | +0.070 ± 0.035 | +0.062 | 0.320 | 97% ± 2 | 1.22 | 0% |
| noisy_guess | 30 | UNBLIND sensitivity (+ imputed u) | -0.006 ± 0.021 | +0.000 | 0.182 | 98% ± 2 | 0.72 | 0% |
| mixed | 30 | Naive pooled mean (baseline) | +0.296 ± 0.005 | +0.297 | 0.299 | 0% ± 0 | 0.16 | 0% |
| mixed | 30 | UNBLIND primary (observed u) | -0.158 ± 0.049 | -0.133 | 0.459 | 98% ± 1 | 1.50 | 1% |
| mixed | 30 | UNBLIND sensitivity (+ imputed u) | -0.094 ± 0.027 | -0.086 | 0.254 | 95% ± 2 | 0.84 | 0% |

## Scenario notes and caveats

* In `confounded`, trials with a non-inert comparator have a true effect 0.25 lower (0.10 instead of 0.35). The
  table scores against 0.35, the effect in the inert-placebo population. The trial-averaged true effect is about 0.25.
  Either way the correction lands far below both, because extrapolating to zero unblinding means extrapolating into
  the low-efficacy designs.
* In `reverse_causation`, `make_trials` adds `0.5 x g_i` to every trial's u, pushing about 19% of trials to the
  ceiling u = 1. That compresses the u range and makes the over-subtraction smaller than an unclipped version would show.
* In `reverse_causation` the sensitivity fit is less biased than the primary fit. That is not a virtue of imputation
  in general: imputed u comes from design only, so it carries none of the efficacy-driven part of u and acts like an
  instrument. It only helps if the design model is right.
* The rater term `c` is fitted when raters vary and the reported estimate is a + c. The naive mean averages over
  rater placement, which is why its bias in `reverse_causation` is about +0.065 (65% on-site raters x 0.10) rather than zero.
* Coverage of the UNBLIND intervals is above 95% when unbiased because `fit_metareg` uses a Knapp-Hartung scale
  floored at 1 (conservative). High coverage under reverse causation reflects wide intervals, not a correct centre.
* Runtime 5 s. Reproduce with `python eval/synthetic_recovery.py`.
