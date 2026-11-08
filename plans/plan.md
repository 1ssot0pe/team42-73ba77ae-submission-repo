# UNBLIND platform: Danny's build plan

> **Who this is for:** Danny, building in VS Code with Claude Sonnet (and parallel sub-agents).
> **How to use it:** work phase by phase. At the end of every phase Sonnet STOPS and waits for Danny to type `CONFIRM PHASE N`. Never start the next phase without it.
> **Repo:** `team42-73ba77ae-submission-repo` (the `unblind` folder). Existing code stays working.

---

## 0. Instructions for the coding agent (read this first, every phase)

You are helping Danny build one part of a hackathon project. Your job is to follow this plan precisely, not to redesign it.

**Before each phase:** re-read Section 1 (North Star) and Section 4 (Non-negotiables). Then read only the phase you are on.

**During each phase:**
1. Touch only the files listed under "Files you create or edit". If something else seems to need changing, STOP and ask Danny.
2. Use the code snippets in this file as the source of truth for names, shapes and signatures. Where a snippet is complete, copy it. Where it is a skeleton, fill in the bodies without changing names, arguments or return shapes.
3. Every agent decision must be logged with `rec.event(agent, text, level, module)`.
4. Every action that changes the trial goes through the ApprovalQueue. No exceptions.
5. Keep a rule-based (no API key) path for every agent. Gemini is an enhancement on top.

**At the end of each phase:**
1. Run the verification commands listed for the phase and paste the output.
2. Tick the acceptance checklist and the drift checklist out loud.
3. Write a 5-line summary: what you built, what you did not build, anything you are unsure of.
4. STOP. Wait for `CONFIRM PHASE N`.

**If you are unsure:** ask. Do not guess at domain logic (blinding, screening criteria, FDA guidance). It is all written here.

---

## 1. North Star (re-read every phase)

**UNBLIND is an agentic platform that runs a psychedelic clinical trial with a team of AI agents, from protocol design to the FDA report, so the trial measures and controls the bias that sinks these drugs.**

- **The problem:** in psychedelic trials, patients know they tripped, and so do the clinicians scoring them. Every result is drug effect plus expectation, stuck together. The FDA's final guidance (July 2026) names this "functional unblinding" as the central threat to validity. It was central to the 2024 rejection of the MDMA application.
- **Why it stays unsolved:** nobody owns blinding as a job. Most trials never measure it. The ones that do measure it differently, and only at the end.
- **What we build:** a master agent coordinating three modules, one per trial phase. Each module is a small team of agents doing real work every simulated day and bringing decisions to a named human.

| Module | Owner | Agents |
|---|---|---|
| **Pre-dosing** | **Danny** | Protocol parser, protocol co-designer, recruitment ad writer, pre-screening, enrolment and randomisation, measurement planner |
| Dosing (acute) | Callum | Check-ins, debriefs, blinding monitor through a sealed vault, drift detection and actions, missing-data chaser, literature agent |
| Post-dosing | Izzy | Follow-ups, researcher question bias gate, harmonised export, FDA blinding report |
| **Master agent + web app** | **Danny** | Clock, message routing, approvals, mission control, volunteer portal |

**Danny's mission:** make the trial start right (pre-dosing), and make the whole platform run as one product (master agent, API, React app, integration).

