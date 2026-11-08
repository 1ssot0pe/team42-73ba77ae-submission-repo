"""Pre-dosing module (Danny). Parse and review the protocol, apply fixes a human
approves, write recruitment ads, pre-screen applicants, enrol the shortlist after
ONE clinician approval, then build the UNBLIND-BLIND-1 measurement plan and the
schedule that dosing and postdose consume.

After setup the module is event-driven: it reacts to approvals, drift and
literature messages, and to actions from the UI (re-check an edited protocol,
apply through the volunteer portal).
"""
from __future__ import annotations

import copy
import difflib
from typing import List

from ..core import DATA, BaseModule, Ctx, TrialRecord
from .agents import (CHECKLIST, CRITERIA, FIXES, M, Enroller, MeasurementPlanner, PreScreeningAgent,
                     ProtocolCoDesigner, ProtocolParser, RecruitmentAgent, fix_satisfied, new_version,
                     protocol_base, protocol_changed_since)

DEFAULT_PROTOCOL = DATA / "protocols" / "example_psilocybin_trd.md"
NUMERIC_FIELDS = ("age", "failed_antidepressants", "months_since_last_psychedelic")
MINUTES_PER_MANUAL_SCREEN = 20      # ASSUMPTION, not a sourced figure
EXPIRED_REVIEWER = "nobody (dosing started before sign-off)"   # an expired fix has no human signer
SHORTLIST_RATIONALE = ("Final eligibility is a clinician's decision. Flagged applicants stay out unless you say otherwise "
                       "in the comment ('include flagged' adds those flagged only for medication washout).")


