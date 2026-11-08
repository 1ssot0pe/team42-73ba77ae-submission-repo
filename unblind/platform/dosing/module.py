"""Dosing (acute) module: the agents that live inside the trial. Owner: Callum.

Mission: catch blinding failure while the trial can still fix it.

Agents (agents.py, monitor.py), in the order they run each day:
    session_agent        runs scheduled dosing sessions; the monitor debrief is structured the same day
    debrief_agent        notes -> adverse events (severity) and unblinding cues, with quotes; serious events go to a clinician
    checkin_agent        participant check-ins: guess, confidence 0-100, expectancy 0-10; re-asks incomplete answers
    rater_visit_agent    weeks 1, 3, 6: MADRS plus the rater's guess, by rater ID
    missing_data_chaser  reminds next day, escalates after two misses, proposes a site fix when a pattern appears
    blinding_monitor     daily vault aggregates per site and rater (participants: information only)
    drift_action_agent   CUSUM drift decision, explanation with evidence, proposed action for a human
    literature_agent     weekly reference-data proposal from the research pipeline's cached extractions
    primary_lock         posts primary_locked to the master after the last week-6 assessment

Record sections written by this module (contract shapes plus the extra keys listed):
    sessions          {id, schedule_id, participant, site, day, monitor_notes, deviations[], synthetic}
    debriefs          {id, session_id, participant, site, day, notes, method, adverse_events[{term, severity, serious, quote}],
                       unblinding_cues[{type, rater_id, quote}], deviations[], synthetic}
    checkins          contract row + {id, reasked, late, complete, schedule_id, judge_input, raw_text, synthetic}
    outcomes          contract row + {synthetic}
    blinding_metrics  contract row + {module, site, n_decisive, n_correct, window_from, window_to, window_n,
                       window_correct, window_decisive, window_accuracy, rolling_accuracy, cusum, threshold, synthetic}.
                       One row per group per vault release (a group is released when its window holds 5+ guesses).
                       accuracy_lo/hi are Wilson 95% intervals from the released counts.
    alerts            contract row + {kind, site, status, action_day, resolved_day, post_action}
    actions           {day, module, approval_id, type, site, reviewer, effect}
    missing_data      {day, schedule_id, participant, site, kind, status: recovered|lost|escalated, detail}
    literature        {id, day, trial, registry_id, fields, verified, url, status: proposed|accepted|rejected, approval_id, source}
Schedule: executes owner=="dosing" entries of kind dosing_session, monitor_debrief, participant_checkin,
rater_assessment, and sets status to done | late_done | missed | lost.

Messages sent (all to "master", which routes them): rater_drift, participant_unblinding, missing_data,
adverse_event, literature_update, primary_locked.  Received: approval_decided, protocol_amended, enrolment_complete.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from ..core import BaseModule, Ctx, TrialRecord, bottlenecks
from . import stats
from .agents import (MODULE, CHECKIN, CheckinAgent, DebriefAgent, LiteratureAgent, MissingDataChaser, PrimaryLock,
                     RaterVisitAgent, SessionAgent, log, short_site)
from .monitor import BlindingMonitor, DriftAgent, batches, rater_sites, reset_day

EVAL = Path(__file__).resolve().parent / "eval_results" / "drift_eval.json"
DRIFT_SITE_DEFAULT_ONSET = None  # never used by agents: onset comes from the CUSUM change-point estimate


def eval_summary() -> Optional[dict]:
    try:
        return json.loads(EVAL.read_text())
    except Exception:
        return None


class Module(BaseModule):
    name = MODULE
    title = "Dosing: live blinding monitor"
    bottleneck_ids = ["blinding_unmeasured", "blinding_failure", "monitoring_burden"]

    def __init__(self):
        self.session, self.debrief = SessionAgent(), DebriefAgent()
        self.checkin, self.rater = CheckinAgent(), RaterVisitAgent()
        self.missing, self.monitor, self.drift = MissingDataChaser(), BlindingMonitor(), DriftAgent()
        self.literature, self.lock = LiteratureAgent(), PrimaryLock()

    # ------------------------------------------------------------ lifecycle
    def setup(self, rec: TrialRecord, ctx: Ctx) -> None:
        mine = [s for s in rec["schedule"] if s.get("owner") == MODULE]
        log(rec, "dosing_module", f"Dosing agents ready: {len(rec['enrolled'])} participants, {len(mine)} scheduled "
                                  "sessions, check-ins and rater assessments to run.")

    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if not rec["enrolled"] or ctx.world is None:
            return
        self.session.run(rec, day, ctx, self.debrief)
        self.checkin.run(rec, day, ctx)
        self.rater.run(rec, day, ctx)
        self.missing.run(rec, day, ctx, self.checkin, self.rater)
        released = self.monitor.run(rec, day, ctx)
        self.drift.run(rec, day, released, ctx)
        self.literature.run(rec, day, ctx)
        self.lock.run(rec, day, ctx)

    def on_message(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        kind, p = msg.get("kind"), msg.get("payload") or {}
        if kind == "approval_decided":
            self._decided(rec, p, ctx)
        elif kind == "protocol_amended":
            what = str(msg.get("text") or (f"Protocol version {p['version']}" if p.get("version") else "Protocol amended"))
            risk = p.get("risk") if isinstance(p.get("risk"), dict) else {}
            band = f"; predicted unblinding now {risk['band']} ({float(risk['u']):.2f})" if {"band", "u"} <= set(risk) else ""
            log(rec, "dosing_module", f"{what[:160]}{band}. Monitoring continues against the amended protocol.")
        elif kind == "enrolment_complete":
            log(rec, "dosing_module", f"Enrolment complete ({len(rec['enrolled'])} participants); dosing agents standing by.")

    def _decided(self, rec: TrialRecord, a: dict, ctx: Ctx) -> None:
        """Act on a human decision. Nothing changes the trial without one."""
        act = a.get("action") or {}
        typ, site = act.get("type"), act.get("site", "")
        alert = next((x for x in rec["alerts"] if x.get("id") == act.get("alert_id")), None)
        if a["status"] == "approved" and typ in ("remote_raters", "reduce_missing"):
            effect = ctx.world.apply_action(typ, site, rec["day"]) if ctx.world is not None else "no simulator"
            rec["actions"].append({"day": rec["day"], "module": MODULE, "approval_id": a["id"], "type": typ, "site": site,
                                   "reviewer": a.get("reviewer"), "effect": effect})
            log(rec, "dosing_module", f"Applied the action approved by {a.get('reviewer')}: {effect}.", "decision")
        if typ == "remote_raters" and alert:
            self.drift.on_decision(rec, a, alert)
        elif typ in ("reduce_missing", "clinical_review") and alert:
            alert["status"] = "action_approved" if a["status"] == "approved" else "dismissed"
            if typ == "clinical_review" and a["status"] == "approved":
                log(rec, "dosing_module", f"{a.get('reviewer')} confirmed the safety response for {act.get('participant')}.", "decision")
        elif typ == "literature_addition":
            for lit in rec["literature"]:
                if lit["approval_id"] == a["id"]:
                    lit["status"] = "accepted" if a["status"] == "approved" else "rejected"
                    if a["status"] == "approved":
                        ctx.bus.post(self.literature.name, "master", "literature_update",
                                     {"trial": lit["trial"], "registry_id": lit["registry_id"]},
                                     f"{lit['trial']} added to the reference data")

    # ------------------------------------------------------------ UI actions
    def handle(self, rec: TrialRecord, action: str, payload: dict, ctx: Ctx) -> dict:
        if action == "checkin":
            return self.checkin.judge(rec, payload or {}, ctx)
        return {"ok": False, "error": f"dosing has no action '{action}'"}

    # ------------------------------------------------------------ KPIs
    def kpis(self, rec: TrialRecord) -> list:
        due = [s for s in rec["schedule"] if s.get("owner") == MODULE and s.get("kind") == CHECKIN and s.get("day", 99) < rec["day"]]
        done = sum(1 for s in due if s.get("status") in ("done", "late_done"))
        drift = [a for a in rec["alerts"] if a.get("kind") == "rater_drift"]
        first = drift[0] if drift else None
        ev = eval_summary()
        out = []
        if first and first["evidence"].get("onset_day_estimate") is not None:
            onset = first["evidence"]["onset_day_estimate"]
            out.append({"label": "Days from drift onset to alert", "value": first["day"] - onset, "baseline": 90 - onset,
                        "unit": "days", "bottleneck_id": "blinding_failure",
                        "note": f"SYNTHETIC. Onset estimated by the agent (day {onset}). Baseline: found at close-out (day 90)."
                                + (f" Over {ev['n_seeds']} simulated trials: median {ev['cusum']['median_delay_days']} days." if ev else "")})
        else:
            out.append({"label": "Days from drift onset to alert", "value": None, "baseline": 62, "unit": "days",
                        "bottleneck_id": "blinding_failure",
                        "note": "No drift detected yet. Baseline: drift from day 28 found at close-out (day 90)."
                                + (f" Over {ev['n_seeds']} simulated trials: median {ev['cusum']['median_delay_days']} days." if ev else "")})
        if ev:
            out.append({"label": "False drift alarms per trial", "value": ev["cusum"]["false_alarms_per_trial_no_drift"],
                        "baseline": ev["end_of_trial_baseline"]["false_alarms_per_trial_no_drift"], "unit": "per trial",
                        "bottleneck_id": "blinding_failure",
                        "note": f"The price of catching drift weeks earlier: about {ev['cusum']['false_alarms_per_trial_no_drift']} "
                                f"extra human reviews per trial ({ev['n_seeds']} SYNTHETIC trials with no drift). "
                                "Baseline: one end-of-trial check raises none, but finds drift about "
                                f"{ev['end_of_trial_baseline']['delay_days_if_detected']} days late."})
        out.append({"label": "Blinding check-ins completed", "value": round(100 * done / len(due), 1) if due else None,
                    "baseline": 29.5, "unit": "%", "bottleneck_id": "blinding_unmeasured",
                    "note": "Baseline: share of randomised psychedelic trials that assessed blinding at all (JAMA Psychiatry 2026)."})
        aes = [a for d in rec["debriefs"] for a in d["adverse_events"]]
        out.append({"label": "Debriefs structured automatically", "value": len(rec["debriefs"]), "baseline": 0,
                    "unit": "debriefs", "bottleneck_id": "monitoring_burden",
                    "note": f"{len(aes)} adverse events and {sum(len(d['unblinding_cues']) for d in rec['debriefs'])} "
                            "unblinding cues extracted, each with its quote."})
        return out

    # ------------------------------------------------------------ view model
    def view(self, rec: TrialRecord) -> dict:
        bn = bottlenecks()
        cards = [{"title": bn[b]["title"], "body": f"{bn[b]['number']}. {bn[b].get('how_we_tackle', '')}", "tone": "info"}
                 for b in self.bottleneck_ids if b in bn]
        cards.append({"title": "SYNTHETIC trial", "tone": "info",
                      "body": "Every participant, rater, guess and note on this page is simulated. The agents never see "
                              "who got the drug: the vault gives them group totals only and hides any group under 5."})
        for a in [x for x in rec["alerts"] if x.get("module") == MODULE and x.get("kind") != "participant_unblinding"][-6:][::-1]:
            tone = {"open": "bad", "action_approved": "warn", "resolved": "good"}.get(a["status"], "info")
            body = a["explanation"]
            if a.get("post_action"):
                pa = a["post_action"]
                body += f" Since the action: {pa['correct']} of {pa['n']} correct ({pa['accuracy']:.0%})."
            status = {"open": "waiting for a human decision",
                      "action_approved": "action approved, checking it works" if a.get("kind") == "rater_drift" else "action approved",
                      "resolved": "drift stopped", "dismissed": "rejected by a human", "superseded": "drift came back"}.get(a["status"], a["status"])
            cards.append({"title": f"{a['title']} (day {a['day']}, {status})", "body": body, "tone": tone})
        lock = PrimaryLock.locked(rec)
        if lock:
            cards.append({"title": f"Primary endpoint locked on day {lock['day']}", "tone": "good",
                          "body": f"{lock['with_week6']} of {lock['n']} participants have a week-6 MADRS."})

        sites = sorted({s.get("site", "") for s in rec["schedule"] if s.get("owner") == MODULE and s.get("site")})
        rater_ids = sorted({s["rater_id"] for s in rec["schedule"] if s.get("owner") == MODULE and s.get("rater_id")})
        timeline = self._drift_timeline(rec)
        one_site = len({t["site"] for t in timeline}) <= 1
        markers = [{"x": t["day"], "label": t["short"] if one_site else f"{t['short']} {t['site']}"} for t in timeline]
        focus = self._focus_site(rec)
        focus_raters = [r for r in rater_ids if rater_sites(rec).get(r) == focus] if focus else []
        cusum_peak = max((m.get("cusum") or 0 for m in rec["blinding_metrics"]
                          if m.get("module") == MODULE and m["who"] == "rater" and m["by"] == "site"), default=0)
        charts = [
            self._chart(rec, "rater", "site", sites, "rolling_accuracy",
                        "Rater guess accuracy by site, last 3 vault batches (SYNTHETIC)",
                        ref=("Expected with working blinding", stats.P0), markers=markers, y_domain=[0, 1]),
            self._chart(rec, "rater", "rater", focus_raters or rater_ids, "rolling_accuracy",
                        (f"Rater guess accuracy at {short_site(focus)}, by rater, last 3 vault batches (SYNTHETIC)" if focus_raters
                         else "Rater guess accuracy by rater, last 3 vault batches (SYNTHETIC)"),
                        ref=("Expected with working blinding", stats.P0), markers=markers, y_domain=[0, 1]),
            self._chart(rec, "rater", "site", sites, "cusum", "Drift score (CUSUM) by site (SYNTHETIC)",
                        ref=("Alarm line", stats.H), markers=markers,
                        y_domain=[0, math.ceil(max(stats.H * 1.4, cusum_peak * 1.1))]),
            self._chart(rec, "participant", "site", sites, "accuracy",
                        "Participant guess accuracy by site, cumulative (SYNTHETIC, information only)", y_domain=[0, 1]),
        ]

        alerts_tbl = [[a["day"], short_site(a.get("site") or "all"), a["severity"], a["title"], a["status"], a.get("approval_id") or ""]
                      for a in rec["alerts"] if a.get("module") == MODULE][-12:][::-1]
        raters = []
        for rid in sorted({s["rater_id"] for s in rec["schedule"] if s.get("rater_id")}):
            b = batches(rec, "rater", "rater", rid)
            if b:
                x = b[-1]
                raters.append([rid, short_site(x["site"] or ""), x["n_decisive"], f"{x['accuracy']:.0%}",
                               f"{x['accuracy_lo']:.0%} to {x['accuracy_hi']:.0%}", x.get("cusum")])
            else:
                raters.append([rid, "", "under 5", "suppressed", "", ""])
        ci = [[c["day"], c["participant"], short_site(c["site"]), c["who"] + (f" {c['rater_id']}" if c.get("rater_id") else ""),
               c["guess"], c["confidence"], "" if c["expectancy"] is None else c["expectancy"],
               c["channel"] + (" (judge)" if c.get("judge_input") else "") + (" (re-asked)" if c.get("reasked") else "")]
              for c in rec["checkins"]][-15:][::-1]
        db = [[d["day"], d["participant"], short_site(d["site"]),
               "; ".join(f"{a['term']} ({a['severity']})" for a in d["adverse_events"]) or "none",
               "; ".join(q["quote"] for q in d["unblinding_cues"]) or "none"] for d in rec["debriefs"]][-10:][::-1]
        md = [[m["day"], m["participant"], short_site(m["site"]), m["kind"].replace("_", " "), m["status"], m["detail"]]
              for m in rec["missing_data"]][-12:][::-1]
        lit = [[x["day"], x["trial"], x["registry_id"], f"{x['verified']} of {x['fields']}", x["status"]] for x in rec["literature"]]
        ids = [p["id"] for p in rec["enrolled"]]
        return {
            "module": self.name, "title": self.title, "kpis": self.kpis(rec), "cards": cards, "charts": charts,
            "tables": [
                {"title": "Drift timeline (marked on the rater charts)", "columns": ["Day", "Event", "Detail"],
                 "rows": [[t["day"], t["label"], t["detail"]] for t in timeline]},
                {"title": "Alerts", "columns": ["Day", "Site", "Severity", "What", "Status", "Approval"], "rows": alerts_tbl},
                {"title": "Blinding by rater (vault aggregates, SYNTHETIC)",
                 "columns": ["Rater", "Site", "Guesses", "Accuracy", "95% interval", "Drift score"], "rows": raters},
                {"title": "Check-in feed (SYNTHETIC)", "columns": ["Day", "Participant", "Site", "Who", "Guess", "Confidence", "Expectancy", "Channel"], "rows": ci},
                {"title": "Debriefs structured by the agent (SYNTHETIC)", "columns": ["Day", "Participant", "Site", "Adverse events", "Unblinding cues"], "rows": db},
                {"title": "Missing data", "columns": ["Day", "Participant", "Site", "What", "Status", "Detail"], "rows": md},
                {"title": "Literature proposals", "columns": ["Day", "Trial", "Registry", "Fields verified", "Status"], "rows": lit},
            ],
            "forms": [{
                "id": "play_patient", "title": "Play a patient (SYNTHETIC participant)", "action": "checkin",
                "fields": [
                    {"name": "participant", "label": "Participant ID", "type": "select" if ids else "text", "options": ids[:60]},
                    {"name": "answer", "label": "Answer in your own words (optional), e.g. 'pretty sure I got the real drug, 80%, expect 7/10'", "type": "text"},
                    {"name": "guess", "label": "Or pick: which group?", "type": "select", "options": ["", "drug", "control", "dont_know"]},
                    {"name": "confidence", "label": "Confidence (0 to 100)", "type": "text"},
                    {"name": "expectancy", "label": "Expected improvement (0 to 10)", "type": "text"},
                ]}],
        }

    @staticmethod
    def _focus_site(rec) -> Optional[str]:
        """The site the per-rater chart shows: the latest drift alert's site, else the highest current drift score."""
        drift = [a for a in rec["alerts"] if a.get("kind") == "rater_drift"]
        if drift:
            return drift[-1]["site"]
        last: dict = {}
        for m in rec["blinding_metrics"]:
            if m.get("module") == MODULE and m["who"] == "rater" and m["by"] == "site" and m.get("site"):
                last[m["site"]] = m.get("cusum") or 0
        return max(last, key=last.get) if last else None

    @staticmethod
    def _drift_timeline(rec) -> list:
        """Onset estimate, alert, action and resolution for every rater-drift alert, in day order.
        label is for the table; short is the chart marker (the site is added when more than one site drifts)."""
        out = []
        for a in rec["alerts"]:
            if a.get("kind") != "rater_drift":
                continue
            s = short_site(a["site"])
            ev = a.get("evidence") or {}

            def add(day, label, short, detail):
                out.append({"day": day, "site": s, "label": f"{label} {s}", "short": short, "detail": detail})
            if ev.get("onset_day_estimate") is not None:
                add(ev["onset_day_estimate"], "Drift onset (estimated)", "Onset (est.)",
                    "Change point from the CUSUM: first batch after the score last sat at 0.")
            add(a["day"], "Alert", "Alert",
                f"{ev.get('correct_since_onset')} of {ev.get('n_since_onset')} rater guesses correct since onset.")
            if a.get("action_day") is not None:
                add(a["action_day"], "Remote raters approved", "Remote raters", "Approved by a named human.")
            if a.get("resolved_day") is not None:
                pa = a.get("post_action") or {}
                add(a["resolved_day"], "Drift stopped", "Stopped", f"{pa.get('correct')} of {pa.get('n')} correct since the action.")
            if a.get("status") == "dismissed":
                add(a.get("decided_day") or a["day"], "Action rejected", "Rejected", "Monitoring continues.")
        return sorted(out, key=lambda t: t["day"])

    def _chart(self, rec, who, by, groups, field, title, ref=None, markers=None, y_domain=None) -> dict:
        """One row per day from day 1 to today with every series key present: null until the group's first
        vault release, then the last released value (the vault only releases batches of 5 or more guesses)."""
        rows = sorted((m for m in rec["blinding_metrics"] if m.get("module") == MODULE and m["who"] == who and m["by"] == by),
                      key=lambda m: m["day"])
        label = (lambda g: g) if by == "rater" else short_site
        series = [{"key": label(g), "label": label(g)} for g in groups]
        if ref:
            series.append({"key": ref[0], "label": ref[0]})
        latest = {label(g): None for g in groups}
        seen_day = {label(g): None for g in groups}
        site_of = {label(g): (g if by == "site" else rater_sites(rec).get(g)) for g in groups}
        resets = {k: reset_day(rec, s) for k, s in site_of.items() if s} if field == "cusum" else {}
        data, i = [], 0
        for d in range(1, max(rec["day"], 0) + 1):
            while i < len(rows) and rows[i]["day"] <= d:
                v = rows[i].get(field)
                k = label(rows[i]["group"])
                latest[k] = round(v, 3) if isinstance(v, (int, float)) else v
                seen_day[k] = rows[i]["day"]
                i += 1
            pt = {"day": d, **latest}
            for k, r in resets.items():  # show the reset from the day after approval, so the alarm itself stays visible
                if latest[k] is not None and seen_day[k] <= r < d:
                    pt[k] = 0.0
            if ref:
                pt[ref[0]] = ref[1]
            data.append(pt)
        chart = {"title": title, "x": "day", "series": series, "data": data}
        if markers:
            chart["markers"] = markers  # optional extra; the same events are in the "Drift timeline" table
        if y_domain:
            chart["y_domain"] = y_domain
        return chart
