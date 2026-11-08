"""Pre-dosing module (Danny). Parse and review the protocol, apply fixes a human
approves, write recruitment ads, pre-screen applicants, enrol the shortlist after
ONE clinician approval, then build the UNBLIND-BLIND-1 measurement plan and the
schedule that dosing and postdose consume.

After setup the module is event-driven: it reacts to approvals, drift and
literature messages, and to actions from the UI (re-check an edited protocol,
apply through the volunteer portal).
"""
from __future__ import annotations

import difflib
from typing import List

from ..core import DATA, BaseModule, Ctx, TrialRecord
from .agents import (CHECKLIST, CRITERIA, FIXES, M, Enroller, MeasurementPlanner, PreScreeningAgent,
                     ProtocolCoDesigner, ProtocolParser, RecruitmentAgent, fix_satisfied, new_version)

DEFAULT_PROTOCOL = DATA / "protocols" / "example_psilocybin_trd.md"
NUMERIC_FIELDS = ("age", "failed_antidepressants", "months_since_last_psychedelic")
MINUTES_PER_MANUAL_SCREEN = 20      # ASSUMPTION, not a sourced figure
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
        self.screener.run(rec, ctx, ctx.world.applicants(n))
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
        return None   # event-driven after setup

    # ------------------------------------------------------------------ messages
    def on_message(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        kind = msg.get("kind")
        if kind == "approval_decided":
            self._approval_decided(rec, msg.get("payload") or {}, ctx)
        elif kind in ("rater_drift", "participant_unblinding"):
            self._propose_amendment(rec, msg, ctx)
        elif kind == "literature_update":
            self.codesigner = ProtocolCoDesigner()          # reload the calibration
            rec.event(self.codesigner.name, "literature update received: reloaded the calibration", "info", M)
            self.codesigner.review(rec, ctx, reason="re-check after a literature update")

    def _approval_decided(self, rec: TrialRecord, a: dict, ctx: Ctx) -> None:
        action = a.get("action") or {}
        kind = action.get("type")
        approved = a.get("status") == "approved"
        if kind in ("apply_fix", "amendment"):
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
            self.codesigner.apply_fix(rec, ctx, fid, a.get("reviewer", ""))
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
            self.planner.run(rec, ctx)

    def _propose_amendment(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        payload = msg.get("payload") if isinstance(msg.get("payload"), dict) else {}
        site = str(payload.get("site") or payload.get("group") or "a site")
        if site.strip().lower() == "all":
            site = "all sites"
        p = rec.get("protocol") or {}
        central = next((c["present"] for c in (rec.get("design_review") or {}).get("checklist") or []
                        if c.get("id") == "central_raters"), False)
        if central or fix_satisfied(p, "central_raters"):
            rec.event(self.codesigner.name, f"'{msg.get('kind')}' at {site}: protocol already specifies central "
                                            "raters; no amendment", "info", M)
            return
        pending = [x for x in ctx.approvals.pending(M)
                   if (x.get("action") or {}).get("type") == "amendment" and x["action"].get("fix") == "central_raters"]
        if pending:
            rec.event(self.codesigner.name, f"'{msg.get('kind')}' at {site}: a central-rater amendment is already "
                                            "waiting for a human; not asking twice", "info", M)
            return
        title, _change, sentence = FIXES["central_raters"]
        ctx.approvals.request(self.codesigner.name, M,
            f"Protocol amendment: central remote raters only (after drift at {site})",
            f"The dosing agents reported '{msg.get('kind')}' at {site}: {msg.get('text') or 'see the dosing alerts'}. "
            f"Amending the protocol so outcome raters are central, remote and blinded removes the rater's view of the "
            f"session. Approving adds the sentence below, saves a new protocol version and re-checks.",
            {"type": "amendment", "fix": "central_raters"},
            evidence={"sentence_to_add": sentence, "trigger": msg.get("kind"), "site": site})

    # ------------------------------------------------------------------ UI actions
    def handle(self, rec: TrialRecord, action: str, payload: dict, ctx: Ctx) -> dict:
        payload = payload or {}
        if action == "recheck":
            text = str(payload.get("text") or "")
            if not text.strip():
                return {"ok": False, "error": "protocol text is empty"}
            editor = str(payload.get("editor") or "").strip() or "anonymous editor"
            old = (rec.get("protocol") or {}).get("text", "")
            diff = [ln for ln in difflib.unified_diff(old.splitlines(), text.splitlines(), lineterm="", n=0)
                    if ln[:1] in "+-" and not ln.startswith(("+++", "---"))][:40]
            rec["protocol"] = self.parser.run(text, ctx)
            v = new_version(rec, f"edited by {editor}", diff)
            rec.event(self.parser.name, f"{editor} edited the protocol ({len(diff)} changed lines); saved as version "
                                        f"{v['version']}", "decision", M)
            dr = self.codesigner.review(rec, ctx, reason=f"re-check after edit (version {v['version']})")
            ctx.bus.post(M, "master", "protocol_amended", {"version": v["version"], "editor": editor,
                                                           "changes": diff[:10], "risk": dr["risk"]},
                         f"Protocol version {v['version']}: edited by {editor}")
            return {"ok": True, "diff": diff, "risk": dr["risk"], "checklist": dr["checklist"]}
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
                except (TypeError, ValueError):
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
