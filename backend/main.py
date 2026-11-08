"""Parallax platform API (FastAPI). Thin glue over the Master agent. No business logic here.

Run:  uvicorn backend.main:app --reload --port 8000     (from the repo root)
The React app (frontend/) calls these endpoints. Everything returned is JSON.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from unblind.platform.core import DATA
from unblind.platform.master.orchestrator import Master

app = FastAPI(title="Parallax platform API", version="0.1")
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
    n_applicants: int = Field(500, ge=10, le=2000)
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
    return _strip_private(json.loads(p.read_text()) if p.exists() else {"bottlenecks": []})


@app.get("/api/protocols")
def list_protocols():
    if not PROTOCOLS.exists():
        return []
    out = []
    for p in sorted(PROTOCOLS.glob("*.md")):
        lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
        out.append({"name": p.name, "title": (lines[0].lstrip("# ").strip() if lines else "") or p.name})
    return out


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
    out = []
    for m in list(TRIALS.values()):
        with m.lock:
            out.append(m.state())
    return out


@app.get("/api/trials/{tid}/state")
def state(tid: str):
    m = _m(tid)
    with m.lock:
        return m.state()


@app.post("/api/trials/{tid}/step")
def step(tid: str, body: Step):
    m = _m(tid)
    with m.lock:
        out = m.step(max(1, min(body.days, 30)))
        return {**out, "state": m.state()}


@app.post("/api/trials/{tid}/auto_approve")
def set_auto(tid: str, on: bool = True):
    m = _m(tid)
    with m.lock:
        m.rec["config"]["auto_approve"] = on
        m._settle()
        return m.state()


@app.get("/api/trials/{tid}/record")
def record(tid: str, sections: str = ""):
    m = _m(tid)
    want = [s for s in sections.split(",") if s] or list(SECTIONS_ALLOWED)
    with m.lock:
        return _strip_private({s: m.rec.get(s) for s in want if s in SECTIONS_ALLOWED})


@app.get("/api/trials/{tid}/events")
def events(tid: str, since: int = 0, module: str = "", level: str = "", limit: int = 400):
    m = _m(tid)
    with m.lock:
        ev = m.rec["events"]
        rows = [dict(e, idx=i) for i, e in enumerate(ev) if i >= since
                and (not module or e["module"] == module) and (not level or e["level"] == level)]
        return _strip_private(rows[-limit:])


@app.get("/api/trials/{tid}/approvals")
def approvals(tid: str, status: str = "pending"):
    m = _m(tid)
    with m.lock:
        rows = m.rec["approvals"] if status == "all" else [a for a in m.rec["approvals"] if a["status"] == status]
        return _strip_private(rows)


@app.post("/api/trials/{tid}/approvals/{aid}")
def decide(tid: str, aid: str, body: Decision):
    m = _m(tid)
    with m.lock:
        try:
            a = m.decide(aid, body.reviewer, body.decision, body.comment)
        except ValueError as e:              # no reviewer, or a bad decision value
            raise HTTPException(400, str(e))
        except KeyError:                     # unknown id, or already decided
            raise HTTPException(404, f"no pending approval {aid}")
        return {"approval": _strip_private(a), "state": m.state()}


@app.get("/api/trials/{tid}/kpis")
def kpis(tid: str):
    m = _m(tid)
    with m.lock:
        return _strip_private(m.kpis())


@app.get("/api/trials/{tid}/messages")
def messages(tid: str):
    m = _m(tid)
    with m.lock:
        return {"edges": m.message_edges(), "recent": _strip_private(m.rec["messages"][-50:])}


# ---------------------------------------------------------------- modules
@app.get("/api/trials/{tid}/modules/{module}/view")
def module_view(tid: str, module: str):
    m = _m(tid)
    with m.lock:
        return _strip_private(m.module_view(module))


@app.post("/api/trials/{tid}/modules/{module}/actions/{action}")
def module_action(tid: str, module: str, action: str, body: Action):
    m = _m(tid)
    with m.lock:
        res = m.module_action(module, action, body.payload)
        return {"result": _strip_private(res), "state": m.state()}


# ---------------------------------------------------------------- evidence engine (existing Parallax pipeline)
class EvidenceIn(BaseModel):
    input: str


@app.post("/api/evidence/run")
def evidence(body: EvidenceIn):
    from unblind import pipeline
    rep = pipeline.run(body.input)
    return json.loads(rep.to_json())
