"""Blinding monitor and drift-and-action agent.

The monitor never sees allocation. Each day, for every group (overall, per
site, per rater; raters and participants), it sends ctx.vault the guesses made
since that group's last released batch. The vault answers with aggregates and
suppresses any group under 5. When a group is released the monitor stores the
batch as a blinding_metrics row and moves that group's cursor, so windows are
disjoint and each holds 5 or more guesses: the monitor's own query pattern
cannot be differenced to isolate one person. Cumulative figures are asked for
only at release, so they add nothing the batches did not already release.

All state (cursors, CUSUM scores, resets) is derived from dosing-owned
sections, so a reloaded TrialRecord carries on exactly where it stopped.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..core import Ctx, TrialRecord
from . import stats
from .agents import MODULE, log, next_id, short_site

LEVELS = (("rater", "overall"), ("rater", "site"), ("rater", "rater"), ("participant", "overall"), ("participant", "site"))
REQUESTER = "dosing.blinding_monitor"


def _fa_note() -> str:
    """The measured false-alarm rate, quoted only if the evaluation has been run (eval_drift.py)."""
    try:
        r = json.loads((Path(__file__).resolve().parent / "eval_results" / "drift_eval.json").read_text())
        return (f" (in {r['n_seeds']} simulated trials without drift this line gave "
                f"{r['cusum']['false_alarms_per_trial_no_drift']} false alarms per trial)")
    except Exception:
        return ""


def group_of(row: dict, by: str) -> Optional[str]:
    if by == "overall":
        return "all"
    if by == "site":
        return row.get("site") or None
    return row.get("rater_id") or None


def batches(rec: TrialRecord, who: str, by: str, group: str) -> list:
    return [m for m in rec["blinding_metrics"]
            if m.get("module") == MODULE and m["who"] == who and m["by"] == by and m["group"] == group]


def rater_sites(rec: TrialRecord) -> dict:
    return {s["rater_id"]: s.get("site", "") for s in rec["schedule"] if s.get("rater_id")}


def reset_day(rec: TrialRecord, site: str) -> int:
    """Last day the drift score for a site was reset: an approved action or a rejected alert."""
    days = [a["day"] for a in rec["actions"] if a.get("module") == MODULE and a.get("site") == site
            and a.get("type") == "remote_raters"]
    days += [a.get("decided_day") or a["day"] for a in rec["alerts"]
             if a.get("kind") == "rater_drift" and a.get("site") == site and a.get("status") == "dismissed"]
    return max(days, default=-10 ** 9)


class BlindingMonitor:
    name = "blinding_monitor"
    PARTICIPANT_INFO_LO = 0.60

    def run(self, rec: TrialRecord, day: int, ctx: Ctx) -> list:
        """Query the vault for every group; returns the blinding_metrics rows released today."""
        released = []
        rs = rater_sites(rec)
        for who, by in LEVELS:
            rows = [c for c in rec["checkins"] if c.get("who") == who and c.get("guess") in ("drug", "control", "dont_know")]
            groups = sorted({g for g in (group_of(c, by) for c in rows) if g})
            cursor = {g: (batches(rec, who, by, g) or [{"window_to": -1}])[-1]["window_to"] for g in groups}
            window = [{"participant": c["participant"], "guess": c["guess"], "g": group_of(c, by)}
                      for c in rows if group_of(c, by) in cursor and c["day"] > cursor[group_of(c, by)] and c["day"] <= day]
            if not window:
                continue
            out = {r["group"]: r for r in ctx.vault.blinding_stats(window, "g", REQUESTER)}
            ok = [g for g, r in out.items() if not r["suppressed"]]
            if not ok:
                continue
            cum = {r["group"]: r for r in ctx.vault.blinding_stats(
                [{"participant": c["participant"], "guess": c["guess"], "g": group_of(c, by)}
                 for c in rows if group_of(c, by) in ok and c["day"] <= day], "g", REQUESTER)}
            for g in ok:
                w, cu = out[g], cum[g]
                wd = w["n"] - w["dont_know"]
                wc = round(w["accuracy"] * wd)
                cd = cu["n"] - cu["dont_know"]
                cc = round(cu["accuracy"] * cd)
                lo, hi = stats.wilson(cc, cd) if cd else (None, None)
                prev = batches(rec, who, by, g)
                site = g if by == "site" else (rs.get(g) if by == "rater" else None)
                row = {
                    "module": MODULE, "day": day, "who": who, "by": by, "group": g, "site": site,
                    "n": cu["n"], "dont_know": cu["dont_know"], "n_decisive": cd, "n_correct": cc,
                    "accuracy": cu["accuracy"], "accuracy_lo": None if lo is None else round(lo, 3),
                    "accuracy_hi": None if hi is None else round(hi, 3), "u": cu["u"], "bang_drug": cu["bang_drug"],
                    "suppressed": False, "window_from": cursor[g] + 1, "window_to": day, "window_n": w["n"],
                    "window_correct": wc, "window_decisive": wd,
                    "window_accuracy": round(wc / wd, 3) if wd else None, "synthetic": True,
                }
                rd = reset_day(rec, site) if site else -10 ** 9  # an approved action restarts the window too
                tail = [b for b in prev if b["window_from"] > rd][-(stats.ROLLING_BATCHES - 1):] + [row]
                rc, rn = stats.rolling(tail)
                row["rolling_accuracy"] = round(rc / rn, 3) if rn else None
                if who == "rater":
                    base = 0.0
                    if prev and site is not None and prev[-1]["day"] > reset_day(rec, site):
                        base = prev[-1].get("cusum") or 0.0
                    elif prev and site is None:
                        base = prev[-1].get("cusum") or 0.0
                    row["cusum"] = round(stats.cusum_step(base, wc, wd), 3)
                    row["threshold"] = stats.H
                rec["blinding_metrics"].append(row)
                released.append(row)
        if released:
            names = ", ".join(f"{short_site(r['group'])} {r['who']}s" for r in released[:4])
            log(rec, self.name, f"The vault released {len(released)} new aggregate batch(es) ({names}"
                                f"{', ...' if len(released) > 4 else ''}); smaller groups stay suppressed.")
        self._participant_info(rec, released, ctx)
        return released

    def _participant_info(self, rec: TrialRecord, released: list, ctx: Ctx) -> None:
        """Participant unblinding is expected with psychedelics: information for the report, never an alarm."""
        done = {a["evidence"].get("group") for a in rec["alerts"] if a.get("kind") == "participant_unblinding"}
        for r in released:
            if r["who"] != "participant" or r["group"] in done:
                continue
            if r["accuracy_lo"] is not None and r["accuracy_lo"] > self.PARTICIPANT_INFO_LO and r["n_decisive"] >= 10:
                where = "all sites" if r["group"] == "all" else short_site(r["group"])
                expl = (f"Participants at {where} guess their group right {r['accuracy']:.0%} of the time (95% interval "
                        f"{r['accuracy_lo']:.0%} to {r['accuracy_hi']:.0%}, n={r['n_decisive']}). This is expected with a "
                        "psychedelic and is recorded for the FDA blinding report. No action proposed.")
                rec["alerts"].append({"id": next_id(rec, "alerts", "DOS-AL"), "day": rec["day"], "module": MODULE,
                                      "severity": "info", "kind": "participant_unblinding", "site": r["site"],
                                      "title": f"Participants at {where} largely know their group", "explanation": expl,
                                      "evidence": {"group": r["group"], "accuracy": r["accuracy"], "n": r["n_decisive"],
                                                   "ci": [r["accuracy_lo"], r["accuracy_hi"]], "bang_drug": r["bang_drug"]},
                                      "approval_id": None, "status": "info"})
                ctx.bus.post(self.name, "master", "participant_unblinding",
                             {"group": r["group"], "accuracy": r["accuracy"], "ci": [r["accuracy_lo"], r["accuracy_hi"]],
                              "n": r["n_decisive"], "bang_drug": r["bang_drug"]}, expl)
                log(rec, self.name, expl, "info")
                done.add(r["group"])


class DriftAgent:
    """Decides whether a rise in rater accuracy is real drift, explains it, and proposes a fix for a human."""
    name = "drift_action_agent"
    COOLOFF = 14

    def _alert(self, rec: TrialRecord, site: str, statuses=("open", "action_approved")) -> Optional[dict]:
        return next((a for a in reversed(rec["alerts"]) if a.get("kind") == "rater_drift" and a.get("site") == site
                     and a.get("status") in statuses), None)

    def run(self, rec: TrialRecord, day: int, released: list, ctx: Ctx) -> None:
        for r in released:
            if r["who"] != "rater" or r["by"] != stats.ALARM_BY or (r.get("cusum") or 0) < stats.H:
                continue
            site = r["group"]
            if any(a.get("kind") == "rater_drift" and a.get("site") == site and a.get("status") == "dismissed"
                   and (a.get("decided_day") or 0) + self.COOLOFF > day for a in rec["alerts"]):
                continue
            current = self._alert(rec, site)
            if current and current["status"] == "open":
                current["evidence"] = self.evidence(rec, site)
                continue
            if current:  # an approved action did not stop it
                current["status"] = "superseded"
            self.raise_alert(rec, day, site, ctx, persists=bool(current))
        self.check_resolution(rec, day)

    def evidence(self, rec: TrialRecord, site: str) -> dict:
        rd = reset_day(rec, site)
        sb = [b for b in batches(rec, "rater", "site", site) if b["window_from"] > rd]
        path = stats.cusum_path(sb)
        onset = stats.cusum_onset(sb, path)
        since = [b for b in sb if onset is not None and b["window_from"] >= onset]
        k, n = sum(b["window_correct"] for b in since), sum(b["window_decisive"] for b in since)
        lo, hi = stats.wilson(k, n) if n else (None, None)
        per_rater = {}
        for rid, s in rater_sites(rec).items():
            if s != site:
                continue
            rb = [b for b in batches(rec, "rater", "rater", rid) if onset is not None and b["window_from"] >= onset]
            rn = sum(b["window_decisive"] for b in rb)
            if rn:
                rc = sum(b["window_correct"] for b in rb)
                per_rater[rid] = {"correct": rc, "n": rn, "accuracy": round(rc / rn, 3)}
        cues = {}
        for d in rec["debriefs"]:
            cues[d["site"]] = cues.get(d["site"], 0) + sum(q["type"] == "rater_contact" for q in d["unblinding_cues"])
        return {"site": site, "onset_day_estimate": onset, "correct_since_onset": k, "n_since_onset": n,
                "accuracy_since_onset": round(k / n, 3) if n else None,
                "ci_since_onset": [round(lo, 3), round(hi, 3)] if n else None,
                "expected_accuracy": stats.P0, "cusum": sb[-1]["cusum"] if sb else None, "threshold": stats.H,
                "per_rater": per_rater, "rater_contact_cues_by_site": cues,
                "rule": f"batched Bernoulli CUSUM, p0={stats.P0}, p1={stats.P1}, H={stats.H}"}

    def raise_alert(self, rec: TrialRecord, day: int, site: str, ctx: Ctx, persists: bool = False) -> dict:
        ev = self.evidence(rec, site)
        s = short_site(site)
        here = ev["rater_contact_cues_by_site"].get(site, 0)
        elsewhere = sum(v for k2, v in ev["rater_contact_cues_by_site"].items() if k2 != site)
        quote = next((q["quote"] for d in reversed(rec["debriefs"]) if d["site"] == site
                      for q in d["unblinding_cues"] if q["type"] == "rater_contact"), None)
        if here:
            cause = (f"monitor debriefs record outcome raters in dosing rooms {here} time(s) at {s} "
                     f"({elsewhere} at other sites), for example \"{quote}\". Raters who see sessions can tell who got the drug.")
        else:
            cause = ("no rater contact is recorded in this site's debriefs, so the likely route is patients describing "
                     "their experience during the MADRS interview, or staff talking about sessions.")
        lo, hi = ev["ci_since_onset"]
        expl = (f"Raters at {s} are guessing which group patients are in far more often than chance. Since about day "
                f"{ev['onset_day_estimate']} they were right {ev['correct_since_onset']} of {ev['n_since_onset']} times "
                f"({ev['accuracy_since_onset']:.0%}, 95% interval {lo:.0%} to {hi:.0%}); with working blinding we expect "
                f"at most about {stats.P0:.0%}. The drift score (CUSUM) is {ev['cusum']:.1f}, past the alarm line of "
                f"{stats.H:.1f}{_fa_note()}. Likely cause: {cause}")
        if persists:
            expl = "Drift is back after the approved action. " + expl
        aid = next_id(rec, "alerts", "DOS-AL")
        ap = ctx.approvals.request(
            self.name, MODULE, f"Move {s} raters to remote (central) assessment",
            expl + f" Proposed action: from tomorrow, {s} MADRS interviews are done by video by central raters who never "
                   "attend sessions and do not know the arm. The protocol amendment goes to pre-dosing to draft.",
            {"type": "remote_raters", "site": site, "alert_id": aid}, evidence=ev)
        alert = {"id": aid, "day": day, "module": MODULE, "severity": "critical", "kind": "rater_drift", "site": site,
                 "title": f"Rater blinding drift at {s}", "explanation": expl, "evidence": ev, "approval_id": ap["id"],
                 "status": "open", "action_day": None, "resolved_day": None}
        rec["alerts"].append(alert)
        ctx.bus.post(self.name, "master", "rater_drift",
                     {"alert_id": aid, "site": site, "accuracy": ev["accuracy_since_onset"], "ci": ev["ci_since_onset"],
                      "n": ev["n_since_onset"], "onset_day_estimate": ev["onset_day_estimate"], "cusum": ev["cusum"],
                      "proposed_action": "remote_raters", "approval_id": ap["id"]},
                     f"Rater drift at {s}: {ev['accuracy_since_onset']:.0%} correct since day {ev['onset_day_estimate']}")
        log(rec, self.name, f"Rater drift at {s}: {ev['correct_since_onset']} of {ev['n_since_onset']} correct since day "
                            f"{ev['onset_day_estimate']} (CUSUM {ev['cusum']:.1f}, alarm line {stats.H:.1f}). "
                            "Proposed remote raters; waiting for a human.", "warn")
        return alert

    def on_decision(self, rec: TrialRecord, approval: dict, alert: dict) -> None:
        if approval["status"] == "approved":
            alert["status"], alert["action_day"] = "action_approved", rec["day"]
            log(rec, self.name, f"Remote raters approved for {short_site(alert['site'])}; the drift score restarts so the "
                                "agent can confirm whether drift stops.", "decision")
        else:
            alert["status"], alert["decided_day"] = "dismissed", rec["day"]
            log(rec, self.name, f"Remote raters rejected for {short_site(alert['site'])} by {approval.get('reviewer')}. "
                                f"Monitoring continues; no new alert for this site for {self.COOLOFF} days.", "decision")

    def check_resolution(self, rec: TrialRecord, day: int) -> None:
        for a in rec["alerts"]:
            if a.get("kind") != "rater_drift" or a.get("status") != "action_approved":
                continue
            post = [b for b in batches(rec, "rater", "site", a["site"]) if b["window_from"] > a["action_day"]]
            if len(post) >= 2 and (post[-1].get("cusum") or 0) < stats.H:
                k, n = sum(b["window_correct"] for b in post), sum(b["window_decisive"] for b in post)
                lo, hi = stats.wilson(k, n)
                a.update(status="resolved", resolved_day=day,
                         post_action={"correct": k, "n": n, "accuracy": round(k / n, 3), "ci": [round(lo, 3), round(hi, 3)]})
                log(rec, self.name, f"Drift at {short_site(a['site'])} has stopped: since the action raters are right "
                                    f"{k} of {n} times ({k / n:.0%}, 95% interval {lo:.0%} to {hi:.0%}).", "decision")
