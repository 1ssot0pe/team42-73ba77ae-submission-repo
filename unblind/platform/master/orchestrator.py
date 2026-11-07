"""The master agent. Drives the trial clock, routes messages between module agents,
escalates to humans, isolates failures, and keeps the trial's memory (TrialRecord).

It never touches allocation. It decides WHO should hear about what:

    dosing:   "rater_drift"     -> predose (draft a protocol amendment), postdose (FDA report)
    dosing:   "primary_locked"  -> postdose (start follow-ups, open the question portal)
    approvals:"approval_decided"-> straight to the module that asked

Routing: fixed table for known kinds; Gemini picks recipients for unknown kinds
(when a key is set); otherwise broadcast. Every routing decision is logged.

If a module cannot be imported (a teammate has not merged yet), a labelled STUB
from stubs.py is used so the platform still runs end to end.
"""
from __future__ import annotations

import importlib
import random
import threading
import traceback
from typing import Any, Dict, List, Optional

from ... import llm
from ..core import ApprovalQueue, BaseModule, Ctx, MessageBus, TrialRecord, Vault, bottlenecks
from ..world import World, WorldConfig
from . import stubs

MODULES = ["predose", "dosing", "postdose"]
STUBS = {"predose": stubs.StubPredose, "dosing": stubs.StubDosing, "postdose": stubs.StubPostdose}

ROUTES: Dict[str, List[str]] = {
    "rater_drift": ["predose", "postdose"],
    "participant_unblinding": ["predose", "postdose"],
    "missing_data": ["postdose"],
    "adverse_event": ["postdose"],
    "primary_locked": ["postdose"],
    "protocol_amended": ["dosing", "postdose"],
    "literature_update": ["predose"],
    "enrolment_complete": ["dosing", "postdose"],
    "question_rejected": [],
}
CLOSE_DAY = 90


