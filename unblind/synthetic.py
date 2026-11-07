"""Synthetic trials with a planted truth.

Used for (1) the demo calibration set before the real corpus is approved and
(2) the evaluation: can the meta-regression recover a known drug effect, and
how badly is it fooled when its assumptions are violated?

Every synthetic row is labelled provenance=SYNTHETIC.

Scenarios
  expectancy         bias = b_true * u. u depends only on design. (model is right)
  reverse_causation  patients who improve guess "drug" more often, so u rises
                     with the true effect. (model's key assumption broken)
  confounded         trials with better blinding also used a lower-efficacy
                     population. (cross-trial confounding)
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

import numpy as np

COMPARATORS = ["inert_placebo", "active_placebo", "low_dose_same_drug", "other_active"]
U_MEAN = {"inert_placebo": 0.75, "active_placebo": 0.45, "low_dose_same_drug": 0.40, "other_active": 0.35}


def make_trials(k: int = 30, true_g: float = 0.35, b_true: float = 0.6, r_onsite: float = 0.10,
                scenario: str = "expectancy", observed_frac: float = 0.35, seed: int = 0) -> List[Dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(k):
        comp = rng.choice(COMPARATORS, p=[0.6, 0.15, 0.15, 0.10])
        pe = float(np.clip(rng.beta(2, 2), 0, 1))
        central = int(rng.random() < 0.35)
        n = int(rng.integers(20, 240))
        g_i = true_g + rng.normal(0, 0.08)               # between-trial heterogeneity in the true effect
        if scenario == "confounded":
            # better-blinded designs happened to recruit less responsive populations
            g_i -= 0.25 * (comp != "inert_placebo")
        u = U_MEAN[comp] + 0.2 * (pe - 0.5) + rng.normal(0, 0.08)
        if scenario == "reverse_causation":
            u += 0.9 * (g_i - true_g) + 0.5 * g_i        # improvement makes people guess "drug"
        u = float(np.clip(u, 0, 1))
        se = float(np.sqrt(4 / n + g_i ** 2 / (2 * n)))
        # truth = effect with zero unblinding AND central blinded raters; on-site raters inflate by r_onsite.
        # Under reverse_causation there is no expectancy bias at all: u is purely a consequence of benefit.
        g_obs = g_i + b_true * u * (scenario != "reverse_causation") + r_onsite * (1 - central) + rng.normal(0, se)
        observed = rng.random() < observed_frac
        rows.append({
            "trial_id": f"SYN-{seed}-{i:03d}", "provenance": "SYNTHETIC", "drug": "synthetic-psychedelic",
            "comparator_type": comp, "central": central, "prior_exposure": round(pe, 2),
            "g": round(float(g_obs), 3), "se_g": round(se, 3),
            "u": round(u, 3) if observed else None, "u_true": round(u, 3),
            "u_status": "observed" if observed else "missing", "u_sd": 0.05 if observed else None,
            "approved": "synthetic",
        })
    return rows


def fill_imputed(rows: List[Dict], dm) -> List[Dict]:
    for r in rows:
        if r.get("u") is None:
            u, sd = dm.predict(r.get("comparator_type"), r.get("prior_exposure"))
            r["u"], r["u_sd"], r["u_status"] = round(u, 3), round(sd, 3), "imputed"
    return rows


def write_demo_calibration(path: Path, seed: int = 7) -> None:
    from .model import design_model
    rows = make_trials(k=36, seed=seed, observed_frac=0.4)
    rows = fill_imputed(rows, design_model(rows))
    fields = ["trial_id", "provenance", "drug", "comparator_type", "central", "prior_exposure",
              "g", "se_g", "u", "u_sd", "u_status", "approved"]
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


if __name__ == "__main__":
    p = Path(__file__).resolve().parent.parent / "data" / "calibration_synthetic.csv"
    write_demo_calibration(p)
    print("wrote", p)
