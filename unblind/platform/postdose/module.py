"""Post-dosing module: follow-up, researcher questions, harmonised export and the FDA blinding report. Owner: Izzy.

Mission: turn everything the trial collected into evidence a regulator and a scientist
can trust, and make that evidence comparable across trials.

Agents (agents.py), in the order they run each day:
    followup_agent         after the primary lock: weeks 8 and 12 (MADRS, end-of-treatment guess and
                           expectancy, durability vs week 6); chases non-responders twice, then records them lost
    bias_gate_agent        reviews every researcher question (unblinding cues, leading wording, personal data,
                           safety, timing and consent): approve, rewrite or reject; ethics approval before release;
                           nothing is released before the primary lock
    interview_agent        asks released questions to participants who consented to data sharing; themes, no identifiers
    closeout_report_agent  day 90: reported vs expectancy-adjusted effect, blinding over time, alerts and decisions,
                           FDA checklist, limitations; a named person signs it off
    harmoniser             UNBLIND-BLIND-1 export with salted-hash IDs and a consent filter; released only on approval

Record sections written by this module (contract sections, shapes documented here):
    followups           {id, participant, site, visit_week, due_day, day, status: planned|done|late_done|missed|lost|
                         no_consent|after_close, attempts, schedule_id, rater_id, madrs, rater_guess, patient_guess,
                         confidence, expectancy, durability_vs_primary, days_late, synthetic}
    research_questions  {id, day, researcher, text, decision: approve|rewrite|reject, reasons[{check, detail, quote}],
                         rewrite, final_text, method, status: rejected_by_gate|awaiting_ethics|approved_held|released|
                         answered|rejected_by_ethics, approval_id, released_day, asked, skipped_no_consent,
                         answers[{pid (pseudonym), day, answer}], themes[], synthetic}
    exports             {standard, status: not_requested|awaiting_approval|exported|rejected, approval_id, n_rows,
                         n_participants, n_excluded_no_consent, completeness, files[], fields[], preview[], cdisc_note}
                         Files go to data/trials/ (git-ignored).
    report              while collecting: {status: collecting, evidence_log[], primary_lock_day}
                         once drafted: + {standard, effect, blinding, alerts, decisions, actions, followups,
                         research_questions, missing_data, checklist[], limitations[], digest, markdown,
                         status: preview|draft|final|changes_requested, approval_id, signed_by, signed_day}
Schedule: updates `status` of entries with owner "postdose" (kind followup, research_question) if they exist.

Messages sent: question_rejected (to master, log only).
Received: primary_locked (start follow-ups, open the portal), rater_drift, participant_unblinding, adverse_event,
missing_data, protocol_amended, enrolment_complete, literature_update (recorded for the report), approval_decided.
"""
from __future__ import annotations

from typing import List

from ..core import BaseModule, Ctx, TrialRecord, bottlenecks
from . import effects
from .agents import (CLOSE_DAY, MODULE, STANDARD, BiasGateAgent, CloseoutReportAgent, FollowUpAgent, Harmoniser,
                     InterviewAgent, log, lock_day, short_site, state)

RECORDED_KINDS = ("rater_drift", "participant_unblinding", "adverse_event", "missing_data", "protocol_amended",
                  "enrolment_complete", "literature_update")


