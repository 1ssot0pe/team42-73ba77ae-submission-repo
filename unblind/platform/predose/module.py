"""Pre-dosing module (Danny). Phase 2 scope: parse the protocol, review it, and
apply fixes a human approves. Recruitment, screening, enrolment and the schedule
come in Phases 3 and 4.
"""
from __future__ import annotations

from ..core import DATA, BaseModule, Ctx, TrialRecord
from .agents import M, ProtocolCoDesigner, ProtocolParser, new_version

DEFAULT_PROTOCOL = DATA / "protocols" / "example_psilocybin_trd.md"


class Module(BaseModule):
    name = "predose"
    title = "Pre-dosing: design, recruitment and screening"
    bottleneck_ids = ["fda_unblinding", "blinding_failure"]

    def __init__(self):
        self.parser = ProtocolParser()
        self.codesigner = ProtocolCoDesigner()

    def setup(self, rec: TrialRecord, ctx: Ctx) -> None:
        text = (rec.get("protocol") or {}).get("text") or DEFAULT_PROTOCOL.read_text()
        rec["protocol"] = self.parser.run(text, ctx)
        p = rec["protocol"]
        rec["design_review"] = {"baseline_risk": self.codesigner.risk(p),
                                "baseline_checklist_ok": sum(c["present"] for c in self.codesigner.checklist(p))}
        new_version(rec, "initial draft", [])
        self.codesigner.review(rec, ctx, reason="initial design review")

    def on_message(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None:
        if msg.get("kind") != "approval_decided":
            return
        a = msg.get("payload") or {}
        action = a.get("action") or {}
        if action.get("type") != "apply_fix":
            return
        if a.get("status") != "approved":
            rec.event(self.codesigner.name, f"fix '{action.get('fix')}' rejected by {a.get('reviewer')}; protocol unchanged",
                      "info", M)
            return
        self.codesigner.apply_fix(rec, ctx, action["fix"], a.get("reviewer", ""))
