"""Pure statistics for the blinding monitor. No allocation, no I/O.

Why a batched Bernoulli CUSUM (the rule we picked)
--------------------------------------------------
The vault releases aggregates only, and never for groups under 5. A classic
CUSUM needs one correct/incorrect indicator per guess, which would reveal
allocation one patient at a time. So the monitor sends the vault disjoint
windows of at least 5 guesses ("batches") and feeds each batch's counts into
the log-likelihood-ratio CUSUM:

    S_k = max(0, S_{k-1} + x_k * ln(p1/p0) + (n_k - x_k) * ln((1-p1)/(1-p0)))

with x_k correct out of n_k decisive guesses in batch k. The increment is
additive, so this is the per-guess Bernoulli CUSUM sampled at batch
boundaries (only the reset to 0 is coarser). It is the optimal sequential
test for a shift from p0 to p1 (Moustakides 1986), so it reacts faster than an
interval rule at the same false-alarm rate. The Wilson interval is still
computed and shown, because it is what a scientist reads, and eval_drift.py
reports both rules against an end-of-trial-only check.
"""
from __future__ import annotations

import math

Z95 = 1.959964

# P0: rater accuracy under working blinding, top of the expected 0.5 to 0.6
# range, so ordinary variation between sites does not alarm. P1: the accuracy
# we must not miss. H: calibrated by eval_drift.py --calibrate on seeds kept
# separate from the reported ones (see eval_results/drift_eval.md).
P0 = 0.60
P1 = 0.85
H = 3.5  # calibration seeds 100-129: lowest false-alarm rate among thresholds that missed no drift

# Alarm on site-level rater groups. Per-rater groups release batches slowly
# and multiply false alarms; they are kept as evidence for which raters drive
# a site alarm.
ALARM_BY = "site"

WILSON_THRESHOLD = 0.75
WILSON_MIN_N = 8
ROLLING_BATCHES = 3


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for k successes out of n."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


def cusum_step(s: float, correct: int, decisive: int, p0: float = P0, p1: float = P1) -> float:
    w_ok, w_bad = math.log(p1 / p0), math.log((1 - p1) / (1 - p0))
    return max(0.0, s + correct * w_ok + (decisive - correct) * w_bad)


def cusum_path(batches: list[dict], p0: float = P0, p1: float = P1) -> list[float]:
    s, out = 0.0, []
    for b in batches:
        s = cusum_step(s, b["window_correct"], b["window_decisive"], p0, p1)
        out.append(s)
    return out


def cusum_onset(batches: list[dict], path: list[float]) -> int | None:
    """Change-point estimate: first day of the batch after the CUSUM last sat at 0."""
    if not batches:
        return None
    last_zero = -1
    for i, s in enumerate(path):
        if s == 0.0:
            last_zero = i
    return batches[min(last_zero + 1, len(batches) - 1)]["window_from"]


def rolling(batches: list[dict], k: int = ROLLING_BATCHES) -> tuple[int, int]:
    tail = batches[-k:]
    return sum(b["window_correct"] for b in tail), sum(b["window_decisive"] for b in tail)


def wilson_rule(batches: list[dict], k: int = ROLLING_BATCHES) -> bool:
    c, n = rolling(batches, k)
    return n >= WILSON_MIN_N and wilson(c, n)[0] > WILSON_THRESHOLD