class Master:
    name = "master"

    def __init__(self, trial_id: str = "DEMO-001", protocol: Optional[dict] = None, seed: int = 42,
                 n_applicants: int = 500, world_cfg: Optional[WorldConfig] = None, auto_approve: bool = False,
                 use_stub_predose: bool = False):
        self.lock = threading.RLock()
        self.rec = TrialRecord(trial_id, synthetic=True)
        self.rec["config"] = {"seed": seed, "n_applicants": n_applicants, "auto_approve": auto_approve}
        if protocol:
            self.rec["protocol"] = protocol
        self.vault = Vault(trial_id, seed=seed)
        self.world = World(self.vault, world_cfg or WorldConfig(seed=seed))
        bus = MessageBus(self.rec)
        self.ctx = Ctx(rec=self.rec, bus=bus, approvals=ApprovalQueue(self.rec, bus), vault=self.vault,
                       llm=llm, rng=random.Random(seed), world=self.world, bottlenecks=bottlenecks())
        self.modules: Dict[str, BaseModule] = {}
        self.module_status: Dict[str, str] = {}
        for m in MODULES:
            if m == "predose" and use_stub_predose:
                self.modules[m], self.module_status[m] = STUBS[m](), "stub"
                continue
            try:
                mod = importlib.import_module(f"unblind.platform.{m}.module")
                self.modules[m], self.module_status[m] = mod.Module(), "real"
            except Exception as e:  # a teammate's module failing must not take the platform down
                self.modules[m], self.module_status[m] = STUBS[m](), "stub"
                self.rec.event("master", f"module '{m}' not available ({type(e).__name__}: {e}); using labelled STUB",
                               "warn", "master")
        self.rec["module_status"] = self.module_status

    # -------------------------------------------------------------- safety
    def _safe(self, mname: str, fn, *a):
        try:
            return fn(*a)
        except Exception as e:
            self.rec.event("master", f"{mname} raised {type(e).__name__}: {e}", "warn", "master",
                           data=traceback.format_exc()[-1500:])
            return None

    # -------------------------------------------------------------- routing
    def _route(self, msg: dict) -> List[str]:
        kind = msg.get("kind", "")
        if kind in ROUTES:
            return ROUTES[kind]
        if llm.available():
            got = llm.ask_json(
                "You route messages between the agents of a clinical trial platform. Modules: predose (protocol "
                "design, recruitment, screening), dosing (sessions, check-ins, blinding monitoring), postdose "
                "(follow-up, researcher questions, FDA report). Choose which modules must receive this message.",
                f"kind={kind}\ntext={msg.get('text', '')}",
                '{"recipients": ["predose|dosing|postdose"], "why": ""}')
            if got and isinstance(got.get("recipients"), list):
                rec = [r for r in got["recipients"] if r in MODULES and r != msg["from"]]
                self.rec.event("master", f"routed '{kind}' to {rec or 'nobody'} (Gemini: {str(got.get('why', ''))[:120]})",
                               "decision", "master")
                return rec
        return [m for m in MODULES if m != msg.get("from")]

    def _deliver(self) -> None:
        for _ in range(6):  # allow short chains of messages within one tick
            pend = [m for m in self.rec["messages"] if not m["delivered"]]
            if not pend:
                return
            for m in pend:
                m["delivered"] = True
                if m["to"] == "master":
                    if m["kind"] == "primary_locked" and not self.rec.get("primary_lock_day"):
                        self.rec["primary_lock_day"] = self.rec["day"]
                        self.rec["phase"] = "follow-up"
                    targets = self._route(m)
                    if targets:
                        self.rec.event("master", f"{m['from']} reported '{m['kind']}': forwarding to {', '.join(targets)}",
                                       "decision", "master")
                    for t in targets:
                        if t in self.modules:
                            self._safe(t, self.modules[t].on_message, self.rec, dict(m, routed_by="master"), self.ctx)
                elif m["to"] in self.modules:
                    self._safe(m["to"], self.modules[m["to"]].on_message, self.rec, m, self.ctx)

    def _auto_approve(self) -> None:
        if not self.rec["config"].get("auto_approve"):
            return
        for a in self.ctx.approvals.pending():
            self.ctx.approvals.decide(a["id"], "demo reviewer (auto-approve ON)", "approved",
                                      "Auto-approved because the demo is fast-forwarding. In real use a named person decides.")

    def _sync_world(self) -> None:
        """Make sure every enrolled participant exists in the simulator."""
        new = [p for p in self.rec["enrolled"] if p["id"] not in self.world.people]
        if new:
            self.world.enrol(new)
        if self.rec["enrolled"] and self.rec["phase"] in ("design", "recruitment"):
            self.rec["phase"] = "dosing"

    def _settle(self) -> None:
        """Run after anything changes: auto-approve (demo), deliver messages, sync the world, save."""
        for _ in range(3):
            self._auto_approve()
            self._deliver()
        self._sync_world()
        self.rec.save()

    # -------------------------------------------------------------- lifecycle
    def setup(self) -> None:
        with self.lock:
            self.rec["day"] = -1
            self.rec["phase"] = "design"
            self.rec.event("master", "trial created; handing the protocol to the pre-dosing agents", "info", "master")
            self._safe("predose", self.modules["predose"].setup, self.rec, self.ctx)
            self._settle()
            for m in ("dosing", "postdose"):
                self._safe(m, self.modules[m].setup, self.rec, self.ctx)
            self._settle()

    def blocked_reason(self) -> Optional[str]:
        if not self.rec["enrolled"]:
            pend = [a["title"] for a in self.ctx.approvals.pending("predose")]
            return ("Waiting for a human: " + "; ".join(pend)) if pend else "No participants enrolled yet."
        return None

    def step(self, days: int = 1) -> dict:
        with self.lock:
            for _ in range(max(1, int(days))):
                if self.rec["phase"] == "closed":
                    break
                reason = self.blocked_reason()
                if reason:
                    return {"advanced": False, "blocked": reason, "day": self.rec["day"]}
                self.rec["day"] += 1
                d = self.rec["day"]
                if d >= CLOSE_DAY:
                    self.rec["phase"] = "close-out"
                for m in MODULES:
                    self._safe(m, self.modules[m].on_day, self.rec, d, self.ctx)
                    self._deliver()
                self._settle()
                if d % 7 == 0:
                    self._weekly_summary(d)
                if d >= CLOSE_DAY:
                    self.rec["phase"] = "closed"
                    self.rec.event("master", "trial closed; FDA blinding report waiting for sign-off", "decision", "master")
            self.rec.save()
            return {"advanced": True, "day": self.rec["day"], "phase": self.rec["phase"]}

    def run_to(self, day: int) -> dict:
        out: dict = {}
        while self.rec["day"] < day and self.rec["phase"] != "closed":
            out = self.step(1)
            if not out.get("advanced"):
                break
        return out

    # -------------------------------------------------------------- human and UI entry points
    def decide(self, approval_id: str, reviewer: str, decision: str, comment: str = "") -> dict:
        with self.lock:
            a = self.ctx.approvals.decide(approval_id, reviewer, decision, comment)
            self._settle()
            return a

    def module_action(self, module: str, action: str, payload: dict) -> dict:
        with self.lock:
            if module not in self.modules:
                return {"ok": False, "error": f"unknown module {module}"}
            res = self._safe(module, self.modules[module].handle, self.rec, action, payload or {}, self.ctx)
            self._settle()
            return res if isinstance(res, dict) else {"ok": False, "error": "module action failed; see timeline"}

    def module_view(self, module: str) -> dict:
        if module not in self.modules:
            return {"error": f"unknown module {module}"}
        v = self._safe(module, self.modules[module].view, self.rec)
        if not isinstance(v, dict):
            v = {"module": module, "title": module, "cards": [{"title": "View failed", "body": "See timeline", "tone": "warn"}]}
        v["status"] = self.module_status.get(module, "?")
        return v

    # -------------------------------------------------------------- summaries
    def _weekly_summary(self, d: int) -> None:
        ev = [e for e in self.rec["events"] if e["day"] > d - 7]
        alerts = [a for a in self.rec["alerts"] if a.get("day", -99) > d - 7]
        pend = len(self.ctx.approvals.pending())
        done = sum(1 for s in self.rec["schedule"] if s.get("status") == "done")
        self.rec.event("master", f"Week {d // 7}: {len(ev)} agent actions, {len(alerts)} new alerts, "
                                 f"{pend} decisions waiting for a human, {done} scheduled tasks done.", "info", "master")

    def kpis(self) -> Dict[str, list]:
        return {m: (self._safe(m, mod.kpis, self.rec) or []) for m, mod in self.modules.items()}

    def message_edges(self) -> List[dict]:
        edges: Dict[tuple, int] = {}
        for m in self.rec["messages"]:
            edges[(m["from"], m["to"])] = edges.get((m["from"], m["to"]), 0) + 1
        return [{"from": a, "to": b, "count": n} for (a, b), n in sorted(edges.items())]

    def state(self) -> dict:
        r = self.rec
        return {
            "trial_id": r["trial_id"], "synthetic": r["synthetic"], "day": r["day"], "phase": r["phase"],
            "close_day": CLOSE_DAY, "primary_lock_day": r.get("primary_lock_day"),
            "module_status": self.module_status, "blocked": self.blocked_reason(),
            "counts": {k: len(r[k]) for k in ("applicants", "enrolled", "schedule", "checkins", "alerts", "events", "messages")},
            "pending_approvals": len(self.ctx.approvals.pending()),
            "auto_approve": r["config"].get("auto_approve", False),
            "gemini": llm.available(),
        }
