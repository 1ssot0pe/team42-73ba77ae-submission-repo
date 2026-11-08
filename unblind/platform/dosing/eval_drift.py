"""Drift evaluation: live monitor vs end-of-trial-only checking. SYNTHETIC.

    python -m unblind.platform.dosing.eval_drift --calibrate   # choose H on seeds 100-129
    python -m unblind.platform.dosing.eval_drift               # report on seeds 0-19

Runs the real Master and World with the real dosing module. Pre-dosing is
replaced by a small labelled harness (EvalPredose) that enrols a fixed-size
SYNTHETIC cohort, so results do not depend on another module's state.

Per seed, three full 90-day trials:
  A. drift planted (Site B raters from day 28), nobody approves  -> detection day
  B. no drift planted                                             -> false alarms
  C. drift planted, every request auto-approved the same day      -> does drift stop?

Rules compared on the same released vault batches:
  * CUSUM (the live rule): batched Bernoulli CUSUM, p0, p1, threshold H
  * Wilson: lower 95% bound over the last 3 batches above 0.75 with n >= 8
  * End-of-trial baseline: one check at close-out, cumulative site Wilson lower bound above p0
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
from pathlib import Path

os.environ.setdefault("UNBLIND_NO_LLM", "1")

from ..core import TRIALS, BaseModule  # noqa: E402
from ..master.orchestrator import CLOSE_DAY, Master  # noqa: E402
from ..world import SITES, WorldConfig  # noqa: E402
from . import stats  # noqa: E402

OUT = Path(__file__).resolve().parent / "eval_results"
DRIFT_SITE, DRIFT_DAY = WorldConfig().drift_site, WorldConfig().drift_day
NEVER = 10 ** 9


class EvalPredose(BaseModule):
    """Evaluation harness only (SYNTHETIC). Enrols per_site people per site, 1:1 stratified
    randomisation in the vault, and a full dosing schedule with `raters` raters per site."""
    name = "predose"

    def __init__(self, per_site: int = 24, raters: int = 2):
        self.per_site, self.raters = per_site, raters

    def setup(self, rec, ctx):
        apps = ctx.world.applicants(self.per_site * len(SITES))
        enrolled = []
        for i, a in enumerate(apps):
            site = SITES[i % len(SITES)]
            j = i // len(SITES)
            enrolled.append({"id": a["id"], "name": a["name"], "site": site,
                             "stratum": f"{site}|{'naive' if a['prior_psychedelic_use'] == 'never' else 'experienced'}",
                             "prior_psychedelic_use": a["prior_psychedelic_use"],
                             "dosing_day": 1 + (j * 20) // self.per_site, "consents": {"checkins": True}})
        ctx.vault.randomise(enrolled, "stratum")
        rec["enrolled"] = enrolled
        k = 0
        for p in enrolled:
            d, pid, site = p["dosing_day"], p["id"], p["site"]
            rid = f"R-{site[5]}{k % self.raters + 1}"
            k += 1

            def add(day, kind, inst, sid, **kw):
                rec["schedule"].append({"id": f"{pid}-{sid}", "participant": pid, "site": site, "day": day, "kind": kind,
                                        "owner": "dosing", "instrument": inst, "status": "scheduled", **kw})
            add(d, "dosing_session", "session", "dose")
            add(d, "monitor_debrief", "debrief", "deb")
            add(d + 1, "participant_checkin", "UNBLIND-BLIND-1", "ci0")
            for w in (1, 3, 6):
                add(d + 7 * w, "participant_checkin", "UNBLIND-BLIND-1", f"ci{w}")
                add(d + 7 * w, "rater_assessment", "MADRS + UNBLIND-BLIND-1-R", f"rv{w}", rater_id=rid)
        ctx.bus.post("predose", "master", "enrolment_complete", {"n": len(enrolled)})


def run_trial(seed: int, drift: bool, approve: bool, per_site: int = 24, raters: int = 2) -> Master:
    cfg = WorldConfig(seed=seed, drift_day=DRIFT_DAY if drift else NEVER)
    tid = f"EVAL-{seed}-{int(drift)}{int(approve)}-{per_site}"
    m = Master(tid, seed=seed, world_cfg=cfg, auto_approve=approve)
    m.modules["predose"], m.module_status["predose"] = EvalPredose(per_site, raters), "eval harness"
    m.rec.save = lambda: None  # keep evaluation in memory
    m.setup()
    m.run_to(CLOSE_DAY)
    for p in TRIALS.glob(f"{tid}*"):
        p.unlink()
    return m


def site_batches(rec, site: str) -> list:
    return [b for b in rec["blinding_metrics"] if b.get("module") == "dosing" and b["who"] == "rater"
            and b["by"] == stats.ALARM_BY and b["group"] == site]


def first_cross(bs: list, rule: str, h: float) -> int | None:
    if rule == "cusum":
        s = 0.0
        for b in bs:
            s = stats.cusum_step(s, b["window_correct"], b["window_decisive"])
            if s >= h:
                return b["day"]
        return None
    for i in range(len(bs)):
        if stats.wilson_rule(bs[: i + 1]):
            return bs[i]["day"]
    return None


def detections(rec, rule: str, h: float = stats.H) -> dict:
    return {s: first_cross(site_batches(rec, s), rule, h) for s in SITES}


def end_of_trial(rec) -> dict:
    out = {}
    for s in SITES:
        bs = site_batches(rec, s)
        k, n = sum(b["window_correct"] for b in bs), sum(b["window_decisive"] for b in bs)
        out[s] = n > 0 and stats.wilson(k, n)[0] > stats.P0
    return out


def score(runs: dict, h: float) -> dict:
    res = {r: {"delay": [], "missed": 0, "fa_null": 0, "fa_drift": 0} for r in ("cusum", "wilson")}
    eot = {"detected": 0, "fa_null": 0}
    for seed, r in runs.items():
        for rule in ("cusum", "wilson"):
            dA = detections(r["A"].rec, rule, h)
            hit = dA[DRIFT_SITE]
            if hit is None:
                res[rule]["missed"] += 1
            elif hit < DRIFT_DAY:
                res[rule]["fa_drift"] += 1
                res[rule]["missed"] += 1
            else:
                res[rule]["delay"].append(hit - DRIFT_DAY)
            res[rule]["fa_drift"] += sum(1 for s, d in dA.items() if s != DRIFT_SITE and d is not None)
            res[rule]["fa_null"] += sum(1 for d in detections(r["B"].rec, rule, h).values() if d is not None)
        eot["detected"] += end_of_trial(r["A"].rec)[DRIFT_SITE]
        eot["fa_null"] += sum(end_of_trial(r["B"].rec).values())
    res["end_of_trial"] = eot
    return res


def collect(seeds, with_action=True, per_site=24, raters=2) -> dict:
    return {s: {"A": run_trial(s, True, False, per_site, raters), "B": run_trial(s, False, False, per_site, raters),
                "C": run_trial(s, True, True, per_site, raters) if with_action else None} for s in seeds}


def calibrate(seeds=range(100, 130)) -> dict:
    runs = collect(seeds, with_action=False)
    n = len(runs)
    grid = []
    for h in (2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0):
        c = score(runs, h)["cusum"]
        grid.append({"H": h, "median_delay": st.median(c["delay"]) if c["delay"] else None, "missed": c["missed"],
                     "false_alarms_per_trial_null": round(c["fa_null"] / n, 3),
                     "false_alarms_per_trial_drift": round(c["fa_drift"] / n, 3)})
    return {"seeds": f"{min(seeds)}-{max(seeds)}", "p0": stats.P0, "p1": stats.P1, "grid": grid,
            "rule": "lowest false-alarm rate among thresholds that missed no drift (a false alarm costs one human review; a missed drift costs the trial)"}


def _q(xs, p):
    xs = sorted(xs)
    if not xs:
        return None
    i = (len(xs) - 1) * p
    lo, hi = int(i), min(int(i) + 1, len(xs) - 1)
    return round(xs[lo] + (xs[hi] - xs[lo]) * (i - lo), 1)


def summarise(runs: dict, label: str) -> dict:
    n = len(runs)
    sc = score(runs, stats.H)
    cu, wi, eot = sc["cusum"], sc["wilson"], sc["end_of_trial"]
    live, onset_err = [], []
    for r in runs.values():
        al = [a for a in r["A"].rec["alerts"] if a.get("kind") == "rater_drift" and a["site"] == DRIFT_SITE]
        live.append(al[0]["day"] if al else None)
        if al and al[0]["evidence"]["onset_day_estimate"] is not None:
            onset_err.append(al[0]["evidence"]["onset_day_estimate"] - DRIFT_DAY)
    out = {"label": label, "n_seeds": n,
           "cusum": {"detected": len(cu["delay"]), "median_delay_days": st.median(cu["delay"]) if cu["delay"] else None,
                     "delay_iqr": [_q(cu["delay"], .25), _q(cu["delay"], .75)],
                     "false_alarms_per_trial_no_drift": round(cu["fa_null"] / n, 3),
                     "false_alarms_per_trial_drift_runs": round(cu["fa_drift"] / n, 3)},
           "wilson_rule": {"detected": len(wi["delay"]), "median_delay_days": st.median(wi["delay"]) if wi["delay"] else None,
                           "delay_iqr": [_q(wi["delay"], .25), _q(wi["delay"], .75)],
                           "false_alarms_per_trial_no_drift": round(wi["fa_null"] / n, 3)},
           "end_of_trial_baseline": {"detected": eot["detected"], "delay_days_if_detected": CLOSE_DAY - DRIFT_DAY,
                                     "false_alarms_per_trial_no_drift": round(eot["fa_null"] / n, 3)},
           "live_agent_alert_days": live,
           "onset_estimate_error_days": {"median": st.median(onset_err) if onset_err else None, "values": onset_err}}
    if all(r["C"] is not None for r in runs.values()):
        stopped = unconfirmed = realert = k = nn = 0
        for r in runs.values():
            C = r["C"]
            al = [a for a in C.rec["alerts"] if a.get("kind") == "rater_drift" and a["site"] == DRIFT_SITE]
            if not al:
                continue
            first = al[0]
            stopped += first["status"] == "resolved"
            unconfirmed += first["status"] == "action_approved"
            realert += len(al) > 1
            if first.get("action_day") is not None:
                post = [b for b in site_batches(C.rec, DRIFT_SITE) if b["window_from"] > first["action_day"]]
                k += sum(b["window_correct"] for b in post)
                nn += sum(b["window_decisive"] for b in post)
        lo, hi = stats.wilson(k, nn) if nn else (None, None)
        kp = [r["C"].modules["dosing"].kpis(r["C"].rec) for r in runs.values()]
        comp = [x["value"] for k_ in kp for x in k_ if x["label"] == "Blinding check-ins completed" and x["value"] is not None]
        deb = [r["C"].rec for r in runs.values()]
        out["after_approval"] = {"drift_stopped": stopped, "too_few_post_action_guesses": unconfirmed, "re_alerts": realert,
                                 "pooled_post_action": {"correct": k, "n": nn, "accuracy": round(k / nn, 3) if nn else None,
                                                        "ci": [round(lo, 3), round(hi, 3)] if nn else None}}
        out["operations_mean_per_trial"] = {
            "checkin_completion_pct": round(sum(comp) / len(comp), 1) if comp else None,
            "debriefs_structured": round(sum(len(r["debriefs"]) for r in deb) / n, 1),
            "adverse_events_captured": round(sum(len(a) for r in deb for a in (d["adverse_events"] for d in r["debriefs"])) / n, 1),
            "rater_contact_cues": round(sum(q["type"] == "rater_contact" for r in deb for d in r["debriefs"] for q in d["unblinding_cues"]) / n, 1),
            "primary_lock_day": round(sum(r.get("primary_lock_day") or 0 for r in deb) / n, 1),
        }
    return out


def report(seeds=range(20)) -> dict:
    seeds = list(seeds)
    main = summarise(collect(seeds), "72 participants, 3 sites, 2 raters per site (plan scale)")
    small = summarise(collect(seeds, with_action=False, per_site=8, raters=1),
                      "24 participants, 3 sites, 1 rater per site (stub pre-dosing scale)")
    return {"synthetic": True, "seeds": f"{seeds[0]}-{seeds[-1]}", "n_seeds": len(seeds),
            "planted_drift": {"site": DRIFT_SITE, "onset_day": DRIFT_DAY,
                              "rater_accuracy": "about 0.59 before, about 0.89 after (world.py)"},
            "detector": {"rule": "batched Bernoulli CUSUM", "p0": stats.P0, "p1": stats.P1, "H": stats.H, "min_batch": 5,
                         "alarm_by": stats.ALARM_BY, "note": "H chosen on calibration seeds 100-129, not on the reported seeds"},
            **{k: v for k, v in main.items() if k not in ("label", "n_seeds")}, "scale": main["label"],
            "sensitivity_small_trial": small}


def to_markdown(r: dict, cal: dict | None) -> str:
    cu, wi, eot = r["cusum"], r["wilson_rule"], r["end_of_trial_baseline"]
    sm = r["sensitivity_small_trial"]
    n = r["n_seeds"]
    L = ["# Drift detection evaluation (SYNTHETIC)", "",
         f"{n} simulated 90-day trials per scenario (seeds {r['seeds']}), real Master, World and dosing module. "
         f"Planted truth: {r['planted_drift']['site']} raters start sitting in on sessions from day {r['planted_drift']['onset_day']}; "
         f"rater accuracy {r['planted_drift']['rater_accuracy']}.", "",
         f"Detector: {r['detector']['rule']}, p0={r['detector']['p0']}, p1={r['detector']['p1']}, H={r['detector']['H']}, "
         f"alarms per {r['detector']['alarm_by']}. {r['detector']['note']}. The vault releases only batches of 5 or more guesses.", "",
         f"## Main result: {r['scale']}", "",
         "| Rule | Drift detected | Median delay (days) | Delay IQR | False alarms per trial, no drift |", "|---|---|---|---|---|",
         f"| CUSUM (live agent) | {cu['detected']}/{n} | {cu['median_delay_days']} | {cu['delay_iqr'][0]} to {cu['delay_iqr'][1]} | {cu['false_alarms_per_trial_no_drift']} |",
         f"| Wilson interval rule | {wi['detected']}/{n} | {wi['median_delay_days']} | {wi['delay_iqr'][0]} to {wi['delay_iqr'][1]} | {wi['false_alarms_per_trial_no_drift']} |",
         f"| End-of-trial check only | {eot['detected']}/{n} | {eot['delay_days_if_detected']} | n/a | {eot['false_alarms_per_trial_no_drift']} |", "",
         f"CUSUM false alarms at other sites (or before onset) in drift runs: {cu['false_alarms_per_trial_drift_runs']} per trial. "
         f"Onset estimate error (agent's change-point vs planted day {r['planted_drift']['onset_day']}): median "
         f"{r['onset_estimate_error_days']['median']} days.", ""]
    aa = r.get("after_approval")
    if aa:
        pa = aa["pooled_post_action"]
        L += [f"After a human approves remote raters: drift confirmed stopped in {aa['drift_stopped']} of {n} trials; in "
              f"{aa['too_few_post_action_guesses']} more, the last rater visits came before two post-action batches could "
              f"confirm it; re-alerts {aa['re_alerts']}. Pooled {r['planted_drift']['site']} rater accuracy after the action: "
              f"{pa['correct']} of {pa['n']} ({pa['accuracy']:.0%}, 95% interval {pa['ci'][0]:.0%} to {pa['ci'][1]:.0%}).", "",
              "Operations (mean per trial): " + ", ".join(f"{k.replace('_', ' ')} {v}" for k, v in r["operations_mean_per_trial"].items()) + ".", ""]
    smc = sm["cusum"]
    L += [f"## Sensitivity: {sm['label']}", "",
          f"CUSUM detected {smc['detected']}/{n} (median delay {smc['median_delay_days']} days), false alarms per no-drift trial "
          f"{smc['false_alarms_per_trial_no_drift']}; end-of-trial check detected {sm['end_of_trial_baseline']['detected']}/{n}. "
          "Small trials produce too few rater guesses after onset for the vault to release, so drift cannot be confirmed "
          "while protecting allocation. More raters' guesses (or more participants per site) buy earlier detection.", "",
          "## Limits", "",
          "Synthetic data with one planted failure mode. The drift size is an assumption of the simulator. A released batch "
          "at 0% or 100% accuracy still reveals the arms of the people in it; adding noise in the vault is the next step. "
          "Auto-approval in run C stands in for a human deciding the same day."]
    if cal:
        L += ["", f"## Threshold calibration (seeds {cal['seeds']}, CUSUM, plan scale)", "", f"Rule: {cal['rule']}.", "",
              "| H | Median delay | Missed | False alarms per trial, no drift | Other sites, drift runs |", "|---|---|---|---|---|"]
        L += [f"| {g['H']} | {g['median_delay']} | {g['missed']} | {g['false_alarms_per_trial_null']} | {g['false_alarms_per_trial_drift']} |"
              for g in cal["grid"]]
    return "\n".join(L) + "\n"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--seeds", type=int, default=20)
    a = ap.parse_args(argv)
    OUT.mkdir(exist_ok=True)
    if a.calibrate:
        cal = calibrate()
        (OUT / "calibration.json").write_text(json.dumps(cal, indent=1))
        for g in cal["grid"]:
            print(g)
        return
    cp = OUT / "calibration.json"
    cal = json.loads(cp.read_text()) if cp.exists() else None
    r = report(range(a.seeds))
    (OUT / "drift_eval.json").write_text(json.dumps(r, indent=1))
    md = to_markdown(r, cal)
    (OUT / "drift_eval.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
