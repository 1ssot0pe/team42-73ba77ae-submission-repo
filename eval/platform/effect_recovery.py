"""Planted-truth evaluation of the close-out report's effect estimates (post-dosing module).

    python eval/platform/effect_recovery.py              # 20 seeds, writes eval/platform/effect_recovery.json
    python eval/platform/effect_recovery.py --seeds 50

EVERYTHING HERE IS SYNTHETIC. The SYNTHETIC World plants a true drug effect of 4 MADRS
points (md_true = -4, negative favours the drug), plus expectancy (3 points when the
patient believes they got the drug) and rater bias (2 points when the rater believes it).

For each seed we simulate one trial the way the platform collects it (participant
guess the day after dosing; rater visits at weeks 1, 3 and 6 with MADRS and the
rater's guess; missed visits as the World decides), then run the SAME estimators the
close-out agent uses (unblind/platform/postdose/effects.py), which see vault
aggregates only. We report bias, RMSE and 95% interval coverage of md_true.

Scenarios
  planted            the default World: expectancy + rater bias + rater drift at Site B from day 28
  no_bias            expectancy and rater bias switched off: adjustment should not distort a clean trial
  reverse_causation  NO expectancy or rater bias, but each person's guess follows their own improvement.
                     Adjusting for the guess then removes real effect. This is the failure the report warns about.

The reverse-causation World subclasses the simulator here, in eval code that plays
"reality". Platform modules never do this; they use the World's public methods only.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from unblind.platform.core import TrialRecord, Vault  # noqa: E402
from unblind.platform.postdose import effects  # noqa: E402
from unblind.platform.world import SITES, World, WorldConfig  # noqa: E402

OUT = Path(__file__).resolve().parent
TRUTH = -4.0
METHODS = ["reported", "within_trial", "within_trial_rater", "cross_trial"]
LABEL = {"reported": "Reported (naive, the baseline)", "within_trial": "Within-trial: same patient guess",
         "within_trial_rater": "Within-trial: same patient and rater guess",
         "cross_trial": "Cross-trial calibration (SYNTHETIC calibration)"}


class ReverseCausationWorld(World):
    """Guesses track each person's own (arm-independent) improvement. No expectancy, no rater bias, no drift."""

    def __init__(self, vault, cfg):
        cfg.expectancy_effect, cfg.rater_bias, cfg.drift_day = 0.0, 0.0, 10 ** 9
        super().__init__(vault, cfg)
        self.latent: Dict[str, float] = {}

    def enrol(self, participants):
        super().enrol(participants)
        for p in participants:
            self.latent[p["id"]] = self.rng.gauss(0, 1)

    def _believes_drug(self, pid, who, day, site):
        base = super()._believes_drug(pid, who, day, site)
        if who == "participant":
            return min(0.98, max(0.02, base + 0.15 * self.latent.get(pid, 0.0)))
        return base

    def madrs(self, pid, day, rater_believes_drug=None, patient_believes_drug=None):
        s = super().madrs(pid, day, rater_believes_drug, patient_believes_drug)
        ramp = min(1.0, max(0.0, day / 21))
        return round(min(60, max(0, s - 4.0 * self.latent.get(pid, 0.0) * ramp)), 1)


def simulate(seed: int, n: int, scenario: str, tmp: Path) -> dict:
    tid = f"EVAL-{scenario}-{n}-{seed}"
    vault = Vault(tid, seed=seed)
    vault.path = tmp / f"{tid}.vault.json"            # keep eval vaults out of data/trials
    cfg = WorldConfig(seed=seed)
    if scenario == "no_bias":
        cfg.expectancy_effect, cfg.rater_bias = 0.0, 0.0
    world = ReverseCausationWorld(vault, cfg) if scenario == "reverse_causation" else World(vault, cfg)
    apps = world.applicants(n)
    enrolled = []
    for i, a in enumerate(apps):
        site = SITES[i % 3]
        enrolled.append({"id": a["id"], "site": site, "dosing_day": 1 + i % 20,
                         "stratum": f"{site}|{'naive' if a['prior_psychedelic_use'] == 'never' else 'experienced'}",
                         "prior_psychedelic_use": a["prior_psychedelic_use"],
                         "consents": {"checkins": True, "data_sharing": True}})
    vault.randomise(enrolled, "stratum")
    world.enrol(enrolled)
    rec = TrialRecord(tid)
    rec["enrolled"] = enrolled
    for p in enrolled:
        pid, d, site = p["id"], p["dosing_day"], p["site"]
        ci = world.respond_checkin(pid, d + 1, "participant", site)
        pg = ci["guess"] if ci else None
        if ci:
            rec["checkins"].append({"participant": pid, "site": site, "day": d + 1, "who": "participant", **ci})
        for wk in (1, 3, 6):
            day = d + 7 * wk
            r = world.respond_checkin(pid, day, "rater", site)
            if r is None:
                continue
            rec["outcomes"].append({"participant": pid, "site": site, "day": day, "visit_week": wk,
                                    "madrs": world.madrs(pid, day, rater_believes_drug=r["guess"] == "drug",
                                                         patient_believes_drug=pg == "drug"),
                                    "rater_id": f"R-{site[5]}1", "rater_guess": r["guess"], "patient_guess": pg})
    return effects.estimate_all(rec, vault, "eval")


