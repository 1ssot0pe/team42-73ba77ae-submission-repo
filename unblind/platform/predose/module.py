"""Pre-dosing module (Danny). Phases 2 and 3: parse and review the protocol,
apply fixes a human approves, write recruitment ads, pre-screen applicants,
and enrol the shortlist after ONE clinician approval. The measurement plan
and schedule come in Phase 4.
"""
from __future__ import annotations

from ..core import DATA, BaseModule, Ctx, TrialRecord
from .agents import (M, Enroller, PreScreeningAgent, ProtocolCoDesigner, ProtocolParser, RecruitmentAgent,
                     new_version)

DEFAULT_PROTOCOL = DATA / "protocols" / "example_psilocybin_trd.md"


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

    def setup(self, rec: TrialRecord, ctx: Ctx) -> None:
        # 1-3: design
        text = (rec.get("protocol") or {}).get("text") or DEFAULT_PROTOCOL.read_text()
        rec["protocol"] = self.parser.run(text, ctx)
        p = rec["protocol"]
        rec["design_review"] = {"baseline_risk": self.codesigner.risk(p),
                                "baseline_checklist_ok": sum(c["present"] for c in self.codesigner.checklist(p))}
        new_version(rec, "initial draft", [])
        self.codesigner.review(rec, ctx, reason="initial design review")
        # 4-7: recruitment and screening
        self.recruiter.run(rec, ctx)
        rec["phase"] = "recruitment"
        n = int((rec.get("config") or {}).get("n_applicants", 500))
        f = self.screener.run(rec, ctx, ctx.world.applicants(n))
        flagged = [{"id": a["id"], "name": a["name"], "reasons": a["screening"]["reasons"],
                    "evidence": a["screening"]["evidence"]}
                   for a in rec["applicants"] if a["screening"]["decision"] == "needs_clinician"]
        ctx.approvals.request("pre-screening agent", "predose",
            f"Clinician: confirm shortlist of {f['auto_eligible']} eligible applicants and review {f['needs_clinician']} flagged",
            "Final eligibility is a clinician's decision. Flagged applicants stay out unless you say otherwise in the comment "
            "('include flagged' adds those flagged only for medication washout).",
            {"type": "shortlist"}, evidence={"flagged": flagged[:50]})

    def on_message(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        if msg.get("kind") != "approval_decided":
            return
        a = msg.get("payload") or {}
        action = a.get("action") or {}
        kind = action.get("type")
        if kind == "apply_fix":
            if a.get("status") != "approved":
                rec.event(self.codesigner.name, f"fix '{action.get('fix')}' rejected by {a.get('reviewer')}; "
                                                "protocol unchanged and it will not be proposed again", "info", M)
                return
            self.codesigner.apply_fix(rec, ctx, action["fix"], a.get("reviewer", ""))
        elif kind == "shortlist":
            if a.get("status") != "approved":
                rec.event(self.enroller.name, f"shortlist rejected by {a.get('reviewer')}: nobody enrolled", "warn", M)
                return
            self.enroller.run(rec, ctx, a)
