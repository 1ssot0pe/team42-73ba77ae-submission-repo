"""Effect estimators for the close-out FDA blinding report. Owner: Izzy (post-dosing).

Every number here is computed from VAULT AGGREGATES only. Nothing in this file
ever sees who got the drug: it passes outcome rows and guesses to the vault and
receives group means back, with any cell under 5 people suppressed.

Sign convention (same as the Compass press releases): md = mean(drug) - mean(control)
on the MADRS, so NEGATIVE favours the drug. The SYNTHETIC world plants a true
effect of 4 points, i.e. md_true = -4.

Three estimates go side by side in the report:

  reported      vault.unblinded_effect on the primary endpoint (week 6).
                Drug effect + expectancy + rater bias, stuck together.
  within-trial  vault.effect_by_guess: compare drug vs control WITHIN people who
                guessed the same way, then pool the strata (weights n_d*n_c/(n_d+n_c)).
                Removes the part of the effect explained by the patient's belief.
  cross-trial   apply the existing meta-regression calibration (unblind.model)
                with this trial's own observed unblinding u.

Neither adjusted number is "the true effect". If patients guess "drug" because
they improved (reverse causation), adjusting for the guess removes real benefit,
so the adjusted values are a conservative bound under stated assumptions.
eval/platform/effect_recovery.py measures how wrong they get in both cases.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

from ... import model as calib

PRIMARY_WEEK_DEFAULT = 6


# ---------------------------------------------------------------------------
# inputs: outcome rows and pre-outcome guesses (no allocation anywhere)
# ---------------------------------------------------------------------------
def primary_week(rec) -> int:
    pe = (rec.get("protocol") or {}).get("primary_endpoint") or {}
    try:
        return int(pe.get("week") or PRIMARY_WEEK_DEFAULT)
    except (TypeError, ValueError):
        return PRIMARY_WEEK_DEFAULT


def _baselines(rec) -> Dict[str, float]:
    """Baseline MADRS if the platform recorded one (visit week 0 or on the enrolment row)."""
    out: Dict[str, float] = {}
    for o in rec.get("outcomes", []):
        if o.get("visit_week") == 0 and o.get("madrs") is not None:
            out[o["participant"]] = float(o["madrs"])
    for p in rec.get("enrolled", []):
        if p.get("baseline_madrs") is not None and p["id"] not in out:
            out[p["id"]] = float(p["baseline_madrs"])
    return out


def primary_rows(rec) -> Tuple[List[dict], Dict[str, str], Dict[str, str], str]:
    """Primary-endpoint rows for the vault.

    Returns (rows [{participant, change}], patient_guess {pid: guess}, rater_guess {pid: guess}, basis).
    Guesses are those recorded BEFORE the outcome (the outcome row's patient_guess, else the
    latest participant check-in on or before that day)."""
    wk = primary_week(rec)
    last: Dict[str, dict] = {}
    for o in rec.get("outcomes", []):
        if o.get("visit_week") == wk and o.get("madrs") is not None:
            last[o["participant"]] = o           # keep the latest row per participant
    base = _baselines(rec)
    use_change = bool(last) and all(pid in base for pid in last)
    rows, pg, rg = [], {}, {}
    for pid, o in sorted(last.items()):
        val = float(o["madrs"]) - base[pid] if use_change else float(o["madrs"])
        rows.append({"participant": pid, "change": val})
        g = o.get("patient_guess")
        if g is None:
            prior = [c for c in rec.get("checkins", []) if c.get("participant") == pid and c.get("who") == "participant"
                     and c.get("day", 10 ** 9) <= o.get("day", 10 ** 9) and c.get("guess")]
            g = prior[-1]["guess"] if prior else None
        if g:
            pg[pid] = g
        if o.get("rater_guess"):
            rg[pid] = o["rater_guess"]
    basis = (f"change from baseline to week {wk}" if use_change else
             f"week-{wk} MADRS score (no baseline MADRS on record; a valid comparison under randomisation)")
    return rows, pg, rg, basis


# ---------------------------------------------------------------------------
# estimators
# ---------------------------------------------------------------------------
def reported_effect(vault, rows: List[dict], requester: str) -> Optional[dict]:
    if not rows:
        return None
    r = vault.unblinded_effect(rows, requester)
    if r:
        r = dict(r, method="Reported: drug minus control on the primary endpoint (vault aggregate)")
    return r


def stratified_effect(vault, rows: List[dict], guesses: Dict[str, str], sd: float, requester: str,
                      label: str) -> Optional[dict]:
    """Drug vs control within guess strata, pooled. Uses vault.effect_by_guess (aggregates, min cell 5)."""
    if not rows or not guesses or not sd:
        return None
    cells = vault.effect_by_guess(rows, guesses, requester)
    by: Dict[str, Dict[str, dict]] = {}
    for c in cells:
        by.setdefault(c["guess"], {})[c["arm"]] = c
    strata, num, den, var = [], 0.0, 0.0, 0.0
    n_used = 0
    for g, arms in sorted(by.items()):
        d, c = arms.get("drug"), arms.get("control")
        if not d or not c or d.get("suppressed") or c.get("suppressed"):
            strata.append({"stratum": g, "used": False,
                           "why": "one arm has fewer than 5 people in this stratum, so the vault suppressed it"})
            continue
        diff = d["mean_change"] - c["mean_change"]
        w = d["n"] * c["n"] / (d["n"] + c["n"])
        se = sd * math.sqrt(1 / d["n"] + 1 / c["n"])
        num += w * diff
        den += w
        var += (w * se) ** 2
        n_used += d["n"] + c["n"]
        strata.append({"stratum": g, "used": True, "md": round(diff, 2), "n": d["n"] + c["n"]})
    if den == 0:
        return {"md": None, "strata": strata, "n_used": 0, "n_total": len([r for r in rows if r["participant"] in guesses]),
                "method": label, "why_missing": "no stratum had 5 or more people in both arms"}
    md = num / den
    se = math.sqrt(var) / den
    return {"md": round(md, 2), "lo": round(md - 1.96 * se, 2), "hi": round(md + 1.96 * se, 2), "se": round(se, 3),
            "strata": strata, "n_used": n_used,
            "n_total": len([r for r in rows if r["participant"] in guesses]), "method": label}


def hedges_g(md: float, sd: float, n1: int, n2: int) -> Tuple[float, float, float]:
    """Hedges' g with POSITIVE = drug better (md is negative when the drug helps). Returns (g, se_g, J)."""
    j = 1 - 3 / (4 * (n1 + n2 - 2) - 1)
    g = -md / sd * j
    se = math.sqrt((n1 + n2) / (n1 * n2) + g * g / (2 * (n1 + n2)))
    return g, se, j