def summarise(runs: List[dict]) -> dict:
    out = {}
    for m in METHODS:
        ests = [r[m] for r in runs if r.get(m) and r[m].get("md") is not None]
        if not ests:
            out[m] = {"label": LABEL[m], "n_estimable": 0}
            continue
        mds = [e["md"] for e in ests]
        mean = sum(mds) / len(mds)
        out[m] = {"label": LABEL[m], "n_estimable": len(ests), "mean": round(mean, 2), "bias": round(mean - TRUTH, 2),
                  "rmse": round(math.sqrt(sum((x - TRUTH) ** 2 for x in mds) / len(mds)), 2),
                  "coverage": round(sum(1 for e in ests if e["lo"] <= TRUTH <= e["hi"]) / len(ests), 2),
                  "mean_ci_width": round(sum(e["hi"] - e["lo"] for e in ests) / len(ests), 2)}
        if m in ("within_trial", "within_trial_rater"):
            out[m]["mean_share_of_participants_used"] = round(
                sum(e["n_used"] / max(1, e["n_total"]) for e in ests) / len(ests), 2)
    return out


def run(seeds: int = 20, n: int = 120) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="unblind-postdose-eval-"))
    res = {"synthetic": True, "truth_md": TRUTH, "n_seeds": seeds, "n_participants": n, "scenarios": {},
           "by_n": {}, "note": "SYNTHETIC planted-truth simulation. Not real-world performance."}
    for sc in ("planted", "no_bias", "reverse_causation"):
        res["scenarios"][sc] = summarise([simulate(s, n, sc, tmp) for s in range(seeds)])
    for nn in (24, 60, 120):
        res["by_n"][str(nn)] = summarise([simulate(s, nn, "planted", tmp) for s in range(seeds)])
    return res


def markdown(res: dict) -> str:
    L = [f"### Effect recovery: naive vs adjusted vs planted truth ({res['n_seeds']} seeds, n = {res['n_participants']})", "",
         f"SYNTHETIC. Truth: drug minus control = {res['truth_md']} MADRS points (4 points benefit). "
         "Coverage = share of 95% intervals containing the truth. Bias = mean estimate minus truth (positive = too small a benefit).", ""]
    titles = {"planted": "Planted world (expectancy 3, rater bias 2, rater drift at Site B)",
              "no_bias": "No bias planted (adjustment should do no harm)",
              "reverse_causation": "Reverse causation (guesses follow improvement; no expectancy bias at all)"}
    for sc, rows in res["scenarios"].items():
        L += [f"**{titles[sc]}**", "", "| Method | Estimable | Mean | Bias | RMSE | Coverage | Mean CI width | Share of people used |",
              "|---|---|---|---|---|---|---|---|"]
        for m in METHODS:
            r = rows[m]
            if not r["n_estimable"]:
                L.append(f"| {r['label']} | 0 of {res['n_seeds']} | | | | | | |")
                continue
            L.append(f"| {r['label']} | {r['n_estimable']} of {res['n_seeds']} | {r['mean']:+.2f} | {r['bias']:+.2f} | "
                     f"{r['rmse']:.2f} | {r['coverage']:.0%} | {r['mean_ci_width']:.2f} | {r.get('mean_share_of_participants_used', '')} |")
        L.append("")
    L += ["**How often the within-trial estimate is available, by trial size (planted world)**", "",
          "| Participants | Reported estimable | Within-trial estimable | Within-trial bias | Within-trial coverage |", "|---|---|---|---|---|"]
    for nn, rows in res["by_n"].items():
        w = rows["within_trial"]
        L.append(f"| {nn} | {rows['reported']['n_estimable']} of {res['n_seeds']} | {w['n_estimable']} of {res['n_seeds']} | "
                 + (f"{w['bias']:+.2f} | {w['coverage']:.0%} |" if w["n_estimable"] else " | |"))
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--n", type=int, default=120)
    a = ap.parse_args()
    r = run(a.seeds, a.n)
    (OUT / "effect_recovery.json").write_text(json.dumps(r, indent=1))
    print(markdown(r))