class Module(BaseModule):
    name = MODULE
    title = "Post-dosing: follow-up, bias gate and FDA blinding report"
    bottleneck_ids = ["small_effects", "nonstandard_data"]

    def __init__(self):
        self.followup, self.gate, self.interview = FollowUpAgent(), BiasGateAgent(), InterviewAgent()
        self.harmoniser, self.report = Harmoniser(), CloseoutReportAgent()

    # ------------------------------------------------------------ lifecycle
    def setup(self, rec: TrialRecord, ctx: Ctx) -> None:
        state(rec)
        rec["exports"].setdefault("standard", STANDARD)
        rec["exports"].setdefault("status", "not_requested")
        log(rec, "postdose_module", f"Post-dosing agents ready for {len(rec['enrolled'])} participants. Follow-ups at weeks 8 "
                                    "and 12 start when the primary endpoint is locked. The researcher question portal is "
                                    "open; approved questions are held until the lock.")

    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        st = state(rec)
        if lock_day(rec) is not None:
            self.followup.run(rec, day, ctx)
            self.gate.release(rec)
            self.interview.run(rec, day, ctx)
        if (day >= CLOSE_DAY or rec.get("phase") in ("close-out", "closed")) and st["status"] in ("collecting", "preview"):
            self.followup.close(rec)
            self.report.draft(rec, ctx, final=True)
            if rec["exports"].get("status") in (None, "not_requested"):
                self.harmoniser.request(rec, ctx, who="closeout")

    def on_message(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        kind, p = msg.get("kind"), msg.get("payload") or {}
        st = state(rec)
        if kind == "approval_decided":
            typ = (p.get("action") or {}).get("type")
            if typ == "release_research_question":
                self.gate.decided(rec, p)
            elif typ == "harmonised_export":
                self.harmoniser.decided(rec, p)
            elif typ == "report_signoff":
                self.report.decided(rec, p)
            return
        if kind == "primary_locked":
            if st["primary_lock_day"] is None:
                st["primary_lock_day"] = rec.get("primary_lock_day") or (p.get("day") if isinstance(p, dict) else None) or rec["day"]
            log(rec, "postdose_module", f"Primary endpoint locked on day {lock_day(rec)}. Starting follow-ups and opening "
                                        "question release (only ethics-approved questions, consenting participants).", "decision")
            if not rec["followups"]:
                self.followup.plan(rec, rec["day"])
            self.gate.release(rec)
            return
        if kind in RECORDED_KINDS:
            summary = msg.get("text") or str(p)[:160]
            st["evidence_log"].append({"day": rec["day"], "kind": kind, "from": msg.get("from"), "summary": str(summary)[:240]})
            if kind in ("rater_drift", "participant_unblinding", "adverse_event"):
                log(rec, "closeout_report_agent", f"Recorded '{kind}' from {msg.get('from')} for the FDA blinding report: "
                                                  f"{str(summary)[:140]}")

    # ------------------------------------------------------------ UI actions
    def handle(self, rec: TrialRecord, action: str, payload: dict, ctx: Ctx) -> dict:
        payload = payload or {}
        state(rec)
        if action == "ask_question":
            text = str(payload.get("question", "")).strip()
            if not text:
                return {"ok": False, "error": "Please type a question."}
            return self.gate.submit(rec, text, str(payload.get("researcher", "")), ctx)
        if action == "sign_off":
            reviewer = str(payload.get("reviewer", "")).strip()
            r = rec["report"]
            if not reviewer:
                return {"ok": False, "error": "A named reviewer is required to sign the report."}
            if r.get("status") != "draft" or not r.get("approval_id"):
                return {"ok": False, "error": f"No report waiting for sign-off (status: {r.get('status')})."}
            a = ctx.approvals.get(r["approval_id"])
            if not a or a["status"] != "pending":
                return {"ok": False, "error": "The sign-off request has already been decided."}
            decision = "rejected" if str(payload.get("decision", "")).lower().startswith("reject") else "approved"
            ctx.approvals.decide(r["approval_id"], reviewer, decision, str(payload.get("comment", "")))
            return {"ok": True, "message": f"Sign-off recorded ({decision}) by {reviewer}."}
        if action == "draft_report":
            if lock_day(rec) is None:
                return {"ok": False, "error": "The report can only be previewed after the primary endpoint is locked."}
            closed = rec["day"] >= CLOSE_DAY or rec.get("phase") in ("close-out", "closed")
            r = self.report.draft(rec, ctx, final=closed)      # after close-out a redraft goes back for sign-off
            return {"ok": True, "message": f"Report {r['status']}.", "markdown": r.get("markdown", "")}
        if action == "request_export":
            return self.harmoniser.request(rec, ctx, who=str(payload.get("requested_by", "")) or "ui")
        return {"ok": False, "error": f"postdose has no action '{action}'"}

    # ------------------------------------------------------------ KPIs
    def kpis(self, rec: TrialRecord) -> List[dict]:
        r, ex = rec["report"], rec["exports"]
        eff = r.get("effect") or {}
        rep, adj = eff.get("reported"), eff.get("primary_adjusted")
        out = [{"label": "Reported vs expectancy-adjusted effect", "unit": "MADRS points",
                "value": adj.get("md") if adj else None, "baseline": rep.get("md") if rep else None,
                "bottleneck_id": "small_effects",
                "note": ("SYNTHETIC. Baseline is the reported (naive) effect; value is the adjusted estimate "
                         f"({adj['method'].split(':')[0].lower()}). Negative favours the drug; planted truth is -4. "
                         "A bound under stated assumptions, not the true effect." if adj and rep else
                         "Appears at close-out (day 90), after the primary endpoint is locked.")}]
        out.append({"label": f"Blinding rows exported in {STANDARD}", "unit": "% complete",
                    "value": ex.get("completeness"), "baseline": round(100 * 4 / 18, 1), "bottleneck_id": "nonstandard_data",
                    "note": (f"{ex.get('n_rows')} rows, {ex.get('n_excluded_no_consent')} withheld for lack of consent. "
                             if ex.get("status") == "exported" else f"Export status: {ex.get('status', 'not requested')}. ")
                            + "Baseline: 4 of 18 real trials reported clean per-arm guess data (our candidate gold set, unverified)."})
        qs = rec["research_questions"]
        changed = sum(1 for q in qs if q["decision"] in ("rewrite", "reject"))
        out.append({"label": "Researcher questions rewritten or blocked by the bias gate", "unit": "questions",
                    "value": changed, "baseline": 0, "bottleneck_id": "blinding_failure",
                    "note": f"{len(qs)} submitted. Without a gate every question reaches participants, including ones "
                            "that reveal the arm or plant expectations."})
        cl = r.get("checklist") or []
        if cl:
            met = sum(1 for c in cl if c["status"] == "met")
            out.append({"label": "FDA guidance items evidenced in the report", "unit": f"of {len(cl)}", "value": met,
                        "baseline": None, "bottleneck_id": "fda_unblinding",
                        "note": "Each item links to the data that evidences it. No standard report exists today."})
        return out

    # ------------------------------------------------------------ view model
    def view(self, rec: TrialRecord) -> dict:
        bn = bottlenecks()
        cards = [{"title": bn[b]["title"], "body": f"{bn[b]['number']}. {bn[b].get('how_we_tackle', '')}", "tone": "info"}
                 for b in self.bottleneck_ids if b in bn]
        cards.append({"title": "SYNTHETIC trial", "tone": "info",
                      "body": "Every participant, answer and score on this page is simulated. The agents never see who got "
                              "the drug: the vault returns group totals only and hides any group under 5."})
        ld = lock_day(rec)
        cards.append({"title": f"Primary endpoint locked on day {ld}" if ld is not None else "Primary endpoint not locked yet",
                      "tone": "good" if ld is not None else "info",
                      "body": "Follow-ups and question release are running." if ld is not None else
                              "Follow-ups and researcher questions wait for the lock, so nothing here can affect the "
                              "week-6 result. You can still submit questions: they are reviewed now and held."})
        r = rec["report"]
        eff = r.get("effect") or {}
        if r.get("status") in ("preview", "draft", "final", "changes_requested"):
            tone = {"final": "good", "draft": "warn", "changes_requested": "bad"}.get(r["status"], "info")
            rep, rng = eff.get("reported"), eff.get("adjusted_range")
            body = (f"Reported {rep['md']:+.2f} MADRS points (95% CI {rep['lo']:+.2f} to {rep['hi']:+.2f}). "
                    + ((f"Expectancy-adjusted range {rng['lo']:+.2f} to {rng['hi']:+.2f}. " if rng["lo"] != rng["hi"] else
                        f"Expectancy-adjusted estimate {rng['lo']:+.2f} (one method estimable). ") if rng else "")
                    if rep else f"No effect estimate: {eff.get('why_missing', 'not available')}. ")
            body += {"final": f"Signed off by {r.get('signed_by')}.", "draft": "Waiting for a named sign-off.",
                     "preview": "Preview only.", "changes_requested": "Sign-off refused; redraft needed."}[r["status"]]
            cards.append({"title": f"FDA blinding report ({r['status'].replace('_', ' ')})", "body": body, "tone": tone})
            cards.append({"title": "Report preview (markdown, SYNTHETIC)", "body": r.get("markdown", ""), "tone": "info"})
        for q in rec["research_questions"][-3:][::-1]:
            tone = {"reject": "bad", "rewrite": "warn", "approve": "good"}[q["decision"]]
            body = q["summary"] if q.get("summary") else (
                ("Rewritten to: " + q["final_text"] if q["decision"] == "rewrite" else
                 ("Approved as written." if q["decision"] == "approve" else "Rejected.")) + " "
                + " ".join(f"{x['detail']} (\"{x['quote']}\")" for x in q["reasons"]))
            cards.append({"title": f"Bias gate: {q['id']} {q['decision']} ({q['status'].replace('_', ' ')})", "body": body,
                          "tone": tone})

        return {"module": self.name, "title": self.title, "kpis": self.kpis(rec), "cards": cards,
                "charts": self._charts(rec), "tables": self._tables(rec), "forms": self._forms(rec)}

    # ------------------------------------------------------------ view helpers
    @staticmethod
    def _charts(rec: TrialRecord) -> list:
        charts = []
        eff = (rec["report"].get("effect") or {})
        pts = [("Reported", eff.get("reported")), ("Within-trial (patient guess)", eff.get("within_trial")),
               ("Within-trial (patient and rater guess)", eff.get("within_trial_rater")),
               ("Cross-trial calibration", eff.get("cross_trial"))]
        data = [{"estimate": k, "md": e["md"], "lo": e["lo"], "hi": e["hi"], "Planted truth": -4.0}
                for k, e in pts if e and e.get("md") is not None]
        if data:
            charts.append({"title": "Effect estimates, MADRS points, negative favours the drug (SYNTHETIC)", "x": "estimate",
                           "series": [{"key": "md", "label": "Estimate"}, {"key": "lo", "label": "95% CI low"},
                                      {"key": "hi", "label": "95% CI high"}, {"key": "Planted truth", "label": "Planted truth"}],
                           "data": data})
        by_week: dict = {}
        for o in rec["outcomes"]:
            if o.get("madrs") is not None and o.get("visit_week") is not None:
                by_week.setdefault(o["visit_week"], []).append(o["madrs"])
        for f in rec["followups"]:
            if f.get("madrs") is not None:
                by_week.setdefault(f["visit_week"], []).append(f["madrs"])
        if by_week:
            charts.append({"title": "Mean MADRS by visit week, both arms pooled (blinded, SYNTHETIC)", "x": "week",
                           "series": [{"key": "All participants", "label": "All participants"}],
                           "data": [{"week": w, "All participants": round(sum(x) / len(x), 1)} for w, x in sorted(by_week.items())],
                           "y_domain": [0, 60]})
        rows = [m for m in rec["blinding_metrics"] if m.get("who") == "rater" and m.get("by") == "site"
                and m.get("accuracy") is not None and not m.get("suppressed")]
        if rows:
            sites = sorted({short_site(m["group"]) for m in rows})
            latest, data = {}, []
            for d in sorted({m["day"] for m in rows}):
                for m in rows:
                    if m["day"] == d:
                        latest[short_site(m["group"])] = m["accuracy"]
                data.append({"day": d, **latest})
            charts.append({"title": "Rater guess accuracy by site, as recorded in the report (SYNTHETIC)", "x": "day",
                           "series": [{"key": s, "label": s} for s in sites], "data": data, "y_domain": [0, 1]})
        return charts

    @staticmethod
    def _tables(rec: TrialRecord) -> list:
        qs = [[q["id"], q["day"], q["text"], q["decision"], "; ".join(sorted({x["check"] for x in q["reasons"]})) or "none",
               q.get("final_text") or "", q["status"].replace("_", " "), q.get("asked", 0)]
              for q in rec["research_questions"]][::-1]
        counts: dict = {}
        for f in rec["followups"]:
            counts.setdefault(f["visit_week"], {}).setdefault(f["status"], 0)
            counts[f["visit_week"]][f["status"]] += 1
        fu = [[f"Week {w}", ", ".join(f"{k.replace('_', ' ')}: {n}" for k, n in sorted(c.items()))] for w, c in sorted(counts.items())]
        r = rec["report"]
        tables = [
            {"title": "Researcher questions and bias gate decisions", "columns":
             ["ID", "Day", "Question as submitted", "Decision", "Checks raised", "Text released", "Status", "Asked"], "rows": qs},
            {"title": "Follow-up visits (SYNTHETIC)", "columns": ["Visit", "Status counts"], "rows": fu},
        ]
        if r.get("checklist"):
            tables.append({"title": "FDA guidance checklist (July 2026)", "columns": ["Item", "Status", "Evidence"],
                           "rows": [[c["item"], c["status"].replace("_", " "), c["evidence"]] for c in r["checklist"]]})
        eff = r.get("effect") or {}
        est = [[e["method"], e["md"], e["lo"], e["hi"]] for e in (eff.get("reported"), eff.get("within_trial"),
                                                               eff.get("within_trial_rater"), eff.get("cross_trial"))
               if e and e.get("md") is not None]
        if est:
            tables.append({"title": "Effect estimates (MADRS points, drug minus control, SYNTHETIC)",
                           "columns": ["Method", "Estimate", "95% CI low", "95% CI high"], "rows": est})
        if r.get("limitations"):
            tables.append({"title": "Limitations stated on the report", "columns": ["Limitation"],
                           "rows": [[x] for x in r["limitations"]]})
        dec = [[d["decided_day"], d["module"], d["title"], d["status"], d["reviewer"]] for d in r.get("decisions", [])]
        if dec:
            tables.append({"title": "Every human decision in the trial", "columns": ["Day", "Module", "Decision", "Outcome", "Reviewer"],
                           "rows": dec})
        themes = [[q["id"], t["theme"], t.get("n") if t.get("n") is not None else "", t.get("quote", ""), t["method"]]
                  for q in rec["research_questions"] for t in q.get("themes", [])]
        if themes:
            tables.append({"title": "Interview themes (pseudonymised, SYNTHETIC)", "columns": ["Question", "Theme", "Answers", "Quote", "Method"],
                           "rows": themes})
        ex = rec["exports"]
        if ex.get("status") == "exported":
            tables.append({"title": f"{STANDARD} export preview (pseudonymised, SYNTHETIC)", "columns": ex["fields"],
                           "rows": [[row.get(k) for k in ex["fields"]] for row in ex.get("preview", [])]})
        return tables

    @staticmethod
    def _forms(rec: TrialRecord) -> list:
        forms = [{"id": "ask_question", "title": "Researcher question portal (goes through the bias gate)", "action": "ask_question",
                  "fields": [{"name": "researcher", "label": "Your name or team", "type": "text"},
                             {"name": "question", "label": "Question for participants, e.g. 'How intense were the visuals "
                                                           "during your psilocybin session?'", "type": "text"}]}]
        r = rec["report"]
        if r.get("status") == "draft":
            forms.append({"id": "sign_off", "title": "Sign off the FDA blinding report (named person required)", "action": "sign_off",
                          "fields": [{"name": "reviewer", "label": "Your name", "type": "text"},
                                     {"name": "decision", "label": "Decision", "type": "select", "options": ["approve", "reject"]},
                                     {"name": "comment", "label": "Comment", "type": "text"}]})
        if lock_day(rec) is not None and r.get("status") in ("collecting", "preview", "changes_requested"):
            forms.append({"id": "draft_report", "title": "Preview the FDA blinding report now", "action": "draft_report",
                          "fields": []})
        if rec["exports"].get("status") in (None, "not_requested", "rejected") and lock_day(rec) is not None:
            forms.append({"id": "request_export", "title": f"Prepare the {STANDARD} export (needs approval)",
                          "action": "request_export", "fields": [{"name": "requested_by", "label": "Your name", "type": "text"}]})
        return forms