**What the judges will see (Danny's parts in bold):**
1. **A judge pastes or edits a draft protocol. The agents score its blinding risk, check it against the FDA guidance, propose fixes, and re-check after each approved fix.**
2. **Hundreds of synthetic applicants are screened to a shortlist that a clinician approves. A judge can apply live in the volunteer portal.**
3. Press play: simulated weeks pass; check-ins, debriefs, live blinding chart (Callum).
4. Raters at one site drift; the agent proposes remote raters; the judge approves (Callum, with **Danny's approval inbox**).
5. Close-out FDA blinding report (Izzy).

---

## 2. The bottlenecks Danny's parts attack (quote these exactly)

| Bottleneck | Number and source | How we move it | Metric we show |
|---|---|---|---|
| Regulators demand blinding evidence | FDA final guidance, July 2026: blinding questionnaires, expectancy measures before randomisation and at end of treatment, central blinded raters, alternative controls (Applied Clinical Trials report) | Co-designer checks the protocol against each item and drafts what is missing | FDA checklist items met, before vs after fixes |
| Designs are locked before their risk is predicted | Blinding failure frequently above 90% in psilocybin, LSD and ayahuasca studies; inert-placebo MDMA trials above 85% (systematic review of 112 RCTs, JAMA Psychiatry 2026) | Predict unblinding (u) before the trial; rank fixes | Predicted u, before vs after fixes |
| Blinding is rarely measured | Only 29.5% (33 of 112) trials assessed it (same review) | Measurement planner builds the standard check-in schedule for every participant | Scheduled blinding check-ins per participant |
| Screening is manual | **NO SOURCED NUMBER YET.** Callum is sourcing one. Until then say "commonly reported" with no figure. | Agent decides most applicants automatically; clinicians review only the shortlist and flagged cases | Share decided automatically; clinician reviews needed; staff hours saved (minutes per manual screen stated as an ASSUMPTION) |

**Sense checks (say these out loud if asked):**
- Bigger trials do not reduce bias. They shrink random error, not the error from knowing your group. Pitch recruitment as faster and fairer.
- Pre-screening cannot remove humans. A clinician legally confirms final eligibility. The agent automates the funnel.
- Prior psychedelic use is balanced (stratified), not excluded.
- Behavioural ad targeting by health or drug-use interest is parked: special category data under UK GDPR.
- The risk number comes from a calibration that is SYNTHETIC tonight. The FDA checklist and fixes stand on the guidance alone.

---

## 3. Architecture

```
                         React app (Vite + TS)  :5173
   Mission control | Pre-dosing | Volunteer portal | Dosing | Post-dosing | Evidence engine (link)
                                   │  fetch /api/...
                         FastAPI (backend/main.py)  :8000
                                   │
                           Master agent (orchestrator.py)
              ┌──────────────┬─────┴────────┬──────────────┐
          predose/         dosing/        postdose/      stubs.py (used until a module imports)
          (Danny)          (Callum)       (Izzy)
              └──────── shared core.py ────────┘
     TrialRecord | MessageBus | ApprovalQueue | Vault (sealed allocation) | World (SYNTHETIC simulator)
```

### Repo layout (new parts only; existing files stay as they are)

```
unblind/platform/
  __init__.py
  MODULE_CONTRACT.md        # Danny writes (Phase 0); shared with Callum and Izzy
  core.py                   # Danny (Phase 0)
  world.py                  # Danny (Phase 0)
  master/__init__.py
  master/orchestrator.py    # Danny (Phase 0, extended in Phase 4)
  master/stubs.py           # Danny (Phase 0)
  predose/__init__.py
  predose/agents.py         # Danny (Phases 1 to 4)
  predose/module.py         # Danny (Phases 1 to 4)
  dosing/                   # CALLUM ONLY. Never edit.
  postdose/                 # IZZY ONLY. Never edit.
backend/__init__.py
backend/main.py             # Danny (Phase 5)
frontend/                   # Danny (Phases 6 to 8): Vite + React + TypeScript
data/bottlenecks.json       # Danny (Phase 0)
data/protocols/*.md         # Danny (Phase 1): fictional example protocols
data/trials/                # runtime output (git-ignored)
tests/platform/test_master.py, test_predose.py, test_api.py   # Danny
```

### Shared shapes (the contract)
These are fixed at the end of Phase 0. Changing them later needs a message to Callum and Izzy.

| Record section | Owner | Shape |
|---|---|---|
| `protocol` | predose | `{title, drug, indication, comparator, rater_model, prior_use_policy, sites[], n_target, primary_endpoint{scale, week}, eligibility{inclusion[], exclusion[]}, has_blinding_questionnaire, has_expectancy_measure, design_flags{}, evidence{field: quote}, text}` |
| `protocol_versions` | predose | `[{version, day, digest, why, changes[], text}]` |
| `design_review` | predose | `{risk{u, u_sd, expected_bias_g, band, calibration, design_model}, checklist[{id, item, present, evidence, note}], model_fixes[], proposed_fixes[], blinding_section_md, baseline_risk, baseline_checklist_ok}` |
| `recruitment` | predose | `{ads[{id, text, reading_ease, checks{}}], channels[], parked, funnel{applied, auto_eligible, auto_excluded, needs_clinician, enrolled}, fairness[], strata{}}` |
| `applicants[]` | predose | World applicant dict plus `screening{decision: eligible\|excluded\|needs_clinician, reasons[], criteria_hit[], evidence[]}` |
| `enrolled[]` | predose | `{id, name, site, stratum, prior_psychedelic_use, dosing_day, consents{checkins, data_sharing}}` |
| `measurement_plan` | predose | `{standard: "UNBLIND-BLIND-1", instruments[], primary_week}` |
| `schedule[]` | predose creates; dosing and postdose update `status` | `{id, participant, site, day, kind, owner, instrument, status, rater_id?, visit_week?}`. `kind` is one of `dosing_session, monitor_debrief, participant_checkin, rater_assessment, followup`. `owner` is `dosing` except `followup`, which is `postdose`. |
| `checkins`, `debriefs`, `outcomes`, `blinding_metrics`, `alerts`, `sessions`, `missing_data`, `literature` | dosing | see MODULE_CONTRACT.md |
| `followups`, `research_questions`, `exports`, `report` | postdose | see MODULE_CONTRACT.md |
| `events`, `messages`, `approvals` | core | written only through `rec.event`, `bus.post`, `approvals.request/decide` |

**Message kinds:** `enrolment_complete`, `protocol_amended` (predose sends); `rater_drift`, `participant_unblinding`, `missing_data`, `adverse_event`, `literature_update`, `primary_locked` (dosing sends); `question_rejected` (postdose); `approval_decided` (core sends to the module that asked).

**Simulated timeline:** setup (day -1) is design, recruitment, screening and enrolment. Days 1 to 20 are staggered dosing. Rater visits happen at each participant's weeks 1, 3 and 6. Primary lock comes after the last week-6 visit. Follow-ups are at weeks 8 and 12. Close-out is day 90.

---

## 4. Non-negotiables (drift guard)

1. **Do not edit** `unblind/platform/dosing/`, `unblind/platform/postdose/`, or any existing file outside the lists in this plan (especially `unblind/pipeline.py`, `unblind/agents.py`, `unblind/model.py`, `app/app.py`, `tests/test_pipeline.py`).
2. **Vault only:** nothing outside `core.py` and `world.py` reads allocation. Never call `vault._arm` or read `vault._alloc` from an agent, the API or the frontend.
3. **Synthetic ground truth stays hidden:** keys starting with `_` (for example `_hidden_exclusion`) are never read by agents, and the API strips them. Only `kpis()` may use them, labelled "evaluation vs synthetic truth".
4. **Human gate:** every trial-changing action goes through `ctx.approvals.request(...)`. The clinician shortlist is ONE approval. Auto-approve exists only as a demo toggle and signs as "demo reviewer (auto-approve ON)".
5. **No new infrastructure:** no database, no auth, no websockets, no Docker, no UI kit, no state library. FastAPI + in-memory trials + JSON files. React + plain CSS + recharts + react-router.
6. **No new LLM providers.** Gemini through the existing `unblind/llm.py` only. Every Gemini answer is validated (allowed values, and the quote must appear in the source) before it is used.
7. **Synthetic is labelled** on every page and chart.
8. **Copy:** UK English, plain language, no em dashes in UI text.
9. **Existing tests keep passing:** `pytest -q tests/test_pipeline.py` must stay at 14 passed.
10. **Scope:** Danny does not build dosing or post-dosing logic. Stubs only, labelled STUB.

---

## 5. Building with multiple agents in VS Code

Three lanes can run in parallel once Phase 0 is confirmed. Give each sub-agent ONLY its lane brief plus Sections 0, 1, 3 and 4.

| Lane | Phases | Files | Can start after |
|---|---|---|---|
| **A: Core and master** | 0, 4 (master parts), 5 (API) | core.py, world.py, master/*, backend/*, tests/platform/test_master.py, test_api.py | now |
| **B: Pre-dosing agents** | 1, 2, 3, 4 (planner) | predose/*, data/protocols/*, tests/platform/test_predose.py | Phase 0 confirmed |
| **C: Frontend** | 6, 7, 8 | frontend/* | Phase 5 endpoints exist (it can use the endpoint table in Phase 5 before then) |

**Sub-agent brief template** (paste into each parallel agent):

```
You are Lane <A|B|C> of the UNBLIND build. Read plan.md Sections 0, 1, 3, 4 and your phases: <list>.
Only create or edit: <files>. Never edit: unblind/platform/dosing/, unblind/platform/postdose/, existing unblind/*.py, app/, tests/test_pipeline.py.
Use the shapes and signatures in plan.md exactly. After each phase: run its verification commands, report, STOP.
```

**Merge rule:** Danny merges lanes into his branch `danny/platform`, then into `main` at checkpoints. Pull `main` before each phase. Callum works on `callum/dosing`, Izzy on `izzy/postdose`.

---

## Phase 0: Branch, foundation and contract

**Goal:** the shared foundation every module depends on, so Callum and Izzy can start against it.
**Bottleneck link:** all of them. This is the shared contract that keeps three people from blocking each other.

**Files you create:** `unblind/platform/__init__.py`, `unblind/platform/core.py`, `unblind/platform/world.py`, `unblind/platform/master/__init__.py`, `unblind/platform/master/orchestrator.py`, `unblind/platform/master/stubs.py`, `unblind/platform/predose/__init__.py`, `unblind/platform/MODULE_CONTRACT.md`, `data/bottlenecks.json`, `tests/platform/__init__.py`, `tests/platform/test_master.py`. Append `data/trials/` to `.gitignore`.

**Steps:**
1. `git checkout -b danny/platform`
2. Create the files below. The code is complete: copy it exactly.
3. Create `tests/platform/test_master.py` (snippet below).
4. Commit, push, and send MODULE_CONTRACT.md to Callum and Izzy.

### 0.1 `unblind/platform/core.py` (complete)
```python
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
TRIALS = DATA / "trials"

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
```

### 0.2 `unblind/platform/world.py` (complete, SYNTHETIC simulator)
```python
"""SYNTHETIC world simulator. Stands in for real people, sites and raters so the
platform can be demonstrated end to end. Nothing here is real data.

Agents never read allocation. Only this simulator peeks at the vault (it plays
the role of reality: real patients who got the drug really do feel it).

Planted events the agents should discover on their own:
  * from day DRIFT_DAY, raters at DRIFT_SITE start sitting in on dosing sessions,
    so their guesses become far more accurate (rater unblinding drift)
  * MISSING_SITE misses check-ins more often (data chasing)
  * some applicants disclose an exclusion only in free text (screening must read it)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from .core import Vault

FIRST = ["Alex", "Sam", "Jordan", "Priya", "Tom", "Aisha", "Leo", "Maya", "Ben", "Chloe", "Omar", "Grace",
         "Dan", "Zara", "Kofi", "Ella", "Ravi", "Nina", "Joe", "Ines", "Hugo", "Amara", "Finn", "Lena"]
MEDS = ["none", "sertraline (SSRI)", "escitalopram (SSRI)", "lithium", "venlafaxine (SNRI)", "quetiapine",
        "propranolol", "none", "none", "sertraline (SSRI)"]
SITES = ["Site A (London)", "Site B (Manchester)", "Site C (Bristol)"]


@dataclass
class WorldConfig:
    seed: int = 42
    true_effect: float = 4.0          # true drug benefit on MADRS (points) at primary endpoint
    expectancy_effect: float = 3.0    # extra points of 'improvement' when a patient believes they got drug
    rater_bias: float = 2.0           # extra points when the RATER believes the patient got drug
    drift_site: str = SITES[1]
    drift_day: int = 28
    missing_site: str = SITES[2]


class World:
    def __init__(self, vault: Vault, cfg: Optional[WorldConfig] = None):
        self.v = vault
        self.cfg = cfg or WorldConfig()
        self.rng = random.Random(self.cfg.seed)
        self.people: Dict[str, dict] = {}
        self._baseline: Dict[str, float] = {}

    # ------------------------------------------------------------- recruitment
    def applicants(self, n: int, start_id: int = 1) -> List[dict]:
        r = self.rng
        out = []
        for i in range(start_id, start_id + n):
            age = r.randint(16, 79)
            uk = r.random() < 0.88
            prior = r.choices(["never", "once", "several times"], [0.55, 0.25, 0.20])[0]
            meds = r.choice(MEDS)
            fails = r.choices([0, 1, 2, 3, 4], [0.12, 0.18, 0.35, 0.22, 0.13])[0]
            psychosis = r.random() < 0.04
            bipolar = r.random() < 0.05
            cardio = r.random() < 0.06
            pregnant = r.random() < 0.02
            hidden = r.random() < 0.06
            free = r.choice([
                "I've tried lots of antidepressants and nothing has really helped.",
                "My GP suggested I look into trials.",
                "I read about psilocybin research and want to help.",
                "Depression has affected my work for years.",
                "I'd like to try something different.",
            ])
            if hidden:
                free = r.choice([
                    "I was diagnosed with bipolar disorder last year but I'm stable now.",
                    "I had a psychotic episode at university, but that was a long time ago.",
                    "My cardiologist is monitoring my blood pressure, it's quite high at the moment.",
                ])
            p = {
                "id": f"APP-{i:04d}", "name": f"{r.choice(FIRST)} {chr(65 + r.randint(0, 25))}.",
                "age": age, "phone": ("+44 7" if uk else r.choice(["+1 415", "+33 6", "+49 151"])) + f"{r.randint(100000000, 999999999)}"[:9],
                "country": "UK" if uk else r.choice(["US", "France", "Germany"]),
                "nearest_site": r.choice(SITES), "self_reported_diagnosis": r.choices(
                    ["major depressive disorder", "treatment-resistant depression", "anxiety", "none"], [0.45, 0.35, 0.12, 0.08])[0],
                "failed_antidepressants": fails, "current_medication": meds,
                "history_psychosis": psychosis, "history_bipolar": bipolar, "cardiovascular_condition": cardio,
                "pregnant_or_breastfeeding": pregnant, "prior_psychedelic_use": prior,
                "months_since_last_psychedelic": None if prior == "never" else r.randint(1, 120),
                "can_attend_8_visits": r.random() < 0.9, "consents_to_chatbot_checkins": r.random() < 0.93,
                "consents_to_data_sharing": r.random() < 0.8, "free_text": free,
                "_hidden_exclusion": hidden,      # ground truth for evaluating the screener (agents must not read keys starting with _)
                "applied_day": 0,
            }
            out.append(p)
        return out

    # ------------------------------------------------------------- dosing phase
    def enrol(self, participants: List[dict]) -> None:
        for p in participants:
            self.people[p["id"]] = p
            self._baseline[p["id"]] = self.rng.gauss(32, 4)

    def _believes_drug(self, pid: str, who: str, day: int, site: str) -> float:
        """Probability that `who` (participant|rater|monitor) guesses 'drug'."""
        arm = self.v._arm(pid)
        prior = self.people.get(pid, {}).get("prior_psychedelic_use", "never")
        if who == "participant":
            base = 0.88 if arm == "drug" else 0.25
            if prior != "never":
                base = min(0.97, base + 0.07) if arm == "drug" else max(0.05, base - 0.10)
        elif who == "monitor":
            base = 0.92 if arm == "drug" else 0.15
        else:  # blinded rater
            base = 0.60 if arm == "drug" else 0.42
            if site == self.cfg.drift_site and day >= self.cfg.drift_day:
                base = 0.90 if arm == "drug" else 0.12   # raters started sitting in on sessions
        return base

    def respond_checkin(self, pid: str, day: int, who: str = "participant", site: str = "") -> Optional[dict]:
        site = site or self.people.get(pid, {}).get("site", "")
        miss_p = 0.18 if site == self.cfg.missing_site else 0.05
        if self.rng.random() < miss_p:
            return None
        pd = self._believes_drug(pid, who, day, site)
        x = self.rng.random()
        dk = 0.08 if who == "participant" else 0.05
        guess = "dont_know" if x < dk else ("drug" if self.rng.random() < pd else "control")
        conf = int(min(100, max(0, self.rng.gauss(70 if guess != "dont_know" else 30, 15))))
        expect = None
        if who == "participant":
            expect = int(min(10, max(0, self.rng.gauss(7 if guess == "drug" else 4, 1.5))))
        return {"guess": guess, "confidence": conf, "expectancy": expect}

    def monitor_debrief(self, pid: str, day: int) -> str:
        arm = self.v._arm(pid)
        r = self.rng
        bits = []
        if arm == "drug":
            bits.append(r.choice(["Participant reported strong visual effects for about four hours.",
                                  "Participant was tearful and described a 'profound' experience.",
                                  "Marked perceptual changes from 40 minutes after dosing."]))
            if r.random() < 0.25:
                bits.append(r.choice(["Transient headache in the evening.", "Nausea in the first hour, resolved.",
                                      "Blood pressure rose to 150/95 at 2 hours, settled by 4 hours.",
                                      "Brief anxiety at peak, managed with reassurance."]))
        else:
            bits.append(r.choice(["Participant reported mild relaxation, little else.",
                                  "Participant asked whether they had received the active drug.",
                                  "Session uneventful, participant slept for an hour."]))
            if r.random() < 0.08:
                bits.append("Mild headache, resolved.")
        if r.random() < 0.10:
            bits.append("Outcome rater came into the room briefly during the session.")
        return " ".join(bits)

    def madrs(self, pid: str, day: int, rater_believes_drug: Optional[bool] = None,
              patient_believes_drug: Optional[bool] = None) -> float:
        """MADRS total (0-60, higher = worse). True effect ramps in after dosing (day 1)."""
        arm = self.v._arm(pid)
        base = self._baseline.get(pid, 32.0)
        ramp = min(1.0, max(0.0, day / 21))
        score = base - 6.0 * ramp                                   # everyone improves a bit (placebo response)
        if arm == "drug":
            score -= self.cfg.true_effect * ramp
        if patient_believes_drug:
            score -= self.cfg.expectancy_effect * ramp
        if rater_believes_drug:
            score -= self.cfg.rater_bias * ramp
        return round(min(60, max(0, score + self.rng.gauss(0, 4))), 1)

    def answer_research_question(self, pid: str, question: str) -> str:
        r = self.rng
        return r.choice([
            "It's hard to put into words, but I've felt more connected to people since.",
            "Honestly not much has changed day to day.",
            "Sleep is better. Mood is up and down.",
            "I think about the session a lot. It made me reflect on my family.",
            "I found the check-ins helpful, they kept me on track.",
        ])

    # ------------------------------------------------------------- actions take effect in the world
    def apply_action(self, kind: str, site: str = "", day: int = 0) -> str:
        """Called by an agent AFTER a human approved an action, so the simulation reflects it."""
        if kind == "remote_raters" and site and site == self.cfg.drift_site:
            self.cfg.drift_day = 10 ** 9          # raters no longer sit in on sessions
            return f"{site}: raters moved to remote assessment from day {day}"
        if kind == "reduce_missing" and site == self.cfg.missing_site:
            self.cfg.missing_site = ""
            return f"{site}: reminder protocol improved"
        return "no effect in simulation"
```

### 0.3 `unblind/platform/master/orchestrator.py` (complete)
```python
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
```

### 0.4 `unblind/platform/master/stubs.py` (complete)
```python
"""STUB modules. Used by the master ONLY when the real dosing / postdose module
cannot be imported (before Callum and Izzy merge). They do the minimum so the
platform runs end to end; every view they return is labelled STUB.

Do not extend these. The real modules replace them automatically.
"""
from __future__ import annotations

from ..core import BaseModule, Ctx, TrialRecord


class StubDosing(BaseModule):
    name = "dosing"
    title = "Dosing (STUB until Callum's module is merged)"

    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if not rec["enrolled"]:
            return
        for s in rec["schedule"]:
            if s.get("owner") != "dosing" or s.get("day") != day or s.get("status") != "scheduled":
                continue
            if s["kind"] in ("participant_checkin", "rater_assessment") and ctx.world is not None:
                who = "participant" if s["kind"] == "participant_checkin" else "rater"
                r = ctx.world.respond_checkin(s["participant"], day, who, s.get("site", ""))
                if r is None:
                    s["status"] = "missed"
                    continue
                rec["checkins"].append({"participant": s["participant"], "site": s.get("site", ""), "day": day,
                                        "who": who, "rater_id": s.get("rater_id"), "guess": r["guess"],
                                        "confidence": r["confidence"], "expectancy": r["expectancy"], "channel": "text"})
            s["status"] = "done"
        guesses = [{"participant": c["participant"], "guess": c["guess"], "all": "all"}
                   for c in rec["checkins"] if c["who"] == "participant"]
        if guesses:
            for m in ctx.vault.blinding_stats(guesses, "all", "stub_dosing"):
                rec["blinding_metrics"].append(dict(m, day=day, who="participant", by="overall"))
        last_primary = max((s["day"] for s in rec["schedule"] if s.get("kind") == "rater_assessment"), default=64)
        if day == last_primary + 1 and not rec.get("primary_lock_day"):
            ctx.bus.post("dosing", "master", "primary_locked", {"day": day}, "All week-6 assessments done (stub).")

    def view(self, rec: TrialRecord) -> dict:
        v = super().view(rec)
        v["cards"] = [{"title": "STUB", "body": "Placeholder dosing module. Callum's real module replaces this.", "tone": "warn"}]
        return v


class StubPostdose(BaseModule):
    name = "postdose"
    title = "Post-dosing (STUB until Izzy's module is merged)"

    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if day == 90 and not rec["report"]:
            rec["report"] = {"status": "draft", "stub": True,
                             "markdown": "# FDA blinding report (STUB)\nIzzy's module produces the real report."}
            rec.event("postdose(stub)", "drafted placeholder report", "info", "postdose")

    def view(self, rec: TrialRecord) -> dict:
        v = super().view(rec)
        v["cards"] = [{"title": "STUB", "body": "Placeholder post-dosing module. Izzy's real module replaces this.", "tone": "warn"}]
        return v


class StubPredose(BaseModule):
    """Only for tests of the master before Danny's predose exists: enrols 24 synthetic people."""
    name = "predose"
    title = "Pre-dosing (STUB)"

    def setup(self, rec: TrialRecord, ctx: Ctx) -> None:
        apps = ctx.world.applicants(24)
        sites = ["Site A (London)", "Site B (Manchester)", "Site C (Bristol)"]
        enrolled = []
        for i, a in enumerate(apps):
            site = sites[i % 3]
            enrolled.append({"id": a["id"], "name": a["name"], "site": site,
                             "stratum": f"{site}|{'naive' if a['prior_psychedelic_use'] == 'never' else 'experienced'}",
                             "prior_psychedelic_use": a["prior_psychedelic_use"], "dosing_day": 1 + i % 20,
                             "consents": {"checkins": True, "data_sharing": True}})
        ctx.vault.randomise(enrolled, "stratum")
        rec["enrolled"] = enrolled
        for p in enrolled:
            d = p["dosing_day"]
            rid = "R-" + p["site"][5] + "1"
            rec["schedule"] += [
                {"id": f"{p['id']}-dose", "participant": p["id"], "site": p["site"], "day": d, "kind": "dosing_session", "owner": "dosing", "instrument": "session", "status": "scheduled"},
                {"id": f"{p['id']}-ci1", "participant": p["id"], "site": p["site"], "day": d + 1, "kind": "participant_checkin", "owner": "dosing", "instrument": "UB1-PG", "status": "scheduled"},
            ] + [{"id": f"{p['id']}-rv{w}", "participant": p["id"], "site": p["site"], "day": d + 7 * w, "kind": "rater_assessment",
                  "owner": "dosing", "instrument": "MADRS+UB1-RG", "status": "scheduled", "rater_id": rid} for w in (1, 3, 6)]
        ctx.bus.post("predose", "master", "enrolment_complete", {"n": len(enrolled)})
```

### 0.5 `data/bottlenecks.json` (complete)
```json
{
  "_note": "Seed entries from sources already verified in this project. The research agent extends this file; every number needs a source URL and quote. 'how_we_tackle' says what the platform changes and how it is measured.",
  "bottlenecks": [
    {
      "id": "blinding_unmeasured",
      "module": "dosing",
      "title": "Most psychedelic trials never measure whether blinding held",
      "number": "29.5% (33 of 112) randomised psychedelic trials assessed blinding integrity",
      "source": "Systematic review of blinding integrity in psychedelic RCTs, JAMA Psychiatry 2026 (doi 10.1001/jamapsychiatry.2026.0255), abstract",
      "url": "https://lifeboat.com/blog/2026/04/blinding-integrity-in-psychedelic-randomized-clinical-trials-a-systematic-review",
      "how_we_tackle": "Every enrolled participant and rater gets the same scheduled guess check-in by default, so measurement coverage goes from about 30% of trials to 100% of participants in trials on the platform.",
      "metric": "share of scheduled blinding check-ins completed"
    },
    {
      "id": "blinding_failure",
      "module": "dosing",
      "title": "When blinding is measured, it usually fails",
      "number": "Psilocybin, LSD and ayahuasca studies frequently reported blinding failure above 90% among participants and raters; inert-placebo MDMA trials exceeded 85%",
      "source": "Same 2026 systematic review, abstract",
      "url": "https://lifeboat.com/blog/2026/04/blinding-integrity-in-psychedelic-randomized-clinical-trials-a-systematic-review",
      "how_we_tackle": "Design agent predicts unblinding before the trial and ranks fixes; blinding monitor detects drift per site and per rater within days instead of at the end of the trial.",
      "metric": "days from drift onset to alert"
    },
    {
      "id": "fda_unblinding",
      "module": "predose",
      "title": "The FDA names functional unblinding as the central threat to validity",
      "number": "Final guidance July 2026 asks for blinding questionnaires, expectancy measures before randomisation and at end of treatment, central blinded raters, and alternative controls",
      "source": "FDA guidance 'Psychedelic Drugs: Considerations for Clinical Investigations' (July 2026), as reported by Applied Clinical Trials",
      "url": "https://www.appliedclinicaltrialsonline.com/view/fda-finalizes-guidance-clinical-trial-design-psychedelic-drug-development",
      "how_we_tackle": "The protocol co-designer checks the draft against each guidance item and drafts the missing blinding section; the close-out agent produces the evidence in one standard report.",
      "metric": "guidance checklist items satisfied"
    },
    {
      "id": "monitoring_burden",
      "module": "dosing",
      "title": "Every dosing session needs two trained monitors and a physician on call",
      "number": "Two monitors per session (lead with graduate training and licensure; assistant with 1 year experience) and a physician able to reach the site within 15 minutes",
      "source": "FDA final guidance July 2026, as reported by Applied Clinical Trials",
      "url": "https://www.appliedclinicaltrialsonline.com/view/fda-finalizes-guidance-clinical-trial-design-psychedelic-drug-development",
      "how_we_tackle": "Monitors speak or type a debrief; the debrief agent structures it into adverse events and unblinding cues, so documentation does not compete with patient care.",
      "metric": "debriefs structured automatically"
    },
    {
      "id": "small_effects",
      "module": "postdose",
      "title": "Late-stage effects are small enough that bias matters",
      "number": "COMP005: -3.6 MADRS points vs placebo (95% CI -5.7 to -1.5). COMP006: -3.8 points vs 1 mg psilocybin (95% CI -5.8 to -1.8)",
      "source": "Compass Pathways press releases, 23 June 2025 and 17 February 2026",
      "url": "https://ir.compasspathways.com/News--Events-/news/news-details/2026/Compass-Pathways-Successfully-Achieves-Primary-Endpoint-in-Second-Phase-3-Trial-Evaluating-COMP360-Psilocybin-for-Treatment-Resistant-Depression/default.aspx",
      "how_we_tackle": "The close-out report gives an expectancy-adjusted range next to the reported effect, using the trial's own blinding data plus the cross-trial calibration.",
      "metric": "reported vs adjusted effect, with interval"
    },
    {
      "id": "nonstandard_data",
      "module": "postdose",
      "title": "Blinding data that is collected is not comparable",
      "number": "Of 18 real trials our research agent examined, only 4 reported clean per-arm participant guess data; timing ranged from the dosing day to day 365, and respondents varied (participants, therapists, raters)",
      "source": "UNBLIND candidate gold set, data/gold_candidates.csv (unverified, needs human check)",
      "url": "",
      "how_we_tackle": "One standard instrument set (UNBLIND-BLIND-1) at fixed timepoints for every trial, exported in one harmonised schema.",
      "metric": "share of trials exporting in the standard schema"
    }
  ]
}
```

### 0.6 `unblind/platform/MODULE_CONTRACT.md` (complete; send to Callum and Izzy)
~~~~markdown
# UNBLIND platform: module contract

Three modules, one owner each, never import each other. They share only:

* `TrialRecord` (a JSON dict, `unblind/platform/core.py`)
* `MessageBus` (agent-to-agent messages, routed by the master)
* `ApprovalQueue` (anything that changes the trial needs a named human)
* `Vault` (the only holder of allocation; agents get aggregates only)
* `World` (SYNTHETIC people, sites and raters; modules may call only its public methods,
  and must never read keys that start with `_`)

## Files each module owns

```
unblind/platform/<module>/agents.py   # the agents (classes or functions)
unblind/platform/<module>/module.py   # class Module(BaseModule): setup / on_day / on_message / kpis
(no UI code)                          # the React app renders your module from view(rec); see VIEW MODEL below
tests/platform/test_<module>.py       # offline tests
```

## Timeline (simulated days)

| Day | Who | What |
|---|---|---|
| setup (day -1) | predose | design review, recruitment ads, pre-screening, enrolment, stratified randomisation via `ctx.vault.randomise`, measurement plan, schedule |
| 1 to 20 | dosing | staggered dosing sessions (each participant has a `dosing_day`) |
| dosing_day to dosing_day + 42 | dosing | post-session check-ins, monitor debriefs, rater assessments at weeks 1, 3, 6 (MADRS + rater guess), daily blinding metrics, drift alerts, missing-data chasing, weekly literature scan |
| primary endpoint lock = last participant's week 6 + 1 | dosing -> master | dosing posts `{"kind": "primary_locked"}` to `master` |
| after lock to day 90 | postdose | follow-ups at weeks 8 and 12, researcher question portal (bias gate), harmonised export |
| 90 | postdose | FDA blinding report, close-out |

The master sets `rec["day"]` and `rec["phase"]`, delivers messages, then calls `on_day` on every module.

## Shared record sections (write only your own)

| Section | Owner | Shape |
|---|---|---|
| `protocol` | predose | `{title, drug, indication, comparator, rater_model, sites[], n_target, primary_endpoint{scale, week}, eligibility{inclusion[], exclusion[]}, text}` |
| `protocol_versions` | predose | list of `{version, day, digest, changes[], risk}` |
| `design_review` | predose | `{risk{u, u_sd, expected_bias_g, band}, fixes[], blinding_section_md, checklist[]}` |
| `recruitment` | predose | `{ads[], funnel{applied, auto_eligible, auto_excluded, needs_clinician, enrolled}}` |
| `applicants` | predose | applicant dicts + `screening{decision: eligible / excluded / needs_clinician, reasons[], evidence[]}` |
| `enrolled` | predose | `{id, name, site, stratum, prior_psychedelic_use, dosing_day, consents{...}}` |
| `measurement_plan` | predose | `{instruments[{id, who, question(s), timepoints_days[], purpose}], standard: "UNBLIND-BLIND-1"}` |
| `schedule` | predose creates; dosing and postdose update `status` | `{id, participant, site, day, kind, owner, instrument, status}` where kind is one of `dosing_session, monitor_debrief, participant_checkin, rater_assessment, followup, research_question` |
| `sessions`, `checkins`, `debriefs`, `outcomes`, `blinding_metrics`, `alerts`, `actions`, `missing_data`, `literature` | dosing | see dosing/module.py docstring |
| `followups`, `research_questions`, `exports`, `report` | postdose | see postdose/module.py docstring |

`outcomes` rows: `{participant, site, day, visit_week, madrs, rater_id, rater_guess, patient_guess}`.
`checkins` rows: `{participant, site, day, who: participant|rater|monitor, rater_id, guess: drug|control|dont_know, confidence, expectancy, channel: text|voice}`.
`blinding_metrics` rows: `{day, who, by: overall|site|rater, group, n, accuracy, accuracy_lo, accuracy_hi, u, bang_drug, suppressed}`.
`alerts` rows: `{id, day, module, severity: info|warn|critical, title, explanation, evidence, approval_id}`.

## Rules every agent follows

1. **Vault only.** Never compute anything from allocation. Use `ctx.vault.blinding_stats(...)` (aggregates, min cell 5).
2. **Human gate.** Any action that changes the trial goes through `ctx.approvals.request(...)`. Check the decision on later days with `ctx.approvals.get(id)`.
3. **Explain yourself.** Every decision writes `rec.event(agent, text, level, module)`, where `level` is `info | decision | warn | human`.
4. **Gemini optional.** Use `ctx.llm.available()` and `ctx.llm.ask_json(...)`. Always have a deterministic fallback, so the demo runs with no key.
5. **Bottleneck first.** Your module page opens with its bottleneck(s) from `data/bottlenecks.json`, and `kpis()` returns quantified impact as `[{label, value, baseline, unit, note, bottleneck_id}]`.
6. **Synthetic is labelled.** Anything from `World` is SYNTHETIC and must say so in the UI.
7. UK English, no em dashes in UI copy, plain language.

## Approvals come back as messages

When a human decides, the module that asked receives
`{"kind": "approval_decided", "from": "approvals", "payload": <the approval dict>}` in `on_message`.
Check `payload["status"]` (`approved` / `rejected`), `payload["action"]` (what you asked for) and `payload["reviewer"]`.

## VIEW MODEL (how your module appears in the React app)

Implement `view(self, rec) -> dict` returning only these keys (all optional except module/title):

```python
{
  "module": "dosing", "title": "Dosing: live blinding monitor",
  "kpis":   [{"label": "...", "value": 12, "unit": "days", "baseline": 62, "note": "...", "bottleneck_id": "blinding_failure"}],
  "cards":  [{"title": "Drift at Site B", "body": "Raters guessed right 88% ...", "tone": "warn"}],   # tone: info|warn|good|bad
  "charts": [{"title": "Rater guess accuracy by site", "x": "day",
              "series": [{"key": "Site A", "label": "Site A"}, {"key": "Site B", "label": "Site B"}],
              "data": [{"day": 10, "Site A": 0.52, "Site B": 0.55}, {"day": 11, "Site A": 0.5, "Site B": 0.61}]}],
  "tables": [{"title": "Alerts", "columns": ["Day", "Site", "What"], "rows": [[29, "Site B", "..."]]}],
  "forms":  [{"id": "play_patient", "title": "Play a patient", "action": "checkin",
              "fields": [{"name": "participant", "label": "Participant ID", "type": "text"},
                         {"name": "guess", "label": "Which group?", "type": "select", "options": ["drug", "control", "dont_know"]}]}]
}
```

A form submit calls `handle(self, rec, action, payload, ctx)` with the form values as `payload`.
Return a JSON-able dict, e.g. `{"ok": True, "message": "..."}`.

## Stubs

If your `module.py` cannot be imported, the master uses a labelled STUB (`master/stubs.py`) so the platform still
runs. As soon as your module imports cleanly it replaces the stub automatically.
~~~~

### 0.7 `tests/platform/test_master.py`
```python
import uuid
from unblind.platform.master.orchestrator import Master


def tid():
    return "TEST-" + uuid.uuid4().hex[:6]


def test_master_runs_to_close_with_stubs():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    assert m.rec["enrolled"], "stub predose should enrol people"
    m.run_to(95)
    assert m.rec["phase"] == "closed"
    assert m.rec.get("primary_lock_day") is not None


def test_vault_aggregates_only_and_suppresses_small_groups():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    one = [{"participant": m.rec["enrolled"][0]["id"], "guess": "drug", "g": "x"}]
    assert m.vault.blinding_stats(one, "g", "test")[0]["suppressed"] is True


def test_approval_decision_comes_back_as_message():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    a = m.ctx.approvals.request("tester", "dosing", "Test", "why", {"type": "x"})
    m.decide(a["id"], "Danny", "approved")
    assert any(x["kind"] == "approval_decided" and x["to"] == "dosing" for x in m.rec["messages"])


def test_record_never_contains_allocation():
    m = Master(tid(), use_stub_predose=True)
    m.setup()
    m.run_to(10)
    import json
    assert '"arm"' not in json.dumps(m.rec)
```

**Verify:**
```bash
python -m pytest -q tests/platform/test_master.py
python -m pytest -q tests/test_pipeline.py        # must still be 14 passed
python -c "from unblind.platform.master.orchestrator import Master; m=Master('SMOKE', use_stub_predose=True); m.setup(); print(m.run_to(95)); print(m.state())"
```

**Acceptance:**
- [ ] 4 new tests pass; existing 14 pass
- [ ] Smoke run reaches `phase: closed` with `module_status` all labelled
- [ ] MODULE_CONTRACT.md sent to Callum and Izzy

**Drift check:** no files outside the list; no database or extra packages; stubs labelled STUB.

**STOP. Wait for `CONFIRM PHASE 0`.**

---

## Phase 1: Example protocols and the protocol parser

**Goal:** turn any free-text protocol into the structured `protocol` record, keeping the sentence behind each field.
**Bottleneck link:** you can't predict risk or check FDA items until the design is machine-readable.

**Files:** `data/protocols/example_psilocybin_trd.md`, `data/protocols/example_mdma_ptsd.md`, `unblind/platform/predose/agents.py` (ProtocolParser section), `tests/platform/test_predose.py` (parser tests).

### 1.1 Example protocols (complete, fictional; the weaknesses are deliberate)
`data/protocols/example_psilocybin_trd.md` (weak on purpose: inert placebo, rater attends sessions, no blinding questionnaire, no expectancy measure, prior use ignored, one therapist):
```markdown
# DRAFT protocol (FICTIONAL EXAMPLE): Single-dose psilocybin for treatment-resistant depression

This is a fictional draft written for the UNBLIND demo. It is not a real protocol.

## Design
A randomised, double-blind, placebo-controlled phase 2 trial in 60 adults with treatment-resistant depression at three sites: Site A (London), Site B (Manchester) and Site C (Bristol).
Participants receive a single oral dose of psilocybin 25 mg or an identical-appearing inert placebo capsule, with psychological support before, during and after the session.

## Outcomes
The primary outcome is change from baseline in MADRS total score at week 6.
MADRS is administered by the site psychiatrist, and the rater is present during the dosing session to support the participant.
Secondary outcomes include response and remission at weeks 1, 3 and 6.

## Population
Inclusion criteria:
- Adults aged 18 to 65
- Major depressive episode with at least two failed antidepressant treatments
Exclusion criteria:
- Personal history of psychosis or bipolar disorder
- Uncontrolled hypertension
- Pregnancy or breastfeeding
- Current lithium treatment

## Safety
Each session is attended by a therapist. Adverse events are recorded at each visit.

## Analysis
Mixed model for repeated measures on MADRS change.
```
`data/protocols/example_mdma_ptsd.md` (better on purpose: active placebo, central raters, stratified, guess check, two monitors, 12-month follow-up; still missing an expectancy measure and factorial design):
```markdown
# DRAFT protocol (FICTIONAL EXAMPLE): MDMA-assisted therapy for PTSD with an active control

This is a fictional draft written for the UNBLIND demo. It is not a real protocol.

## Design
A randomised, double-blind phase 2 trial in 80 adults with chronic PTSD at Site A (London) and Site C (Bristol).
Participants receive MDMA 120 mg or an active placebo (niacin 100 mg) during three therapy sessions.
Randomisation is stratified by site and prior psychedelic use.

## Outcomes
The primary outcome is change in CAPS-5 total severity at week 18.
CAPS-5 is administered by central blinded raters by videoconference who do not attend therapy sessions.
At the end of treatment participants and raters are asked to guess allocation.

## Population
Inclusion criteria:
- Adults aged 18 to 65 with PTSD for at least 6 months
Exclusion criteria:
- Personal history of psychosis or bipolar disorder
- Uncontrolled cardiovascular disease
- Pregnancy

## Safety
Two session monitors attend every session and a physician can attend within 15 minutes. An abuse potential assessment is planned.

## Follow-up
Participants are followed for 12 months after the last session.
```

### 1.2 ProtocolParser (key logic; fill in exactly this behaviour)
```python
# unblind/platform/predose/agents.py
import re
from typing import Any, Dict, List, Optional
from ... import model as ubmodel          # existing UNBLIND model (calibration, counterfactuals)
from ..core import Ctx, TrialRecord, digest

M = "predose"
SITES = ["Site A (London)", "Site B (Manchester)", "Site C (Bristol)"]
COMPARATORS = ["inert_placebo", "active_placebo", "low_dose_same_drug", "other_active"]

def _sentences(text): return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if len(s.strip()) > 3]
def _find(text, pattern):  # first sentence matching pattern, for evidence quotes
    rx = re.compile(pattern, re.I); return next((s for s in _sentences(text) if rx.search(s)), None)

class ProtocolParser:
    name = "protocol parser"
    def run(self, text: str, ctx: Ctx) -> dict:
        """Rules first, then optional Gemini refinement. Never raises on odd input."""
        # title: first non-empty line without leading '#'
        # drug: first of psilocybin|mdma|lsd|5-meo-dmt|dmt|ayahuasca|zalsupindole found, else "unknown"
        # indication: 'treatment-resistant' -> treatment-resistant depression; 'ptsd'/'post-traumatic' -> ptsd; 'depress' -> major depressive disorder
        # comparator: niacin|diphenhydramine|methylphenidate|active placebo -> active_placebo;
        #             low-dose / 1 mg comparator -> low_dose_same_drug; escitalopram|sertraline -> other_active; else inert_placebo
        # rater_model: 'central blinded rater' | 'remote rater' | 'videoconference' -> central_remote, else onsite
        # prior_use_policy: 'stratif... prior/psychedelic' -> stratify; exclusion of any prior psychedelic -> exclude; else ignore
        # has_blinding_questionnaire: 'guess' or 'blinding questionnaire|integrity|assessment|index'
        # has_expectancy_measure: 'expectan'
        # n_target: '<N> participants|patients|adults' else 60
        # primary_endpoint: scale in MADRS|CAPS-5|HAM-D|QIDS|PCL-5 (default MADRS); week from 'primary ... week N' (default 6)
        # sites: Site A/B/C names found, else all SITES
        # eligibility: bullet lines under 'Inclusion criteria' and 'Exclusion criteria'
        # design_flags: two_monitors, physician_15min, followup_12m (12-month|52 weeks), factorial, abuse_potential,
        #   raters_attend_sessions = rater ... present|attend|sit in ... session  AND NOT 'do/does/will not attend'
        # evidence: {field: quote sentence} for each field found
        # Gemini (if ctx.llm.available()): ask for comparator, rater_model, prior_use_policy with verbatim quotes;
        #   accept a value ONLY if it is in the allowed list AND the quote appears in the text; log the override as a decision.
        # Finally: rec.event(self.name, "parsed '<title>': <drug>, <comparator>, raters <rater_model>, prior use <policy>, n=<n>, primary <scale> week <w>", "decision", M)
```

**Tests to add** (`tests/platform/test_predose.py`):
```python
def test_parser_reads_both_examples():
    # psilocybin -> ("psilocybin","inert_placebo","onsite","ignore"), endpoint {"scale":"MADRS","week":6}
    # mdma       -> ("mdma","active_placebo","central_remote","stratify"), endpoint {"scale":"CAPS-5","week":18}
def test_garbage_protocol_does_not_crash():
    # ProtocolParser().run("!!! ???", ctx) returns defaults without raising
```

**Verify:** `python -m pytest -q tests/platform/test_predose.py -k parser`
**Acceptance:** both examples parse to exactly the tuples above; nonsense input returns defaults; every field found has an evidence quote.
**Drift check:** the parser does not compute risk (that's Phase 2), and does not import dosing or postdose.
**STOP. Wait for `CONFIRM PHASE 1`.**

---

## Phase 2: Protocol co-designer (risk, FDA checklist, fixes, versions, re-check)

**Goal:** before the trial, predict how badly the design will unblind, check it against the FDA guidance, propose fixes, and re-check automatically after every approved fix or edit.
**Bottleneck link:** "Regulators demand blinding evidence" and "Designs are locked before their risk is predicted".

**Files:** `predose/agents.py` (ProtocolCoDesigner, CHECKLIST, FIXES, new_version), tests.

### 2.1 Risk (uses the existing UNBLIND model; do not modify `unblind/model.py`)
```python
class ProtocolCoDesigner:
    name = "protocol co-designer"
    def __init__(self):
        rows, self.cal_label = ubmodel.load_calibration()          # SYNTHETIC until real trials are approved
        self.dm = ubmodel.design_model(rows)
        from ...synthetic import fill_imputed
        rows = fill_imputed([dict(r) for r in rows], self.dm)
        self.fit = ubmodel.fit_metareg(rows) or ubmodel.fit_metareg(rows, use_imputed=True)

    def _design(self, p):
        pe = {"stratify": 0.4, "ignore": 0.5, "exclude": 0.0}.get(p.get("prior_use_policy", "ignore"), 0.5)
        return {"comparator_type": p.get("comparator", "inert_placebo"), "prior_exposure": pe,
                "central": int(p.get("rater_model") == "central_remote")}

    def risk(self, p):
        d = self._design(p)
        u, usd = self.dm.predict(d["comparator_type"], d["prior_exposure"])
        b = self.fit.coef.get("u", 0.0) if self.fit else 0.0
        c = self.fit.coef.get("central", 0.0) if self.fit else 0.0
        bias = b * u - c * (1 - d["central"])
        band = "high" if u >= 0.6 else "medium" if u >= 0.35 else "low"
        return {"u": round(u, 3), "u_sd": round(usd, 3), "expected_bias_g": round(bias, 3), "band": band,
                "calibration": self.cal_label, "design_model": self.dm.source}
```
> Note for the pitch: `u = 2 x guess accuracy - 1`, so 0 is a coin flip and 1 means everyone knew.

### 2.2 FDA July 2026 checklist (complete)
```python
CHECKLIST = [
    ("blinding_questionnaire", "Blinding questionnaire (participants and raters guess allocation)", lambda p: p.get("has_blinding_questionnaire")),
    ("expectancy_measure", "Expectancy measured before randomisation and at end of treatment", lambda p: p.get("has_expectancy_measure")),
    ("central_raters", "Central blinded raters who do not attend dosing sessions",
     lambda p: p.get("rater_model") == "central_remote" and not p.get("design_flags", {}).get("raters_attend_sessions")),
    ("alternative_control", "Alternative or active control considered (not only inert placebo)", lambda p: p.get("comparator") != "inert_placebo"),
    ("durability", "12-week double-blind efficacy then about 12-month follow-up with retreatment criteria", lambda p: p.get("design_flags", {}).get("followup_12m")),
    ("monitors", "Two session monitors and a physician able to attend within 15 minutes",
     lambda p: p.get("design_flags", {}).get("two_monitors") and p.get("design_flags", {}).get("physician_15min")),
    ("factorial", "Factorial design considered to separate therapy from drug effect", lambda p: p.get("design_flags", {}).get("factorial")),
    ("abuse_potential", "Abuse-potential assessment planned", lambda p: p.get("design_flags", {}).get("abuse_potential")),
]
CHECK_PATTERNS = {"blinding_questionnaire": r"guess|blinding", "expectancy_measure": r"expectan", "central_raters": r"rater|assessor",
                  "alternative_control": r"placebo|comparator|control", "durability": r"follow[- ]up|month",
                  "monitors": r"monitor|facilitator|physician", "factorial": r"factorial", "abuse_potential": r"abuse"}
# checklist(p) -> [{id, item, present, evidence: first matching sentence (<=300 chars), note: "" or "Missing or not stated in the protocol"}]
```

### 2.3 Fixes (complete). Each one becomes an approval; approval -> new version -> automatic re-check.
```python
FIXES = {  # fix id -> (title, structured change, sentence appended to the protocol text)
    "central_raters": ("Move outcome raters to central, remote, blinded assessment",
        {"rater_model": "central_remote", "design_flags.raters_attend_sessions": False},
        "Outcome ratings will be performed by central blinded raters by videoconference; raters will not attend dosing sessions."),
    "blinding_questionnaire": ("Add the UNBLIND-BLIND-1 guess questionnaire for participants and raters", {"has_blinding_questionnaire": True},
        "Participants and raters will guess allocation (drug, control, don't know) with confidence after dosing and at weeks 1, 3 and 6."),
    "expectancy_measure": ("Measure expectancy before randomisation and at end of treatment", {"has_expectancy_measure": True},
        "Participant expectancy (0 to 10) will be recorded before randomisation and at the end of treatment."),
    "alternative_control": ("Use a low dose of the same drug as comparator", {"comparator": "low_dose_same_drug"},
        "The comparator arm will receive a low dose of the study drug (1 mg)."),
    "stratify_prior_use": ("Stratify randomisation by prior psychedelic use", {"prior_use_policy": "stratify"},
        "Randomisation will be stratified by site and prior psychedelic use (naive or experienced)."),
}
```

**review(rec, ctx, reason)** must:
1. compute `risk` and `checklist`
2. get `model_fixes` from `ubmodel.counterfactuals(self.fit, self.dm, self._design(p))`
3. set `proposed_fixes`: the missing ones among central_raters, blinding_questionnaire, expectancy_measure and alternative_control, plus `stratify_prior_use` if the policy isn't stratify
4. draft `blinding_section_md` (Section 2.4)
5. **preserve `baseline_risk` and `baseline_checklist_ok`**
6. write `rec["design_review"]`
7. log one decision event: "u=..., expected bias ..., FDA checklist k/8, n fixes proposed"
8. request ONE approval per proposed fix that isn't already pending: `{"type": "apply_fix", "fix": fid}`, with `evidence={"sentence_to_add": ...}`

**apply_fix(rec, ctx, fid, approver)** must:
1. apply the structured change (supporting the dotted key `design_flags.x`)
2. append the sentence to `protocol.text`
3. `new_version(rec, f"fix approved by {approver}: {title}", [sentence])`
4. `review(...)` again: this is the automatic re-check
5. post `protocol_amended` to master

**new_version(rec, why, changes)** appends `{version, day, digest(text), why, changes, text}`.

### 2.4 Drafted blinding section (template)
```python
def draft_section(self, p):
    rater = ("central blinded raters by videoconference who do not attend dosing sessions" if p.get("rater_model") == "central_remote"
             else "raters (currently on site; we recommend central blinded raters)")
    return "\n".join([
        "## Blinding and expectancy",
        "Allocation is concealed by stratified permuted-block randomisation (site x prior psychedelic use) held in a sealed vault.",
        f"Primary outcome ({p['primary_endpoint']['scale']}, week {p['primary_endpoint']['week']}) is scored by {rater}.",
        "Blinding integrity: participants and raters complete the UNBLIND-BLIND-1 guess item (drug, control, don't know) with confidence "
        "(0 to 100) after dosing and at weeks 1, 3 and 6. Blinding indices (Bang) are monitored per site and per rater during the trial, "
        "and a drift alert triggers a documented human decision.",
        "Expectancy: participants rate expected improvement (0 to 10) before randomisation, after dosing and at end of treatment.",
        "Analysis: the primary effect is reported alongside an expectancy-adjusted range with stated assumptions.",
    ])
```

**Tests:**
- Psilocybin example: `blinding_questionnaire`, `expectancy_measure` and `central_raters` are all missing.
- Approving the `central_raters` fix creates protocol version 2, and the checklist now shows central_raters present.
- Approving `alternative_control` lowers `risk.u`.

**Expected numbers** (synthetic calibration; small differences are fine): psilocybin example starts at about u = 0.79 (high), FDA 0/8. After all fixes, about u = 0.55 (medium), FDA 4/8.

**Verify:** `python -m pytest -q tests/platform/test_predose.py -k "checklist or fix"`
**STOP. Wait for `CONFIRM PHASE 2`.**

---

## Phase 3: Recruitment ads, pre-screening, clinician approval, enrolment

**Goal:** screen hundreds of applicants automatically, flag every disclosed risk for a clinician, and enrol nobody until a named clinician approves. Then randomise inside the vault, stratified.
**Bottleneck link:** "Screening is manual". Pitch it as faster and fairer, never as "less bias".

**Files:** `predose/agents.py` (RecruitmentAgent, flesch, CRITERIA, PreScreeningAgent, funnel, fairness, Enroller), tests.

### 3.1 Recruitment ads
- 3 variants:
  - plain English
  - no promise of benefit (no "cure", "will help you", "guaranteed")
  - mention a comparison or placebo chance and the time commitment
  - no sensational terms ("magic mushroom", "trip")
- Score each with Flesch reading ease:
```python
def flesch(text):
    words = re.findall(r"[A-Za-z']+", text); sents = max(1, len(re.findall(r"[.!?]+", text)))
    syl = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower())) - (1 if w.lower().endswith("e") and len(w) > 3 else 0)) for w in words)
    return 0.0 if not words else round(206.835 - 1.015 * (len(words) / sents) - 84.6 * (syl / len(words)), 1)
```
- Store `checks{no_promise_of_benefit, mentions_comparison, no_sensational_terms}`.
- Channels: GP and clinic referral, opt-in national research registries, patient charities, hospital noticeboards.
- `parked`: "Behavioural ad targeting by health or drug-use interests is parked: special category data under UK GDPR; ad platforms restrict health targeting."
- Log it as a decision: "ads need ethics approval".

### 3.2 Screening criteria (complete; show as a table in the UI)
```python
CRITERIA = [  # id, label, rule, why
    ("age", "Age", "18 to 65", "Typical adult trial range"),
    ("uk_mobile", "UK mobile", "+44 7 number", "Check-ins run through the UK chatbot"),
    ("diagnosis", "Diagnosis", "MDD or TRD; TRD needs at least 2 failed antidepressants", "Matches the protocol population"),
    ("psychosis_bipolar", "Psychosis, personal bipolar", "Exclude", "Safety; standard psychedelic exclusion"),
    ("cardio", "Uncontrolled cardiovascular condition", "Exclude", "Blood pressure rises during sessions"),
    ("pregnancy", "Pregnancy or breastfeeding", "Exclude", "Safety"),
    ("lithium", "Lithium", "Exclude", "Interaction risk"),
    ("ssri_snri", "SSRI or SNRI", "Needs clinician (washout decision)", "Clinical judgement"),
    ("recent_psychedelic", "Psychedelic use in last 12 months", "Exclude", "Recent exposure confounds"),
    ("earlier_psychedelic", "Earlier psychedelic use", "Allowed, recorded for stratification", "Balance, do not exclude"),
    ("visits", "Can attend visits", "Required", "8 in-person visits"),
    ("free_text", "Free-text disclosure", "Needs clinician, with the quoted sentence", "Never auto-include a disclosed risk"),
    ("consent", "Consent to chatbot check-ins", "Required", "The standard measurement depends on it"),
]
DISCLOSURE = re.compile(r"bipolar|psychos|psychotic|schizo|cardiolog|heart|blood pressure|pregnan|suicid|self[- ]harm|seizure|epilep", re.I)
```

**`screen_one(applicant, protocol, ctx)`** returns `{decision, reasons[], criteria_hit[], evidence[]}`:
- Any exclusion gives `excluded`. Otherwise any flag gives `needs_clinician`. Otherwise `eligible`.
- The TRD rule applies only when `protocol.indication == "treatment-resistant depression"`.
- Free text: if the regex matches, flag it and keep the full sentence as evidence. If not, and Gemini is available, ask whether it discloses a relevant condition. Accept only if the returned quote is a substring of the free text.
- **Never read keys starting with `_`.**

**`PreScreeningAgent.run(rec, ctx, applicants)`** screens everyone, appends to `rec["applicants"]`, and sets `funnel` and `fairness`:
- fairness = eligible rate by age band (18-30, 31-45, 46-65, 65+) and by country
- flag when the spread is over 20 points, naming the main criterion driving it

### 3.3 The single clinician approval (Module.setup)
```python
ctx.approvals.request("pre-screening agent", "predose",
    f"Clinician: confirm shortlist of {f['auto_eligible']} eligible applicants and review {f['needs_clinician']} flagged",
    "Final eligibility is a clinician's decision. Flagged applicants stay out unless you say otherwise in the comment "
    "('include flagged' adds those flagged only for medication washout).",
    {"type": "shortlist"}, evidence={"flagged": flagged[:50]})
```

### 3.4 Enroller (after approval only)
- Pool = eligible applicants. Add the flagged ones only if the comment contains "include flagged", and then never those with a free-text disclosure.
- Take up to `n_target`.
- `stratum = f"{site}|{'naive' if never else 'experienced'}"`
- `dosing_day = 1 + (i % 20)`
- `counts = ctx.vault.randomise(enrolled, "stratum")`. Store the counts only, never arms.
- Post `enrolment_complete` to master.
- Log: "randomised 1:1 within N strata in the sealed vault (agents never see allocation)".

**Tests:**
- Nothing is enrolled before the approval, and `Master.step` returns `blocked`.
- Every applicant with `_hidden_exclusion` ends up not eligible.
- After approval: more than 10 enrolled, and the strata counts sum to the number enrolled.
- The record JSON never contains an arm.
- Portal check: `{"age": 30, "phone": "+447700900123", "free_text": "I was diagnosed with bipolar disorder"}` gives `needs_clinician`.

**Expected with 500 applicants** (synthetic; numbers vary): about 49 eligible, 56 needing a clinician, and all hidden exclusions caught.
**STOP. Wait for `CONFIRM PHASE 3`.**

---

## Phase 4: Measurement planner, module wiring and the end-to-end run (21:30 checkpoint)

**Goal:** produce the standard measurement plan and the schedule Callum and Izzy consume, and wire everything into the master.

### 4.1 UNBLIND-BLIND-1 instruments (complete)
```python
INSTRUMENTS = [
    {"id": "UB1-EXP0", "who": "participant", "questions": ["How much do you expect to improve? (0 to 10)"], "timepoints_days": ["before randomisation"], "purpose": "Baseline expectancy (FDA July 2026)"},
    {"id": "UB1-PG", "who": "participant", "questions": ["Which group do you think you are in? (drug, control, don't know)", "How sure are you? (0 to 100)", "How much do you expect to improve? (0 to 10)"], "timepoints_days": ["dosing +1", "week 1", "week 3", "week 6"], "purpose": "Participant blinding and expectancy"},
    {"id": "UB1-RG", "who": "rater", "questions": ["Which group do you think this participant is in?", "How sure are you? (0 to 100)"], "timepoints_days": ["week 1", "week 3", "week 6"], "purpose": "Rater blinding (central raters)"},
    {"id": "UB1-MD", "who": "monitor", "questions": ["Free-text debrief: effects, adverse events, anything that could reveal the arm"], "timepoints_days": ["dosing day"], "purpose": "Safety and unblinding cues"},
    {"id": "MADRS", "who": "rater", "questions": ["MADRS total (0 to 60)"], "timepoints_days": ["baseline", "week 1", "week 3", "week 6"], "purpose": "Primary outcome"},
    {"id": "UB1-FU", "who": "participant", "questions": ["Follow-up check-in and end-of-treatment guess and expectancy"], "timepoints_days": ["week 8", "week 12"], "purpose": "Durability and end-of-treatment blinding"},
]
```

### 4.2 Schedule builder (complete: exact shapes Callum and Izzy depend on)
```python
def build_schedule(rec):
    wk = int(rec["protocol"].get("primary_endpoint", {}).get("week", 6))
    raters = {s: ["R-" + s[5] + "1", "R-" + s[5] + "2"] for s in SITES}       # e.g. R-A1, R-B2
    sched = []
    for i, p in enumerate(rec["enrolled"]):
        d, pid, site = p["dosing_day"], p["id"], p["site"]
        rid = raters.get(site, ["R-X1"])[i % 2]
        def add(kind, day, owner, instrument, **extra):
            sched.append({"id": f"{pid}-{kind}-{day}", "participant": pid, "site": site, "day": day, "kind": kind,
                          "owner": owner, "instrument": instrument, "status": "scheduled", **extra})
        add("dosing_session", d, "dosing", "session")
        add("monitor_debrief", d, "dosing", "UB1-MD")
        add("participant_checkin", d + 1, "dosing", "UB1-PG")
        for w in sorted({1, 3, wk}):
            add("rater_assessment", d + 7 * w, "dosing", "MADRS+UB1-RG", rater_id=rid, visit_week=w)
            add("participant_checkin", d + 7 * w, "dosing", "UB1-PG", visit_week=w)
        for w in (8, 12):
            add("followup", d + 7 * w, "postdose", "UB1-FU", visit_week=w)
    return sched
```

### 4.3 `predose/module.py`: lifecycle (skeleton; fill in exactly)
```python
class Module(BaseModule):
    name = "predose"; title = "Pre-dosing: design, recruitment and screening"
    bottleneck_ids = ["fda_unblinding", "blinding_failure"]
    def setup(self, rec, ctx):
        # 1 parse rec["protocol"]["text"] (or data/protocols/example_psilocybin_trd.md if empty)
        # 2 store baseline_risk and baseline_checklist_ok in rec["design_review"]; new_version("initial draft")
        # 3 co-designer review (creates fix approvals)   4 recruitment ads   5 rec["phase"] = "recruitment"
        # 6 screen ctx.world.applicants(rec["config"]["n_applicants"])   7 ONE clinician shortlist approval (3.3)
    def on_day(self, rec, day, ctx): return None   # event-driven after setup
    def on_message(self, rec, msg, ctx):
        # approval_decided: rejected -> log; apply_fix|amendment -> codesigner.apply_fix; shortlist -> Enroller.run + MeasurementPlanner.run
        # rater_drift | participant_unblinding -> approval request {"type":"amendment","fix":"central_raters"} titled
        #     "Protocol amendment: central remote raters only (after drift at <site>)"
        # literature_update -> rebuild co-designer (reload calibration) and review(reason="re-check after a literature update")
    def handle(self, rec, action, payload, ctx):
        # "recheck" {text, editor}: re-parse, unified diff vs old text (changed lines only, max 40), new_version, review; return {ok, diff, risk, checklist}
        # "apply" {applicant}: fill defaults, screen_one, append with source="portal", log decision; return {ok, applicant}
    def kpis(self, rec):  # see 4.4
    def view(self, rec):  # base view + a "Screening criteria" table from CRITERIA
```

### 4.4 KPIs (quantified impact; the brief demands it)
- Applicants decided automatically (%), with a baseline of 0
- Clinician reviews needed, "of N", with a baseline of N (the manual process reviews everyone)
- Staff hours saved = automatically decided x **20 min (ASSUMPTION, labelled)** / 60
- Hidden free-text exclusions caught, labelled **"Evaluation against synthetic ground truth only"**
- FDA checklist items met, before vs after
- Predicted unblinding u, before vs after, noting that the calibration is SYNTHETIC

**Verify:**
```bash
python -m pytest -q tests/platform
python -c "from unblind.platform.master.orchestrator import Master; m=Master('E2E', auto_approve=True); m.setup(); print(m.state()); print(m.run_to(95)); print(m.kpis()['predose'])"
```
**Acceptance:**
- [ ] module_status shows predose `real`, dosing and postdose `stub` (or real if merged)
- [ ] the run reaches day 90 and `closed`
- [ ] the schedule only contains the 5 kinds, with the correct owners
- [ ] predose KPIs print

**Checkpoint:** merge into `main` and tell Callum and Izzy that the schedule is live.
**STOP. Wait for `CONFIRM PHASE 4`.**

---

## Phase 5: FastAPI backend

**Goal:** a thin JSON API over the Master. No business logic in the API.
**Files:** `backend/__init__.py`, `backend/main.py`, `tests/platform/test_api.py`. Add `fastapi`, `uvicorn` and `httpx` to `requirements.txt`.

### 5.1 Endpoints (complete contract)
| Method | Path | Body | Returns |
|---|---|---|---|
| GET | /api/health | | `{ok, gemini, trials[]}` |
| GET | /api/bottlenecks | | `data/bottlenecks.json` |
| GET | /api/protocols | | `[{name, title}]` from data/protocols |
| GET | /api/protocols/{name} | | `{name, text}` (path traversal blocked) |
| POST | /api/trials | `{protocol_text?, example?, seed=42, n_applicants=500, auto_approve=false}` | TrialState |
| GET | /api/trials | | TrialState[] |
| GET | /api/trials/{id}/state | | TrialState |
| POST | /api/trials/{id}/step | `{days}` (1 to 30) | `{advanced, blocked?, day, state}` |
| POST | /api/trials/{id}/auto_approve?on=true | | TrialState |
| GET | /api/trials/{id}/record?sections=a,b | | the chosen record sections (allow-list; `_` keys stripped) |
| GET | /api/trials/{id}/events?since=&module=&level= | | events with `idx` |
| GET | /api/trials/{id}/approvals?status=pending\|all | | approvals |
| POST | /api/trials/{id}/approvals/{aid} | `{reviewer, decision: approved\|rejected, comment}` | `{approval, state}`; 400 if no reviewer |
| GET | /api/trials/{id}/kpis | | `{module: Kpi[]}` |
| GET | /api/trials/{id}/messages | | `{edges[{from,to,count}], recent[]}` |
| GET | /api/trials/{id}/modules/{m}/view | | ViewModel |
| POST | /api/trials/{id}/modules/{m}/actions/{action} | `{payload}` | `{result, state}` |
| POST | /api/evidence/run | `{input}` | existing UNBLIND pipeline report (needs internet) |

### 5.2 `backend/main.py` (complete)
```python
"""UNBLIND platform API (FastAPI). Thin glue over the Master agent. No business logic here.

Run:  uvicorn backend.main:app --reload --port 8000     (from the repo root)
The React app (frontend/) calls these endpoints. Everything returned is JSON.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from unblind.platform.core import DATA
from unblind.platform.master.orchestrator import Master

app = FastAPI(title="UNBLIND platform API", version="0.1")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

TRIALS: Dict[str, Master] = {}          # in-memory; a server restart means starting a new trial
PROTOCOLS = DATA / "protocols"
SECTIONS_ALLOWED = {"protocol", "protocol_versions", "design_review", "recruitment", "applicants", "enrolled",
                    "measurement_plan", "schedule", "sessions", "checkins", "debriefs", "outcomes", "blinding_metrics",
                    "alerts", "actions", "missing_data", "literature", "followups", "research_questions", "exports",
                    "report", "approvals", "kpis"}


def _m(trial_id: str) -> Master:
    m = TRIALS.get(trial_id)
    if m is None:
        raise HTTPException(404, f"no trial {trial_id} in this server session; create one")
    return m


def _strip_private(obj: Any) -> Any:
    """Never send synthetic ground-truth keys (starting with '_') to the browser."""
    if isinstance(obj, dict):
        return {k: _strip_private(v) for k, v in obj.items() if not str(k).startswith("_")}
    if isinstance(obj, list):
        return [_strip_private(x) for x in obj]
    return obj


# ---------------------------------------------------------------- models
class CreateTrial(BaseModel):
    protocol_text: Optional[str] = None
    example: Optional[str] = None          # file name in data/protocols
    seed: int = 42
    n_applicants: int = 500
    auto_approve: bool = False


class Step(BaseModel):
    days: int = 1


class Decision(BaseModel):
    reviewer: str
    decision: str                          # approved | rejected
    comment: str = ""


class Action(BaseModel):
    payload: Dict[str, Any] = {}


# ---------------------------------------------------------------- meta
@app.get("/api/health")
def health():
    from unblind import llm
    return {"ok": True, "gemini": llm.available(), "trials": list(TRIALS)}


@app.get("/api/bottlenecks")
def get_bottlenecks():
    p = DATA / "bottlenecks.json"
    return json.loads(p.read_text()) if p.exists() else {"bottlenecks": []}


@app.get("/api/protocols")
def list_protocols():
    if not PROTOCOLS.exists():
        return []
    return [{"name": p.name, "title": p.read_text().splitlines()[0].lstrip("# ").strip()} for p in sorted(PROTOCOLS.glob("*.md"))]


@app.get("/api/protocols/{name}")
def get_protocol(name: str):
    p = (PROTOCOLS / name).resolve()
    if PROTOCOLS.resolve() not in p.parents or not p.exists():
        raise HTTPException(404, "not found")
    return {"name": name, "text": p.read_text()}


# ---------------------------------------------------------------- trials
@app.post("/api/trials")
def create_trial(body: CreateTrial):
    text = body.protocol_text
    if not text and body.example:
        text = get_protocol(body.example)["text"]
    tid = f"T-{time.strftime('%H%M%S')}-{uuid.uuid4().hex[:4]}"
    m = Master(tid, protocol={"text": text} if text else None, seed=body.seed,
               n_applicants=body.n_applicants, auto_approve=body.auto_approve)
    m.setup()
    TRIALS[tid] = m
    return m.state()


@app.get("/api/trials")
def list_trials():
    return [m.state() for m in TRIALS.values()]


@app.get("/api/trials/{tid}/state")
def state(tid: str):
    return _m(tid).state()


@app.post("/api/trials/{tid}/step")
def step(tid: str, body: Step):
    m = _m(tid)
    out = m.step(max(1, min(body.days, 30)))
    return {**out, "state": m.state()}


@app.post("/api/trials/{tid}/auto_approve")
def set_auto(tid: str, on: bool = True):
    m = _m(tid)
    m.rec["config"]["auto_approve"] = on
    with m.lock:
        m._settle()
    return m.state()


@app.get("/api/trials/{tid}/record")
def record(tid: str, sections: str = ""):
    r = _m(tid).rec
    want = [s for s in sections.split(",") if s] or list(SECTIONS_ALLOWED)
    return _strip_private({s: r.get(s) for s in want if s in SECTIONS_ALLOWED})


@app.get("/api/trials/{tid}/events")
def events(tid: str, since: int = 0, module: str = "", level: str = "", limit: int = 400):
    ev = _m(tid).rec["events"]
    rows = [dict(e, idx=i) for i, e in enumerate(ev) if i >= since
            and (not module or e["module"] == module) and (not level or e["level"] == level)]
    return _strip_private(rows[-limit:])


@app.get("/api/trials/{tid}/approvals")
def approvals(tid: str, status: str = "pending"):
    m = _m(tid)
    rows = m.rec["approvals"] if status == "all" else [a for a in m.rec["approvals"] if a["status"] == status]
    return _strip_private(rows)


@app.post("/api/trials/{tid}/approvals/{aid}")
def decide(tid: str, aid: str, body: Decision):
    m = _m(tid)
    try:
        a = m.decide(aid, body.reviewer, body.decision, body.comment)
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
    return {"approval": _strip_private(a), "state": m.state()}


@app.get("/api/trials/{tid}/kpis")
def kpis(tid: str):
    return _m(tid).kpis()


@app.get("/api/trials/{tid}/messages")
def messages(tid: str):
    m = _m(tid)
    return {"edges": m.message_edges(), "recent": _strip_private(m.rec["messages"][-50:])}


# ---------------------------------------------------------------- modules
@app.get("/api/trials/{tid}/modules/{module}/view")
def module_view(tid: str, module: str):
    return _strip_private(_m(tid).module_view(module))


@app.post("/api/trials/{tid}/modules/{module}/actions/{action}")
def module_action(tid: str, module: str, action: str, body: Action):
    m = _m(tid)
    res = m.module_action(module, action, body.payload)
    return {"result": _strip_private(res), "state": m.state()}


# ---------------------------------------------------------------- evidence engine (existing UNBLIND pipeline)
class EvidenceIn(BaseModel):
    input: str


@app.post("/api/evidence/run")
def evidence(body: EvidenceIn):
    from unblind import pipeline
    rep = pipeline.run(body.input)
    return json.loads(rep.to_json())
```
> Master needs two extra public methods used by the API, already included in orchestrator.py: `decide()`, `module_action()`, `module_view()`, `message_edges()`, `state()`, `kpis()`.

**Test** (`tests/platform/test_api.py`, using `fastapi.testclient.TestClient`):
- create trial, then `/state` shows `blocked` (the shortlist isn't approved)
- approve the shortlist with a reviewer, then `/step` advances
- `/approvals/...` with an empty reviewer gives 400
- `/record?sections=applicants` contains no `_hidden_exclusion`
- `/protocols/../../etc/passwd` gives 404

**Verify:** `python -m pytest -q tests/platform/test_api.py` then `uvicorn backend.main:app --reload --port 8000` and open http://127.0.0.1:8000/docs
**STOP. Wait for `CONFIRM PHASE 5`.**

---

## Phase 6: React app shell and mission control

**Goal:** the product shell. Judges drive the whole trial from here.
**Setup:**
```bash
cd frontend   # create with: npm create vite@5 frontend -- --template react-ts   (then replace files as below)
npm i react-router-dom@6.28.0 recharts@2.13.3
```
`vite.config.ts` proxies `/api` to `http://127.0.0.1:8000` (server port 5173).

### 6.1 File tree
```
frontend/src/
  main.tsx            # BrowserRouter > TrialProvider > App
  App.tsx             # header nav + SyntheticBanner + routes
  styles.css          # plain CSS (tokens: --ink #1d2433, --accent #4b3fb5, --soft #eeecfb, --warn #fff4dc)
  types.ts            # TrialState, TrialEvent, Approval, Kpi, Bottleneck, ViewModel, MessageEdge (mirror Section 3 shapes)
  api.ts              # typed fetch client for every endpoint in 5.1 + reviewer name in localStorage (try/catch)
  trial.tsx           # TrialProvider: {trialId (localStorage), state, tick, setTrialId, refresh}
  components/common.tsx  # SyntheticBanner, BottleneckStrip, PhaseBar, KpiGrid, ApprovalInbox, Timeline, MessageMap, DataTable
  pages/MissionControl.tsx
  pages/Predose.tsx      # Phase 7
  pages/Portal.tsx       # Phase 7
  pages/ModulePage.tsx   # Phase 8 (generic renderer for dosing and postdose)
```

### 6.2 Key code (copy these; they define the data flow)
```ts
// api.ts (core helper)
async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
  return r.json() as Promise<T>;
}
const post = <T>(path: string, body: unknown) => j<T>(path, { method: "POST", body: JSON.stringify(body) });
export const api = {
  createTrial: (b: {protocol_text?: string; example?: string; seed?: number; n_applicants?: number; auto_approve?: boolean}) => post<TrialState>("/api/trials", b),
  state: (t: string) => j<TrialState>(`/api/trials/${t}/state`),
  step: (t: string, days: number) => post<{advanced: boolean; blocked?: string; day: number; state: TrialState}>(`/api/trials/${t}/step`, { days }),
  decide: (t: string, id: string, reviewer: string, decision: "approved" | "rejected", comment = "") =>
    post(`/api/trials/${t}/approvals/${id}`, { reviewer, decision, comment }),
  // ...one function per endpoint in 5.1
};
```
```tsx
// trial.tsx: every component refetches when `tick` changes (after any step or decision)
const refresh = useCallback(async () => {
  if (!trialId) { setState(null); return; }
  try { setState(await api.state(trialId)); setTick((x) => x + 1); }
  catch { setTrialId(null); setState(null); }   // server restarted: trial is gone
}, [trialId]);
```
```tsx
// MissionControl: Play loop (2 days every 350 ms; stops when blocked or closed)
const play = async () => {
  playing.current = !playing.current; setIsPlaying(playing.current);
  while (playing.current) {
    const r = await step(2);
    if (!r || !r.advanced || r.state.phase === "closed") { playing.current = false; setIsPlaying(false); }
    await new Promise((res) => setTimeout(res, 350));
  }
};
```

### 6.3 Mission control content (top to bottom)
1. **No trial yet:** an example protocol dropdown (from /api/protocols) fills an editable textarea, plus an auto-approve checkbox (labelled "demo fast-forward") and a "Create trial" button ("Agents working..." while busy).
2. **With a trial:**
   - **PhaseBar** (design, recruitment, dosing, follow-up, close-out, closed, plus "Day X of 90")
   - **Controls:** Next day, +1 week, Play/Pause, auto-approve toggle, then the trial ID, Gemini on/off and module real/stub status, and a New trial button
   - **`blocked` banner** (for example "Waiting for a human: Clinician: confirm shortlist...")
   - **KPI grids** per module
   - a two-column grid: **ApprovalInbox** (reviewer name required; Approve/Reject with an optional comment; evidence in `<details>`) and **MessageMap** (an SVG with nodes for master, predose, dosing, postdose and approvals; edge width = log of the count)
   - **Timeline** (newest first; a filter for All, Decisions, Warnings or Human; decision rows tagged DECISION, warnings amber, human rows green)

**Verify:** `npm run build` passes (tsc and vite); `npm run dev` with uvicorn running gives a clean create, approve, play loop with no console errors.
**STOP. Wait for `CONFIRM PHASE 6`.**

---

## Phase 7: Pre-dosing page and volunteer portal

### 7.1 Pre-dosing page (reads `/record?sections=protocol,protocol_versions,design_review,recruitment,applicants,enrolled,measurement_plan`)
Order:
1. BottleneckStrip(module="predose")
2. KPI grid
3. Risk card: "u = 0.79 [high]" (u means: 0 is a coin flip, 1 means everyone knows), then expected bias, then the calibration label in small text
4. ApprovalInbox(module="predose")
5. FDA checklist table: Item, Present/Missing, evidence quote
6. Protocol editor: a textarea plus "Save version and re-check", which calls `actions/recheck`; show the returned diff (+/- lines)
7. Drafted blinding section, plus a version history table (v, day, why, changes)
8. Screening funnel: Applied, Eligible (auto), Excluded (auto), Needs clinician, Enrolled
9. Flagged table (Applicant, reasons, quoted disclosure)
10. Fairness table
11. Recruitment ads (text, reading ease, checks, plus the parked-targeting note)
12. Measurement plan table
13. Timeline(module="predose")

### 7.2 Volunteer portal (the judge-input moment)
- A form with: name, age, mobile, diagnosis, failed antidepressants, current medication, psychedelic use (plus months since, if any), checkboxes for psychosis, bipolar, heart condition, pregnancy, can attend visits, and consents to check-ins, and free text.
- Show "Synthetic demo. Do not enter real personal or health information."
- On submit, call `actions/apply`, and on the right show the decision pill (eligible, excluded or needs clinician), the reasons, the quoted disclosure, and "Final eligibility is always confirmed by a clinician."

**Demo test:** free text "I was diagnosed with bipolar disorder last year" gives needs clinician, with the quote.
**STOP. Wait for `CONFIRM PHASE 7`.**

---

## Phase 8: Generic module pages (dosing and post-dosing) and integration

**Goal:** Callum and Izzy write Python only. Their modules appear in React through `view(rec)` (see the VIEW MODEL in MODULE_CONTRACT.md).
**ModulePage(module):**
- a STUB banner if `status === "stub"`
- BottleneckStrip and KPI grid
- cards (tone colours)
- charts: recharts LineChart per chart, with series keys, `connectNulls`, and the caption "Synthetic data."
- ApprovalInbox(module)
- forms: generic inputs, and submit calls `actions/{form.action}` with the values as payload
- tables
- Timeline(module)

**Integration steps:**
1. Pull `callum/dosing` and `izzy/postdose` into `danny/platform`. Never edit their folders; if their code breaks, send them the traceback from the timeline.
2. Run the full path twice with auto-approve OFF:
   - create
   - approve 2 or 3 fixes
   - approve the shortlist
   - Play
   - approve Callum's drift action when it appears
   - Play to close
   - Izzy's report waits for sign-off
3. Then once with auto-approve ON.

**Acceptance:** module_status shows all `real`; no Python tracebacks in the timeline; `npm run build` is clean; `pytest -q` passes everywhere.
**Freeze:** tag `v1`, push to `main`.
**STOP. Wait for `CONFIRM PHASE 8`.**

---

## Phase 9 (optional, only if time): Gemini polish
- Gemini-assisted protocol parsing on the three fields (validated, as in Phase 1).
- Gemini routing for unknown message kinds (already in the master; test with a made-up kind).
- An "Ask the co-designer" box: the question and protocol go to Gemini; the answer must cite protocol sentences, and is shown with a "suggestion, not a decision" label.
- Key in `.env` as `GEMINI_API_KEY` (never committed); `GEMINI_MODEL` is optional.

---

## 10. Demo script (Danny's parts)

| Time | Show | Say |
|---|---|---|
| 0:30 to 1:30 | Mission control: create from the weak psilocybin draft | "The co-designer reads the draft and predicts high unblinding (u about 0.8). It checks the FDA July 2026 items: 0 of 8. It proposes fixes." |
| | Approve the 'central raters' fix | "Every fix is a human decision. It creates a new protocol version and the agents re-check automatically." |
| | Pre-dosing funnel | "500 synthetic applicants, mostly decided automatically. Every disclosed risk goes to a clinician with the quote. One clinician approval enrols the shortlist, randomised inside a sealed vault the AI can't read." |
| Judges' 2 minutes | Volunteer portal | "Apply as a volunteer. Mention anything in the free text. Watch the agent decide." |
| 3:30 to 4:00 | Mission control timeline and message map | "Every agent decision is logged. Every trial-changing action was signed by a person. One standard, every trial comparable." |

**Judge questions:**
- "Can an AI decide who joins a trial?" No. It sorts and explains; a clinician confirms (show the approval).
- "Is targeting by drug interest legal?" We parked it for that reason (UK GDPR special category data).
- "What if the risk number is wrong?" The calibration is synthetic tonight and labelled so. The checklist and fixes stand on the FDA guidance alone.
- "Can the AI see who got the drug?" No. Allocation lives only in the vault; agents get aggregates with groups under 5 suppressed.

---

## 11. Glossary (for the agent and for Danny)
| Term | Meaning |
|---|---|
| Blinding | Keeping secret who got the real drug |
| Functional unblinding | The drug's effects give the secret away |
| u | 2 x guess accuracy - 1: 0 is a coin flip, 1 means everyone knew |
| Bang index | Per-arm blinding score from -1 to 1, where 0 is ideal |
| Central blinded rater | A remote scorer who never sees the session and doesn't know the arm |
| Stratified randomisation | Randomising separately within groups (site x naive or experienced) |
| MADRS / CAPS-5 | Depression / PTSD scales scored by a clinician |
| Primary endpoint | The one outcome the trial promised to test (scale + week) |
| UNBLIND-BLIND-1 | Our standard instrument set: guesses, confidence, expectancy at fixed timepoints |
| Synthetic | Simulated data, always labelled, never presented as real-world performance |