class Module(BaseModule):
    name = "predose"
    title = "Pre-dosing: design, recruitment and screening"
    bottleneck_ids = ["fda_unblinding", "blinding_failure"]

    def __init__(self):
        self.parser = ProtocolParser()
        self.codesigner = ProtocolCoDesigner()
        self.recruiter = RecruitmentAgent()
        self.screener = PreScreeningAgent()
        self.enroller = Enroller()
        self.planner = MeasurementPlanner()

    # ------------------------------------------------------------------ setup
    def setup(self, rec: TrialRecord, ctx: Ctx) -> None:
        # 1-3: design
        text = (rec.get("protocol") or {}).get("text") or DEFAULT_PROTOCOL.read_text()
        rec["protocol"] = self.parser.run(text, ctx)
        p = rec["protocol"]
        rec["design_review"] = {"baseline_risk": self.codesigner.risk(p),
                                "baseline_checklist_ok": sum(c["present"] for c in self.codesigner.checklist(p))}
        new_version(rec, "initial draft", [])
        self.codesigner.review(rec, ctx, reason="initial design review")
        # 4-7: recruitment and screening, then ONE clinician shortlist approval
        self.recruiter.run(rec, ctx)
        rec["phase"] = "recruitment"
        n = int((rec.get("config") or {}).get("n_applicants", 500))
        self.screener.run(rec, ctx, ctx.world.applicants(n, indication=rec["protocol"].get("indication")))
        self._request_shortlist(rec, ctx, SHORTLIST_RATIONALE)

    def _request_shortlist(self, rec: TrialRecord, ctx: Ctx, rationale: str) -> dict:
        f = rec["recruitment"]["funnel"]
        flagged = [{"id": a["id"], "name": a["name"], "reasons": a["screening"]["reasons"],
                    "evidence": a["screening"]["evidence"]}
                   for a in rec["applicants"] if a["screening"]["decision"] == "needs_clinician"]
        return ctx.approvals.request("pre-screening agent", "predose",
            f"Clinician: confirm shortlist of {f['auto_eligible']} eligible applicants and review {f['needs_clinician']} flagged",
            rationale, {"type": "shortlist"}, evidence={"flagged": flagged[:50]})

    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        # Event-driven after setup. The one daily job: if a rater drift is remembered, check whether dosing's own
        # remote-rater action has been decided (the master may only tell dosing about that decision).
        if (rec.get("design_review") or {}).get("pending_drift"):
            self._check_drift(rec, ctx)

    # ------------------------------------------------------------------ messages
    def on_message(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        kind = msg.get("kind")
        if kind == "approval_decided":
            a = msg.get("payload") or {}
            if a.get("module") == M:
                self._approval_decided(rec, a, ctx)
            elif (rec.get("design_review") or {}).get("pending_drift"):
                self._check_drift(rec, ctx)
        elif kind == "rater_drift":
            self._remember_drift(rec, msg, ctx)
        elif kind == "participant_unblinding":
            self._note_participant_unblinding(rec, msg)
        elif kind == "literature_update":
            self.codesigner = ProtocolCoDesigner()          # reload the calibration
            rec.event(self.codesigner.name, "literature update received: reloaded the calibration", "info", M)
            self.codesigner.review(rec, ctx, reason="re-check after a literature update")

    @staticmethod
    def _stale(rec: TrialRecord, a: dict, what: str, agent: str) -> None:
        action = a.get("action") or {}
        v_now = (rec.get("protocol_versions") or [{}])[-1].get("version", "?")
        rec.event(agent, f"{what} approved by {a.get('reviewer')}, but the protocol changed since this edit was proposed "
                         f"(v{action.get('base_version', '?')} -> v{v_now}); not applied, please re-open the editor and "
                         "save again", "warn", M)

    def _approval_decided(self, rec: TrialRecord, a: dict, ctx: Ctx) -> None:
        action = a.get("action") or {}
        kind = action.get("type")
        approved = a.get("status") == "approved"
        if kind == "amendment_edit":
            editor = action.get("editor") or "anonymous editor"
            if not approved:
                rec.event(self.parser.name, f"protocol edit by {editor} rejected by {a.get('reviewer')}; protocol "
                                            "unchanged", "info", M)
                return
            if protocol_changed_since(rec, action):
                self._stale(rec, a, f"protocol edit by {editor}", self.parser.name)
                return
            self._apply_edit(rec, ctx, str(action.get("text") or ""), editor,
                             f"amendment by {editor}, approved by {a.get('reviewer')}")
        elif kind in ("apply_fix", "amendment"):
            if kind == "apply_fix" and self._expired(rec, a, ctx):      # second guard: never apply an expired fix
                rec.event(self.codesigner.name, f"fix '{action.get('fix')}' was expired: dosing started before it was "
                                                "signed, so it is not applied; edit the protocol to propose an "
                                                "amendment instead", "warn", M)
                return
            if not approved:
                rec.event(self.codesigner.name, f"{kind.replace('_', ' ')} '{action.get('fix')}' rejected by "
                                                f"{a.get('reviewer')}; protocol unchanged"
                                                f"{' and it will not be proposed again' if kind == 'apply_fix' else ''}",
                          "info", M)
                return
            fid = action.get("fix")
            if fid not in FIXES:
                return
            if fix_satisfied(rec.get("protocol") or {}, fid):
                rec.event(self.codesigner.name, f"{kind.replace('_', ' ')} '{fid}' approved by {a.get('reviewer')} is "
                                                "already in the protocol; no new version", "info", M)
                return
            if kind == "apply_fix" and protocol_changed_since(rec, action, allow_fixes=True):
                self._stale(rec, a, f"fix '{fid}'", self.codesigner.name)
                return
            self.codesigner.apply_fix(rec, ctx, fid, a.get("reviewer", ""),
                                      amendment_site=(action.get("site") or "a site") if kind == "amendment" else None)
        elif kind == "shortlist":
            if not approved:
                comment = str(a.get("comment") or "").strip()
                rec.event(self.enroller.name, f"shortlist rejected by {a.get('reviewer')}: nobody enrolled"
                                              f"{f' (comment: {comment})' if comment else ''}; asking the clinician again",
                          "warn", M)
                quoted = f"\"{comment}\"" if comment else "(no comment given)"
                self._request_shortlist(rec, ctx,
                    f"The previous shortlist was rejected by {a.get('reviewer')}, who said: {quoted}. Nobody is enrolled "
                    f"and the trial stays blocked until a clinician approves a shortlist. " + SHORTLIST_RATIONALE)
                return
            self.enroller.run(rec, ctx, a)
            if rec.get("enrolled"):
                self._expire_fixes(rec, ctx)
            self.planner.run(rec, ctx)

    # ------------------------------------------------------------------ enrolment closes the design stage
    def _expire_fixes(self, rec: TrialRecord, ctx: Ctx) -> None:
        """Dosing starts once people are enrolled: design fixes nobody signed expire (not approved, not applied), and
        the design risk is frozen as risk_at_enrolment. Later changes go through protocol amendments."""
        dr = rec.setdefault("design_review", {})
        if "risk_at_enrolment" not in dr:
            dr["risk_at_enrolment"] = copy.deepcopy(dr.get("risk"))
        expired = dr.setdefault("expired_fixes", [])
        for a in ctx.approvals.pending(M):        # the queue's own dicts: a new status takes them out of pending()
            action = a.get("action") or {}
            if action.get("type") != "apply_fix":
                continue
            a.update(status="expired", reviewer=EXPIRED_REVIEWER, decided_day=rec["day"],
                     comment="expired: dosing started")
            expired.append({"id": a["id"], "fix": action.get("fix"), "day": rec["day"]})
            rec.event(self.codesigner.name, f"fix '{action.get('fix')}' expired: dosing started before anyone signed it, "
                                            "so it was not applied. Edit the protocol to propose an amendment instead",
                      "decision", M)

    @staticmethod
    def _expired(rec: TrialRecord, a: dict, ctx: Ctx) -> bool:
        """Was this apply_fix approval expired at enrolment? Checks the payload, the queue's copy and our own log."""
        live = ctx.approvals.get(a.get("id")) or {}
        ids = {e.get("id") for e in (rec.get("design_review") or {}).get("expired_fixes") or []}
        return a.get("status") == "expired" or live.get("status") == "expired" or a.get("id") in ids

    # ------------------------------------------------------------------ dosing signals
    @staticmethod
    def _site_label(payload: dict) -> str:
        site = str(payload.get("site") or payload.get("group") or "a site")
        return "all sites" if site.strip().lower() == "all" else site

    @staticmethod
    def _central_in_protocol(rec: TrialRecord) -> bool:
        central = next((c["present"] for c in (rec.get("design_review") or {}).get("checklist") or []
                        if c.get("id") == "central_raters"), False)
        return bool(central or fix_satisfied(rec.get("protocol") or {}, "central_raters"))

    def _note_participant_unblinding(self, rec: TrialRecord, msg: dict) -> None:
        """Participant unblinding is expected with psychedelics: information for the report, not an amendment."""
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        where = self._site_label(payload)
        bits = []
        if isinstance(payload.get("accuracy"), (int, float)):
            bits.append(f"guess accuracy {payload['accuracy']:.0%}")
        ci = payload.get("ci")
        if isinstance(ci, (list, tuple)) and len(ci) == 2 and all(isinstance(x, (int, float)) for x in ci):
            bits.append(f"95% interval {ci[0]:.0%} to {ci[1]:.0%}")
        if payload.get("n") is not None:
            bits.append(f"n={payload['n']}")
        summary = ", ".join(bits) or str(msg.get("text") or "no details given")[:160]
        dr = rec.setdefault("design_review", {})
        dr.setdefault("participant_unblinding_notes", []).append(
            {"day": rec["day"], "site": where, "summary": summary})
        rec.event(self.codesigner.name, f"participant unblinding at {where} ({summary}) noted for the blinding report; "
                                        "expected with a psychedelic, so no protocol change", "info", M)

    def _remember_drift(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        """Rater drift: wait for the human's decision on dosing's own remote-rater action before asking anything."""
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        site = self._site_label(payload)
        if self._central_in_protocol(rec):
            rec.event(self.codesigner.name, f"'rater_drift' at {site}: protocol already specifies central raters; "
                                            "no amendment", "info", M)
            return
        pend = rec.setdefault("design_review", {}).setdefault("pending_drift", [])
        entry = {"site": site, "raw_site": str(payload.get("site") or payload.get("group") or ""), "day": rec["day"],
                 "alert_id": payload.get("alert_id"), "approval_id": payload.get("approval_id")}
        old = next((e for e in pend if e["site"] == site), None)
        if old:
            old.update({k: v for k, v in entry.items() if v and k != "day"})
        else:
            pend.append(entry)
        rec.event(self.codesigner.name, f"'rater_drift' at {site}: waiting for the decision on the dosing team's "
                                        "remote-rater action before proposing a protocol amendment", "info", M)
        self._check_drift(rec, ctx)

    @staticmethod
    def _matches_drift(a: dict, e: dict) -> bool:
        """Is approval `a` dosing's remote-rater action for the remembered drift `e`?"""
        if a.get("module") != "dosing":
            return False
        act = a.get("action") or {}
        if e.get("approval_id"):
            return a.get("id") == e["approval_id"]
        if e.get("alert_id") and act.get("alert_id"):
            return act["alert_id"] == e["alert_id"]
        typ, title = str(act.get("type") or "").lower(), str(a.get("title") or "")
        if "rater" not in typ and "rater" not in title.lower():
            return False
        names = {n.strip().lower() for n in (e.get("raw_site"), e.get("site")) if n}
        short = {n.split(" (")[0] for n in names}
        if {str(act.get(k) or "").strip().lower() for k in ("site", "group")} & (names | short):
            return True
        return any(n and n in title.lower() for n in names | short)

    def _check_drift(self, rec: TrialRecord, ctx: Ctx) -> None:
        dr = rec.setdefault("design_review", {})
        pend = dr.get("pending_drift") or []
        if not pend:
            return
        used = set(dr.setdefault("drift_dosing_approvals", []))
        ids = {x.get("id") for x in rec.get("approvals") or []}
        keep = []
        for e in pend:
            probe = e if e.get("approval_id") in ids else dict(e, approval_id=None)   # unknown id: match by site
            a = next((x for x in reversed(rec.get("approvals") or []) if x.get("id") not in used
                      and x.get("status") in ("approved", "rejected") and self._matches_drift(x, probe)), None)
            if a is None:
                keep.append(e)
                continue
            used.add(a["id"])
            dr["drift_dosing_approvals"].append(a["id"])
            if a["status"] == "rejected":
                rec.event(self.codesigner.name, f"the dosing remote-rater action at {e['site']} was rejected by "
                                                f"{a.get('reviewer')}; no protocol amendment proposed", "info", M)
                continue
            self._request_central_raters(rec, ctx, e, a)
        dr["pending_drift"] = keep

    def _request_central_raters(self, rec: TrialRecord, ctx: Ctx, e: dict, dosing: dict) -> None:
        site = e["site"]
        if self._central_in_protocol(rec):
            rec.event(self.codesigner.name, f"remote raters approved at {site}, and the protocol already specifies "
                                            "central raters; no amendment", "info", M)
            return
        pending = [x for x in ctx.approvals.pending(M)
                   if (x.get("action") or {}).get("type") == "amendment" and x["action"].get("fix") == "central_raters"]
        if pending:
            rec.event(self.codesigner.name, f"remote raters approved at {site}: a central-rater amendment is already "
                                            "waiting for a human; not asking twice", "info", M)
            return
        _title, _change, sentence = FIXES["central_raters"]
        ctx.approvals.request(self.codesigner.name, M,
            f"Make remote central raters permanent at every site (after drift at {site})",
            f"Raters at {site} drifted and {dosing.get('reviewer')} approved the dosing team's action to move them to "
            f"remote assessment. Amending the protocol makes outcome raters central, remote and blinded at every site, "
            f"so no rater sees a session. Approving adds the sentence below, saves a new protocol version and re-checks.",
            {"type": "amendment", "fix": "central_raters", "site": site, "dosing_approval": dosing.get("id")},
            evidence={"sentence_to_add": sentence, "trigger": "rater_drift", "site": site,
                      "dosing_approval": {"id": dosing.get("id"), "title": dosing.get("title"),
                                          "reviewer": dosing.get("reviewer")}})

    # ------------------------------------------------------------------ UI actions
    def handle(self, rec: TrialRecord, action: str, payload: dict, ctx: Ctx) -> dict:
        payload = payload or {}
        if action == "recheck":
            text = str(payload.get("text") or "")
            if not text.strip():
                return {"ok": False, "error": "protocol text is empty"}
            editor = str(payload.get("editor") or "").strip() or "anonymous editor"
            if not rec.get("enrolled"):
                return self._apply_edit(rec, ctx, text, editor, f"edited by {editor}")
            diff = self._diff(rec, text)
            a = ctx.approvals.request(self.parser.name, M,
                f"Protocol amendment: edit by {editor} ({len(diff)} changed lines)",
                f"{editor} edited the protocol after enrolment. Participants are already enrolled, so the change is a "
                "protocol amendment and needs a named human. Approving saves a new protocol version, re-checks it and "
                "tells the other modules.",
                {"type": "amendment_edit", "text": text, "diff": diff, "editor": editor, **protocol_base(rec)},
                evidence={"diff": diff})
            return {"ok": True, "pending_approval": a["id"], "diff": diff,
                    "message": "Participants are enrolled, so this edit is a protocol amendment: sent for approval"}
        if action == "apply":
            src = payload.get("applicant") if isinstance(payload.get("applicant"), dict) else payload
            a = {k: v for k, v in dict(src).items() if not str(k).startswith("_")}   # never accept hidden keys
            for k in NUMERIC_FIELDS:          # blank stays missing (screen_one then asks a clinician)
                if k not in a:
                    continue
                if a[k] is None or (isinstance(a[k], str) and not a[k].strip()):
                    a.pop(k)
                    continue
                try:
                    if isinstance(a[k], bool):
                        raise ValueError
                    a[k] = int(float(a[k]))
                except (TypeError, ValueError, OverflowError):     # OverflowError: "1e400" is float inf
                    return {"ok": False, "error": f"'{k}' must be a whole number"}
            n = sum(1 for x in rec["applicants"] if x.get("source") == "portal") + 1
            a["id"] = f"PORTAL-{n:04d}"       # ids are always assigned here; any client id is ignored
            a.setdefault("name", "Portal applicant")
            a.setdefault("country", "UK" if str(a.get("phone") or "").replace(" ", "").startswith("+44") else "unknown")
            a["applied_day"] = rec["day"]
            a["source"] = "portal"
            a["screening"] = self.screener.screen_one(a, rec.get("protocol") or {}, ctx)
            rec["applicants"].append(a)
            self._refresh_funnel(rec)
            s = a["screening"]
            rec.event(self.screener.name, f"portal applicant {a['id']}: {s['decision']}"
                                          f"{' (' + '; '.join(s['reasons']) + ')' if s['reasons'] else ''}", "decision", M)
            return {"ok": True, "applicant": a}
        return super().handle(rec, action, payload, ctx)

    @staticmethod
    def _diff(rec: TrialRecord, text: str) -> List[str]:
        old = (rec.get("protocol") or {}).get("text", "")
        return [ln for ln in difflib.unified_diff(old.splitlines(), text.splitlines(), lineterm="", n=0)
                if ln[:1] in "+-" and not ln.startswith(("+++", "---"))][:40]

    def _apply_edit(self, rec: TrialRecord, ctx: Ctx, text: str, editor: str, why: str) -> dict:
        """Shared path for an edited protocol: re-parse, diff, new version, re-check, tell the master."""
        diff = self._diff(rec, text)
        rec["protocol"] = self.parser.run(text, ctx)
        v = new_version(rec, why, diff)
        rec.event(self.parser.name, f"{editor} edited the protocol ({len(diff)} changed lines); saved as version "
                                    f"{v['version']}", "decision", M)
        dr = self.codesigner.review(rec, ctx, reason=f"re-check after edit (version {v['version']})")
        ctx.bus.post(M, "master", "protocol_amended", {"version": v["version"], "editor": editor,
                                                       "changes": diff[:10], "risk": dr["risk"]},
                     f"Protocol version {v['version']}: edited by {editor}")
        return {"ok": True, "diff": diff, "risk": dr["risk"], "checklist": dr["checklist"], "version": v["version"]}

    @staticmethod
    def _refresh_funnel(rec: TrialRecord) -> None:
        dec = [x["screening"]["decision"] for x in rec["applicants"]]
        rec["recruitment"].setdefault("funnel", {}).update(
            applied=len(dec), auto_eligible=dec.count("eligible"), auto_excluded=dec.count("excluded"),
            needs_clinician=dec.count("needs_clinician"), enrolled=len(rec["enrolled"]))

    # ------------------------------------------------------------------ KPIs and view
    def kpis(self, rec: TrialRecord) -> List[dict]:
        apps = rec.get("applicants") or []
        n = len(apps)
        dec = [a["screening"]["decision"] for a in apps]
        auto = dec.count("eligible") + dec.count("excluded")
        review = dec.count("needs_clinician")
        # the ONLY place that reads synthetic ground truth ('_' keys)
        hidden = [a for a in apps if a.get("_hidden_exclusion")]
        caught = sum(1 for a in hidden if "free_text" in a["screening"].get("criteria_hit", []))
        dr = rec.get("design_review") or {}
        risk, base = dr.get("risk") or {}, dr.get("baseline_risk") or {}
        ok = sum(1 for c in dr.get("checklist") or [] if c.get("present"))
        return [
            {"label": "Applicants decided automatically", "value": round(100 * auto / n, 1) if n else 0.0, "baseline": 0,
             "unit": "%", "note": f"{auto} of {n} SYNTHETIC applicants decided by the pre-screening agent; a clinician "
                                  "still confirms the shortlist", "bottleneck_id": None},
            {"label": "Clinician reviews needed", "value": review, "baseline": n, "unit": f"of {n}",
             "note": "Flagged applicants only; the manual process reviews everyone", "bottleneck_id": None},
            {"label": "Staff hours saved", "value": round(auto * MINUTES_PER_MANUAL_SCREEN / 60, 1), "baseline": 0,
             "unit": "hours", "note": f"ASSUMPTION: {MINUTES_PER_MANUAL_SCREEN} minutes per manual screen (not a sourced "
                                      "figure)", "bottleneck_id": None},
            {"label": "Hidden free-text exclusions caught", "value": caught, "baseline": len(hidden),
             "unit": f"of {len(hidden)}", "note": "Hidden disclosures flagged by the free-text check. Evaluation against "
                                                  "synthetic ground truth only (evaluation vs synthetic truth)", "bottleneck_id": None},
            {"label": "FDA checklist items met", "value": ok, "baseline": dr.get("baseline_checklist_ok", 0),
             "unit": f"of {len(CHECKLIST)}", "note": "FDA July 2026 guidance; before (baseline) vs after approved fixes",
             "bottleneck_id": "fda_unblinding"},
            {"label": "Predicted unblinding u", "value": risk.get("u"), "baseline": base.get("u"), "unit": "u",
             "note": "0 is a coin flip, 1 means everyone knew. Before (baseline) vs after fixes. The calibration is "
                     "SYNTHETIC", "bottleneck_id": "blinding_failure"},
        ]

    def view(self, rec: TrialRecord) -> dict:
        v = super().view(rec)
        v["tables"].append({"title": "Screening criteria", "columns": ["Criterion", "Rule", "Why"],
                            "rows": [[label, rule, why] for _cid, label, rule, why in CRITERIA]})
        return v
