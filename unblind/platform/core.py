"""UNBLIND platform core: the shared contract every module agent uses.

Three modules (pre-dosing, dosing, post-dosing) never call each other directly.
They read and write one TrialRecord, talk through the MessageBus, ask humans
through the ApprovalQueue, and get blinding statistics only through the Vault.
The master agent drives the clock and routes messages.

Everything a module needs is in `Ctx`. Module contract (see MODULE_CONTRACT.md):

    class Module(BaseModule):
        name = "predose"            # | "dosing" | "postdose"
        def setup(self, rec, ctx): ...          # once, before day 0
        def on_day(self, rec, day, ctx): ...    # every simulated day
        def on_message(self, rec, msg, ctx): ...# messages addressed to this module
        def kpis(self, rec) -> list[dict]: ...  # quantified impact for the UI
"""
from __future__ import annotations

import hashlib
import os
import json
import math
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
TRIALS = Path(os.environ.get("UNBLIND_TRIALS_DIR", DATA / "trials"))  # Vercel: only /tmp is writable

SECTIONS = [
    "protocol", "protocol_versions", "design_review", "recruitment", "applicants", "enrolled",
    "measurement_plan", "schedule", "sessions", "checkins", "debriefs", "outcomes", "blinding_metrics",
    "alerts", "actions", "missing_data", "literature", "followups", "research_questions",
    "exports", "report", "messages", "approvals", "events", "kpis",
]


