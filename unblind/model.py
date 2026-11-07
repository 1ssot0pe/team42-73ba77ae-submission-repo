"""The physics: a random-effects meta-regression across trials.

    g_i = a + b * u_i + c * central_i + e_i,   e_i ~ N(0, se_i^2 + tau^2)

g  standardised effect (Hedges' g, positive = drug better than comparator)
u  unblinding index in [0, 1]: excess correct guessing above chance,
   u = max(0, 2 * accuracy - 1)   (0 = coin flip, 1 = everyone knew)
central  1 if outcome raters were central/remote and blinded

a  the effect a trial with zero unblinding and on-site raters would show
b  bias per unit of unblinding (expected to be positive)

Primary fit uses ONLY trials whose blinding was observed. Trials whose u was
imputed from design enter a sensitivity fit, with their x-uncertainty
propagated (errors-in-variables inflation b^2 * var_u).

IMPORTANT LIMITATION (stated in every report): if patients guess "drug"
because they improved, u is partly caused by efficacy, and b absorbs real
drug effect. The intercept is then a conservative lower bound, not "the
true effect". See eval/synthetic_recovery.py, scenario "reverse_causation".
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

DATA = Path(__file__).resolve().parent.parent / "data"


def u_from_accuracy(acc: float) -> float:
    return float(max(0.0, min(1.0, 2 * acc - 1)))


# ---------------------------------------------------------------------------
@dataclass
class Fit:
    coef: Dict[str, float]
    se: Dict[str, float]
    cov: np.ndarray
    names: List[str]
    tau2: float
    k: int
    df: int
    u_range: tuple
    label: str = ""

    def ci(self, name: str, level: float = 0.95):
        t = _tcrit(self.df, level)
        return self.coef[name] - t * self.se[name], self.coef[name] + t * self.se[name]

    def summary(self) -> Dict[str, object]:
        out = {"label": self.label, "k": self.k, "tau2": round(self.tau2, 4),
               "u_observed_range": [round(x, 2) for x in self.u_range]}
        for n in self.names:
            lo, hi = self.ci(n)
            out[n] = {"est": round(self.coef[n], 3), "ci95": [round(lo, 3), round(hi, 3)]}
        return out


def _tcrit(df: int, level: float = 0.95) -> float:
    # small table, avoids a scipy dependency
    table = {1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57, 6: 2.45, 7: 2.36, 8: 2.31, 9: 2.26, 10: 2.23,
             12: 2.18, 15: 2.13, 20: 2.09, 25: 2.06, 30: 2.04, 40: 2.02, 60: 2.00, 120: 1.98}
    if df <= 0:
        return float("inf")
    keys = sorted(table)
    for k in keys:
        if df <= k:
            return table[k]
    return 1.96


def fit_metareg(rows: Sequence[dict], covariates=("u", "central"), label: str = "",
                use_imputed: bool = False) -> Optional[Fit]:
    data = [r for r in rows if r.get("g") is not None and r.get("se_g") and r.get("u") is not None
            and (use_imputed or r.get("u_status") == "observed")]
    covs = [c for c in covariates if c == "u" or len({float(r.get(c) or 0) for r in data}) > 1]
    names = ["intercept"] + covs
    k, p = len(data), len(names)
    if k < p + 2:
        return None
    X = np.array([[1.0] + [float(r.get(c) or 0) for c in covs] for r in data])
    y = np.array([float(r["g"]) for r in data])
    v = np.array([float(r["se_g"]) ** 2 for r in data])
    vu = np.array([float(r.get("u_sd") or 0) ** 2 if r.get("u_status") != "observed" else 0.0 for r in data])

    b_u = 0.0
    tau2 = 0.0
    for _ in range(4):  # iterate: EIV inflation depends on slope, tau2 depends on weights
        vi = v + (b_u ** 2) * vu
        W = np.diag(1.0 / vi)
        XtWX = X.T @ W @ X
        inv = np.linalg.pinv(XtWX)
        beta_fe = inv @ X.T @ W @ y
        resid = y - X @ beta_fe
        Q = float(resid @ W @ resid)
        P = W - W @ X @ inv @ X.T @ W
        tau2 = max(0.0, (Q - (k - p)) / float(np.trace(P)))
        Wr = np.diag(1.0 / (vi + tau2))
        inv_r = np.linalg.pinv(X.T @ Wr @ X)
        beta = inv_r @ X.T @ Wr @ y
        b_u = float(beta[1]) if "u" in covs else 0.0
    # Knapp-Hartung style scaling for small k
    resid = y - X @ beta
    s2 = max(1.0, float(resid @ Wr @ resid) / max(1, k - p))
    cov = inv_r * s2
    us = [float(r["u"]) for r in data]
    return Fit(coef={n: float(b) for n, b in zip(names, beta)},
               se={n: math.sqrt(max(cov[i, i], 0)) for i, n in enumerate(names)},
               cov=cov, names=names, tau2=tau2, k=k, df=k - p,
               u_range=(min(us), max(us)), label=label)


# ---------------------------------------------------------------------------
# design -> unblinding (used to impute missing u, and for counterfactuals)
# ---------------------------------------------------------------------------
def load_priors() -> dict:
    return json.loads((DATA / "priors.json").read_text())


@dataclass
class DesignModel:
    source: str                     # "fitted on N observed trials" | "assumption table"
    priors: dict = field(default_factory=dict)
    beta: Optional[np.ndarray] = None
    resid_sd: float = 0.2

    def features(self, comparator: str, prior_exposure: Optional[float]) -> np.ndarray:
        pe = 0.5 if prior_exposure is None else float(prior_exposure)
        return np.array([1.0, comparator == "active_placebo", comparator == "low_dose_same_drug",
                         comparator == "other_active", pe], dtype=float)

    def predict(self, comparator: Optional[str], prior_exposure: Optional[float]) -> tuple:
        """Returns (u_mean, u_sd)."""
        comparator = comparator or "inert_placebo"
        if comparator == "waitlist_or_none":
            return 1.0, 0.05
        if self.beta is not None:
            u = float(self.features(comparator, prior_exposure) @ self.beta)
            sd = self.resid_sd + (0.1 if prior_exposure is None else 0.0)
            return min(1.0, max(0.0, u)), sd
        pr = self.priors["unblinding_by_comparator"].get(comparator, self.priors["unblinding_by_comparator"]["inert_placebo"])
        u = pr["u"]
        adj = self.priors["prior_exposure_effect"]
        if prior_exposure is not None:
            u += adj * (prior_exposure - 0.5)
        sd = pr["sd"] + (0.1 if prior_exposure is None else 0.0)
        return min(1.0, max(0.0, u)), sd


def design_model(rows: Sequence[dict], min_obs: int = 8) -> DesignModel:
    priors = load_priors()
    obs = [r for r in rows if r.get("u_status") == "observed" and r.get("comparator_type")]
    if len(obs) >= min_obs:
        dm = DesignModel(source=f"fitted on {len(obs)} trials with observed blinding", priors=priors)
        X = np.array([dm.features(r["comparator_type"], r.get("prior_exposure")) for r in obs])
        y = np.array([float(r["u"]) for r in obs])
        lam = 0.5 * np.eye(X.shape[1]); lam[0, 0] = 0
        beta = np.linalg.solve(X.T @ X + lam, X.T @ y)
        dm.beta = beta
        dm.resid_sd = float(np.sqrt(np.mean((y - X @ beta) ** 2))) + 0.05
        return dm
    return DesignModel(source="assumption table data/priors.json (not fitted)", priors=priors)


# ---------------------------------------------------------------------------
# applying the calibration to one trial
# ---------------------------------------------------------------------------
def correct(fit: Fit, g: float, se_g: float, u: float, u_sd: float, central: bool) -> Dict[str, float]:
    b = fit.coef.get("u", 0.0)
    c = fit.coef.get("central", 0.0)
    # bias relative to a zero-unblinding, on-site-rater reference
    bias = b * u
    var_b = fit.se.get("u", 0.0) ** 2
    var = se_g ** 2 + (u ** 2) * var_b + (b ** 2) * (u_sd ** 2)
    corrected = g - bias
    sd = math.sqrt(var)
    lo, hi = corrected - 1.96 * sd, corrected + 1.96 * sd
    return {"bias": bias, "corrected": corrected, "lo": lo, "hi": hi, "sd": sd,
            "extrapolated": not (fit.u_range[0] - 0.05 <= u <= fit.u_range[1] + 0.05)}


LEVERS = [
    ("Switch comparator to a low dose of the same drug", {"comparator_type": "low_dose_same_drug"}),
    ("Switch comparator to an active placebo (e.g. niacin)", {"comparator_type": "active_placebo"}),
    ("Move outcome raters central and remote, blinded", {"central": 1}),
    ("Enrol psychedelic-naive participants", {"prior_exposure": 0.0}),
]


def counterfactuals(fit: Fit, dm: DesignModel, design: dict, u_actual: Optional[float] = None) -> List[dict]:
    """Expected bias (in g units) under the current design and each single change.

    If the trial's own unblinding was measured, the baseline uses it and each
    change shifts it by the design model's predicted difference."""
    pri = dm.priors
    feas = pri.get("feasibility", {})
    b = fit.coef.get("u", 0.0)
    c = fit.coef.get("central", 0.0) if "central" in fit.coef else 0.0

    u0, _ = dm.predict(design.get("comparator_type"), design.get("prior_exposure"))
    shift = (u_actual - u0) if u_actual is not None else 0.0

    def bias_of(d):
        u, usd = dm.predict(d.get("comparator_type"), d.get("prior_exposure"))
        u = min(1.0, max(0.0, u + shift))
        return b * u + c * float(d.get("central") or 0), usd

    base, base_sd = bias_of(design)
    out = []
    for name, change in LEVERS:
        d2 = dict(design); d2.update(change)
        if all(design.get(k) == v for k, v in change.items()):
            continue
        new, sd = bias_of(d2)
        red = base - new
        f = feas.get(name, 0.7)
        out.append({"change": name, "expected_bias_before": round(base, 3), "expected_bias_after": round(new, 3),
                    "bias_reduction": round(red, 3), "feasibility_weight": f,
                    "score": round(red * f, 3), "u_sd": round(sd, 2)})
    out.sort(key=lambda r: -r["score"])
    return out


def load_calibration(name: str = "auto") -> tuple:
    """Real corpus if it has enough human-approved rows, else the labelled synthetic set."""
    import csv
    real = DATA / "calibration_real.csv"
    if name in ("auto", "real") and real.exists():
        rows = [_coerce(r) for r in csv.DictReader(real.open()) if r.get("approved", "").lower() in ("1", "true", "yes")]
        if len([r for r in rows if r.get("u_status") == "observed"]) >= 6 or name == "real":
            return rows, "real (human-approved rows from data/calibration_real.csv)"
    syn = DATA / "calibration_synthetic.csv"
    rows = [_coerce(r) for r in csv.DictReader(syn.open())]
    return rows, "SYNTHETIC calibration set (data/calibration_synthetic.csv). Not real-world performance."


def _coerce(r: dict) -> dict:
    out = dict(r)
    for k in ("g", "se_g", "u", "u_sd", "prior_exposure"):
        v = r.get(k)
        out[k] = float(v) if v not in (None, "", "NA") else None
    out["central"] = 1 if str(r.get("central", "0")).strip() in ("1", "True", "true") else 0
    return out