@lru_cache(maxsize=1)
def _calibration():
    rows, label = calib.load_calibration()
    return calib.fit_metareg(rows, label=label), label


def cross_trial_effect(reported: dict, u: Optional[float], u_sd: float, central: bool) -> Optional[dict]:
    """Apply the existing meta-regression calibration with this trial's observed u."""
    if not reported or u is None or not reported.get("sd"):
        return None
    fit, label = _calibration()
    if fit is None:
        return None
    g, se_g, j = hedges_g(reported["md"], reported["sd"], reported["n_drug"], reported["n_control"])
    c = calib.correct(fit, g, se_g, u, u_sd, central)
    scale = reported["sd"] / j                    # g units back to MADRS points
    return {"md": round(-c["corrected"] * scale, 2), "lo": round(-c["hi"] * scale, 2), "hi": round(-c["lo"] * scale, 2),
            "g_reported": round(g, 3), "g_adjusted": round(c["corrected"], 3), "bias_g": round(c["bias"], 3),
            "u": u, "u_sd": round(u_sd, 3), "central_raters": central, "extrapolated": bool(c["extrapolated"]),
            "calibration": label, "synthetic_calibration": "SYNTHETIC" in label,
            "method": "Cross-trial: meta-regression calibration applied with this trial's observed unblinding"}


def observed_u(vault, guesses: Dict[str, str], requester: str) -> Tuple[Optional[float], float, Optional[dict]]:
    """Participant unblinding index u = 2*accuracy - 1 from the vault, with an sd from its interval."""
    rows = [{"participant": p, "guess": g, "all": "all"} for p, g in guesses.items()]
    if not rows:
        return None, 0.2, None
    st = vault.blinding_stats(rows, "all", requester)[0]
    if st.get("suppressed"):
        return None, 0.2, st
    u_sd = max(0.05, (st["accuracy_hi"] - st["accuracy_lo"]) / 3.92 * 2)
    return st["u"], u_sd, st


def central_raters(rec) -> bool:
    model = str((rec.get("protocol") or {}).get("rater_model", "")).lower()
    return any(k in model for k in ("central", "remote"))


# ---------------------------------------------------------------------------
# everything together (used by the close-out agent and by the evaluation)
# ---------------------------------------------------------------------------
def estimate_all(rec, vault, requester: str = "closeout_report_agent") -> dict:
    rows, pg, rg, basis = primary_rows(rec)
    out: dict = {"basis": basis, "primary_week": primary_week(rec), "n_rows": len(rows),
                 "n_with_patient_guess": len(pg), "sign": "drug minus control; negative favours the drug"}
    rep = reported_effect(vault, rows, requester)
    out["reported"] = rep
    if not rep:
        out["why_missing"] = ("fewer than 5 participants per arm have a primary-endpoint score"
                              if rows else "no primary-endpoint scores were recorded")
        out["within_trial"] = out["within_trial_rater"] = out["cross_trial"] = None
        out["adjusted_range"] = None
        return out
    out["within_trial"] = stratified_effect(vault, rows, pg, rep["sd"], requester,
                                            "Within-trial: drug vs control among people who made the same guess")
    both = {p: f"patient {pg[p]}, rater {rg[p]}" for p in pg if p in rg}
    out["within_trial_rater"] = stratified_effect(vault, rows, both, rep["sd"], requester,
                                                  "Within-trial (sensitivity): same patient guess AND same rater guess")
    u, u_sd, _ = observed_u(vault, pg, requester)
    out["cross_trial"] = cross_trial_effect(rep, u, u_sd, central_raters(rec))
    pts = [e["md"] for e in (out["within_trial"], out["cross_trial"]) if e and e.get("md") is not None]
    out["adjusted_range"] = {"lo": min(pts), "hi": max(pts)} if pts else None
    prim = out["within_trial"] if out["within_trial"] and out["within_trial"].get("md") is not None else out["cross_trial"]
    out["primary_adjusted"] = prim
    return out