# ---------------------------------------------------------------------------
# Trial record: one JSON document per trial. No allocation data ever lives here.
# ---------------------------------------------------------------------------
class TrialRecord(dict):
    def __init__(self, trial_id: str, synthetic: bool = True):
        super().__init__()
        self["trial_id"] = trial_id
        self["synthetic"] = synthetic
        self["day"] = -1
        self["phase"] = "design"          # design | recruitment | dosing | follow-up | closed
        self["created"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        for s in SECTIONS:
            self[s] = {} if s in ("protocol", "design_review", "recruitment", "measurement_plan",
                                  "report", "kpis", "exports") else []

    # events are the human-readable timeline the UI shows
    def event(self, agent: str, text: str, level: str = "info", module: str = "", data: Any = None) -> None:
        self["events"].append({"day": self["day"], "t": time.time(), "agent": agent, "module": module,
                               "level": level, "text": text, "data": data})

    def save(self) -> Path:
        TRIALS.mkdir(parents=True, exist_ok=True)
        p = TRIALS / f"{self['trial_id']}.json"
        p.write_text(json.dumps(self, indent=1, default=str))
        return p

    @classmethod
    def load(cls, trial_id: str) -> "TrialRecord":
        d = json.loads((TRIALS / f"{trial_id}.json").read_text())
        r = cls(d["trial_id"], d.get("synthetic", True))
        r.update(d)
        return r


# ---------------------------------------------------------------------------
# Message bus: agents talk by posting messages; the master routes them.
# ---------------------------------------------------------------------------
class MessageBus:
    def __init__(self, rec: TrialRecord):
        self.rec = rec

    def post(self, sender: str, to: str, kind: str, payload: Any = None, text: str = "") -> dict:
        m = {"id": uuid.uuid4().hex[:8], "day": self.rec["day"], "from": sender, "to": to,
             "kind": kind, "payload": payload, "text": text, "delivered": False}
        self.rec["messages"].append(m)
        return m

    def pending(self, to: str) -> List[dict]:
        return [m for m in self.rec["messages"] if not m["delivered"] and (m["to"] == to or m["to"] == "*")]


# ---------------------------------------------------------------------------
# Human approval queue: every action that changes the trial needs a named person.
# ---------------------------------------------------------------------------
class ApprovalQueue:
    """Decisions are announced back to the requesting module as a message
    {kind: "approval_decided", payload: <approval>} so modules react to them in on_message."""

    def __init__(self, rec: TrialRecord, bus: Optional["MessageBus"] = None):
        self.rec = rec
        self.bus = bus

    def request(self, agent: str, module: str, title: str, rationale: str, action: dict,
                evidence: Any = None, auto_policy: Optional[str] = None) -> dict:
        a = {"id": uuid.uuid4().hex[:8], "day": self.rec["day"], "agent": agent, "module": module,
             "title": title, "rationale": rationale, "action": action, "evidence": evidence,
             "status": "pending", "reviewer": None, "comment": "", "decided_day": None,
             "auto_policy": auto_policy}
        self.rec["approvals"].append(a)
        self.rec.event(agent, f"asked a human to approve: {title}", "decision", module)
        return a

    def decide(self, approval_id: str, reviewer: str, decision: str, comment: str = "") -> dict:
        if not reviewer.strip():
            raise ValueError("a named reviewer is required")
        if decision not in ("approved", "rejected"):
            raise ValueError("decision must be approved | rejected")
        for a in self.rec["approvals"]:
            if a["id"] == approval_id and a["status"] == "pending":
                a.update(status=decision, reviewer=reviewer.strip(), comment=comment, decided_day=self.rec["day"])
                self.rec.event(reviewer.strip(), f"{decision}: {a['title']}", "human", a["module"])
                if self.bus is not None:
                    self.bus.post("approvals", a["module"], "approval_decided", dict(a))
                return a
        raise KeyError(approval_id)

    def pending(self, module: Optional[str] = None) -> List[dict]:
        return [a for a in self.rec["approvals"] if a["status"] == "pending" and (module is None or a["module"] == module)]

    def get(self, approval_id: str) -> Optional[dict]:
        return next((a for a in self.rec["approvals"] if a["id"] == approval_id), None)


# ---------------------------------------------------------------------------
# Vault: the ONLY place allocation lives. Agents (and the LLM) get aggregates only.
# ---------------------------------------------------------------------------
MIN_CELL = 5


class Vault:
    """Sealed allocation. Stored in a separate file; never copied into the TrialRecord.

    API for agents:  randomise(), blinding_stats(), unblinded_effect()  (aggregates only)
    API for humans:  unseal(reviewer)  logged, only after database lock.
    """

    def __init__(self, trial_id: str, seed: int = 0):
        self.path = TRIALS / f"{trial_id}.vault.json"
        self._alloc: Dict[str, str] = {}
        self._rng = random.Random(seed)
        self.access_log: List[dict] = []
        if self.path.exists():
            d = json.loads(self.path.read_text())
            self._alloc, self.access_log = d["alloc"], d.get("log", [])

    def __getstate__(self) -> dict:
        return dict(self.__dict__)

    def __setstate__(self, state: dict) -> None:
        # the allocation and access log travel inside the snapshot; the file path is re-pointed at this
        # instance's TRIALS dir (a snapshot may be restored on a different machine with an empty /tmp)
        self.__dict__.update(state)
        self.path = TRIALS / Path(str(state.get("path", "vault.json"))).name

    def _save(self) -> None:
        TRIALS.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"alloc": self._alloc, "log": self.access_log}))

    def _log(self, who: str, what: str) -> None:
        self.access_log.append({"t": time.strftime("%H:%M:%S"), "who": who, "what": what})

    def randomise(self, participants: List[dict], strata_key: str = "stratum", block: int = 4) -> Dict[str, int]:
        """Stratified permuted-block randomisation 1:1. Returns counts per stratum only."""
        by: Dict[str, List[str]] = {}
        for p in participants:
            by.setdefault(str(p.get(strata_key, "all")), []).append(p["id"])
        counts: Dict[str, int] = {}
        for s, ids in by.items():
            seq: List[str] = []
            while len(seq) < len(ids):
                b = ["drug"] * (block // 2) + ["control"] * (block // 2)
                self._rng.shuffle(b)
                seq += b
            for pid, arm in zip(ids, seq):
                self._alloc[pid] = arm
            counts[s] = len(ids)
        self._log("vault", f"randomised {sum(counts.values())} participants in {len(counts)} strata")
        self._save()
        return counts

    def enrolled(self) -> int:
        return len(self._alloc)

    def blinding_stats(self, guesses: List[dict], group_key: str, requester: str) -> List[dict]:
        """guesses: [{participant, guess: 'drug'|'control'|'dont_know', <group_key>: ...}].
        Returns per-group accuracy and Bang blinding index for the drug arm. Groups smaller
        than MIN_CELL are suppressed so no individual allocation can be inferred."""
        self._log(requester, f"blinding_stats by {group_key} on {len(guesses)} guesses")
        groups: Dict[str, List[dict]] = {}
        for g in guesses:
            groups.setdefault(str(g.get(group_key, "all")), []).append(g)
        out = []
        for k, rows in sorted(groups.items()):
            rows = [r for r in rows if r["participant"] in self._alloc]
            n = len(rows)
            if n < MIN_CELL:
                out.append({"group": k, "n": n, "suppressed": True})
                continue
            correct = sum(1 for r in rows if r["guess"] == self._alloc[r["participant"]])
            dk = sum(1 for r in rows if r["guess"] == "dont_know")
            drug = [r for r in rows if self._alloc[r["participant"]] == "drug"]
            nd = len(drug)
            bang = None
            if nd >= MIN_CELL:
                cd = sum(1 for r in drug if r["guess"] == "drug")
                wd = sum(1 for r in drug if r["guess"] == "control")
                bang = round((cd - wd) / nd, 3)   # Bang BI (drug arm): -1..1, 0 = ideal
            acc = correct / max(1, n - dk)
            se = math.sqrt(max(acc * (1 - acc), 1e-6) / max(1, n - dk))
            out.append({"group": k, "n": n, "dont_know": dk, "accuracy": round(acc, 3),
                        "accuracy_lo": round(max(0, acc - 1.96 * se), 3), "accuracy_hi": round(min(1, acc + 1.96 * se), 3),
                        "u": round(max(0.0, 2 * acc - 1), 3), "bang_drug": bang, "suppressed": False})
        return out

    def unblinded_effect(self, outcomes: List[dict], requester: str) -> Optional[dict]:
        """Aggregate drug-minus-control mean change. Only callable after database lock (enforced by caller)."""
        self._log(requester, "unblinded_effect (aggregate)")
        d = [o["change"] for o in outcomes if self._alloc.get(o["participant"]) == "drug"]
        c = [o["change"] for o in outcomes if self._alloc.get(o["participant"]) == "control"]
        if len(d) < MIN_CELL or len(c) < MIN_CELL:
            return None
        md = sum(d) / len(d) - sum(c) / len(c)
        sd = math.sqrt((_var(d) * (len(d) - 1) + _var(c) * (len(c) - 1)) / (len(d) + len(c) - 2))
        se = sd * math.sqrt(1 / len(d) + 1 / len(c))
        return {"md": round(md, 2), "lo": round(md - 1.96 * se, 2), "hi": round(md + 1.96 * se, 2),
                "n_drug": len(d), "n_control": len(c), "sd": round(sd, 2)}

    def effect_by_guess(self, outcomes: List[dict], guesses: Dict[str, str], requester: str) -> List[dict]:
        """Aggregate outcome change by (arm, participant guess). For the close-out report only.
        outcomes: [{participant, change}]; guesses: {participant: 'drug'|'control'|'dont_know'}.
        Cells with fewer than MIN_CELL participants are suppressed."""
        self._log(requester, "effect_by_guess (aggregate)")
        cells: Dict[tuple, List[float]] = {}
        for o in outcomes:
            arm = self._alloc.get(o["participant"])
            g = guesses.get(o["participant"])
            if arm is None or g is None:
                continue
            cells.setdefault((arm, g), []).append(float(o["change"]))
        out = []
        for (arm, g), xs in sorted(cells.items()):
            if len(xs) < MIN_CELL:
                out.append({"arm": arm, "guess": g, "n": len(xs), "suppressed": True})
            else:
                out.append({"arm": arm, "guess": g, "n": len(xs), "mean_change": round(sum(xs) / len(xs), 2),
                            "suppressed": False})
        return out

    def unseal(self, reviewer: str) -> Dict[str, str]:
        if not reviewer.strip():
            raise ValueError("named reviewer required")
        self._log(reviewer, "UNSEALED allocation")
        self._save()
        return dict(self._alloc)

    # world simulator only (never passed to agents)
    def _arm(self, pid: str) -> Optional[str]:
        return self._alloc.get(pid)


def _var(x: List[float]) -> float:
    m = sum(x) / len(x)
    return sum((v - m) ** 2 for v in x) / max(1, len(x) - 1)


# ---------------------------------------------------------------------------
# Bottlenecks: every module states the problem it attacks, with a sourced number.
# ---------------------------------------------------------------------------
def bottlenecks() -> Dict[str, dict]:
    p = DATA / "bottlenecks.json"
    if not p.exists():
        return {}
    return {b["id"]: b for b in json.loads(p.read_text())["bottlenecks"]}


# ---------------------------------------------------------------------------
# Context handed to every module
# ---------------------------------------------------------------------------
@dataclass
class Ctx:
    rec: TrialRecord
    bus: MessageBus
    approvals: ApprovalQueue
    vault: Vault
    llm: Any                      # unblind.llm module (ask_json / ask_text / available)
    rng: random.Random
    world: Any = None             # SYNTHETIC world simulator; modules may only use its public "respond_*" methods
    bottlenecks: Dict[str, dict] = field(default_factory=dict)

    # The llm entry is the `unblind.llm` module, which cannot be pickled: drop it and re-import on load.
    def __getstate__(self) -> dict:
        d = dict(self.__dict__)
        d["llm"] = None
        return d

    def __setstate__(self, state: dict) -> None:
        self.__dict__.update(state)
        from .. import llm as _llm
        self.llm = _llm


class BaseModule:
    name = "base"
    title = ""
    bottleneck_ids: List[str] = []

    def setup(self, rec: TrialRecord, ctx: Ctx) -> None: ...
    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None: ...
    def on_message(self, rec: TrialRecord, msg: dict, ctx: Ctx) -> None: ...
    def kpis(self, rec: TrialRecord) -> List[dict]:
        return []

    def view(self, rec: TrialRecord) -> dict:
        """JSON view model the React app renders generically (see VIEW MODEL in the contract)."""
        return {"module": self.name, "title": self.title, "kpis": self.kpis(rec), "cards": [], "tables": [],
                "charts": [], "forms": []}

    def handle(self, rec: TrialRecord, action: str, payload: dict, ctx: "Ctx") -> dict:
        """Actions sent from the UI (e.g. 'checkin', 'ask_question', 'recheck', 'apply')."""
        return {"ok": False, "error": f"{self.name} has no action '{action}'"}


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]
