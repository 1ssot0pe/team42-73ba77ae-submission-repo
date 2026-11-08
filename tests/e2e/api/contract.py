"""Section B: API contract for every route in backend/main.py, against ONE instance.

    .venv/bin/python tests/e2e/api/contract.py --base http://127.0.0.1:8001 [--evidence]

Checks status codes and shapes, error codes, recursive privacy (no '_' keys, no participant arm),
response sizes (flag > 1 MB; sizes at day 0, 45, 90) and latency (p50 / max per endpoint, step 1/7/30).
Writes tests/e2e/api/results/contract_<label>.json and prints a summary. Exit code 1 if any check failed.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from common import MB, Client, arm_key_paths, dump, privacy_scan  # noqa: E402

RESULTS = os.path.join(os.path.dirname(__file__), "results")
REVIEWER = "E2E Tester"


class Run:
    def __init__(self, c: Client):
        self.c = c
        self.checks = []
        self.privacy = []
        self.big = []
        self.arm_paths = set()

    def check(self, name, ok, detail=""):
        self.checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:400]})
        print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  :: {str(detail)[:300]}"), flush=True)
        return ok

    def scan(self, name, r):
        if len(r.content) > MB:
            self.big.append({"name": name, "bytes": len(r.content)})
        try:
            body = r.json()
        except ValueError:
            return None
        v = privacy_scan(body)
        if v:
            self.privacy.append({"name": name, "violations": v[:20], "n": len(v)})
        self.arm_paths.update(arm_key_paths(body))
        return body

    def expect(self, name, r, status, shape=None):
        body = self.scan(name, r)
        ok = r.status_code == status
        detail = f"status {r.status_code} body {r.text[:200]}"
        if ok and shape is not None:
            try:
                ok = shape(body)
                detail = f"shape check failed: {r.text[:200]}"
            except Exception as e:  # noqa: BLE001
                ok, detail = False, f"shape raised {type(e).__name__}: {e}; body {r.text[:200]}"
        self.check(f"{name} -> {status}", ok, detail)
        return body


def decide_all(c: Client, tid: str, decision="approved", only=None):
    """Approve (or reject) every pending approval; returns the list decided."""
    done = []
    for a in c.get(f"/api/trials/{tid}/approvals").json():
        if only and not only(a):
            continue
        r = c.post(f"/api/trials/{tid}/approvals/{a['id']}", json={"reviewer": REVIEWER, "decision": decision})
        if r.status_code == 200:
            done.append(a)
    return done


def advance(c: Client, tid: str, to_day: int):
    """Step to a day, approving anything that comes up on the way."""
    while True:
        st = c.get(f"/api/trials/{tid}/state").json()
        if st["day"] >= to_day or st["phase"] == "closed":
            return st
        decide_all(c, tid)
        n = min(30, to_day - st["day"])
        r = c.post(f"/api/trials/{tid}/step", json={"days": n}, key=f"POST step days={n}")
        if r.status_code != 200 or not r.json().get("advanced"):
            return r.json() if r.status_code == 200 else {"error": r.status_code}


def sizes(c: Client, tid: str):
    out = {}
    for name, path in [("state", f"/api/trials/{tid}/state"), ("record_all", f"/api/trials/{tid}/record"),
                       ("events_default", f"/api/trials/{tid}/events"),
                       ("events_all", f"/api/trials/{tid}/events?limit=100000"),
                       ("approvals_all", f"/api/trials/{tid}/approvals?status=all"),
                       ("kpis", f"/api/trials/{tid}/kpis"), ("messages", f"/api/trials/{tid}/messages"),
                       ("view_predose", f"/api/trials/{tid}/modules/predose/view"),
                       ("view_dosing", f"/api/trials/{tid}/modules/dosing/view"),
                       ("view_postdose", f"/api/trials/{tid}/modules/postdose/view")]:
        r = c.get(path)
        out[name] = len(r.content)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument("--label", default="local8001")
    ap.add_argument("--evidence", action="store_true", help="also call /api/evidence/run (may hit the network)")
    ap.add_argument("--reps", type=int, default=10, help="repeats per GET for latency")
    a = ap.parse_args()
    c = Client(a.base)
    R = Run(c)
    T = lambda tid: f"/api/trials/{tid}"  # noqa: E731

    # ------------------------------------------------------------- meta
    R.expect("health", c.get("/api/health"), 200, lambda b: b["ok"] is True and isinstance(b["trials"], list))
    R.expect("bottlenecks", c.get("/api/bottlenecks"), 200, lambda b: isinstance(b["bottlenecks"], list) and b["bottlenecks"])
    protos = R.expect("protocols", c.get("/api/protocols"), 200,
                      lambda b: all({"name", "title"} <= set(x) for x in b) and len(b) >= 2)
    name = protos[0]["name"] if protos else "example_psilocybin_trd.md"
    R.expect("protocols/{name} valid", c.get(f"/api/protocols/{name}"), 200, lambda b: b["name"] == name and len(b["text"]) > 100)
    for bad in ["nope.md", "..%2F..%2Fbackend%2Fmain.py", "%2E%2E%2F%2E%2E%2FREADME.md", "..%2Fbottlenecks.json",
                "%2Fetc%2Fpasswd", "..%5C..%5CREADME.md", "%2E", "%2E%2E", "....%2F%2F....%2F%2FREADME.md"]:
        r = c.get(f"/api/protocols/{bad}")
        R.check(f"protocols traversal {bad} -> 404", r.status_code == 404 and "import" not in r.text and "root:" not in r.text,
                f"{r.status_code} {r.text[:120]}")

    # ------------------------------------------------------------- create: bad bodies
    R.expect("create bad json", c.post("/api/trials", data="{not json", headers={"Content-Type": "application/json"}), 422)
    R.expect("create n_applicants=5", c.post("/api/trials", json={"example": name, "n_applicants": 5}), 422)
    R.expect("create n_applicants=5000", c.post("/api/trials", json={"example": name, "n_applicants": 5000}), 422)
    R.expect("create seed='abc'", c.post("/api/trials", json={"example": name, "seed": "abc"}), 422)
    R.expect("create example unknown", c.post("/api/trials", json={"example": "nope.md"}), 404)
    R.expect("create example traversal", c.post("/api/trials", json={"example": "../../README.md"}), 404)
    r = c.post("/api/trials", json={})
    R.expect("create with no protocol at all", r, 200, lambda b: b["trial_id"].startswith("T-"))
    r = c.post("/api/trials", json={"protocol_text": "!!! ???", "n_applicants": 50})
    R.expect("create garbage protocol", r, 200, lambda b: b["trial_id"].startswith("T-"))

    # ------------------------------------------------------------- unknown trial on every trial route
    for m, p, body in [("GET", "state", None), ("POST", "step", {"days": 1}), ("POST", "auto_approve", None),
                       ("GET", "record", None), ("GET", "events", None), ("GET", "approvals", None),
                       ("POST", "approvals/abc", {"reviewer": "x", "decision": "approved"}), ("GET", "kpis", None),
                       ("GET", "messages", None), ("GET", "modules/dosing/view", None),
                       ("POST", "modules/dosing/actions/checkin", {"payload": {}})]:
        r = c.call(m, f"/api/trials/T-NOPE/{p}", key="unknown trial", json=body)
        R.check(f"unknown trial {m} {p} -> 404", r.status_code == 404, f"{r.status_code} {r.text[:120]}")

    # ------------------------------------------------------------- main trial (manual approvals)
    t0 = time.perf_counter()
    r = c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "seed": 42})
    create_ms = (time.perf_counter() - t0) * 1000
    st = R.expect("create psilocybin", r, 200, lambda b: {"trial_id", "day", "phase", "counts", "pending_approvals",
                                                            "blocked", "report_status"} <= set(b))
    tid = st["trial_id"]
    R.expect("list trials", c.get("/api/trials"), 200, lambda b: any(x["trial_id"] == tid for x in b))
    R.expect("state", c.get(f"{T(tid)}/state"), 200, lambda b: b["trial_id"] == tid and b["day"] == -1)
    R.expect("step while blocked", c.post(f"{T(tid)}/step", json={"days": 1}), 200,
             lambda b: b["advanced"] is False and b["blocked"])
    R.expect("step days='abc'", c.post(f"{T(tid)}/step", json={"days": "abc"}), 422)
    R.expect("step no body", c.post(f"{T(tid)}/step"), 422)
    pend = R.expect("approvals pending", c.get(f"{T(tid)}/approvals"), 200, lambda b: len(b) >= 1 and b[0]["status"] == "pending")
    R.expect("approvals all", c.get(f"{T(tid)}/approvals?status=all"), 200, lambda b: len(b) >= len(pend))
    R.expect("approvals status=bogus", c.get(f"{T(tid)}/approvals?status=bogus"), 200, lambda b: b == [])
    aid = pend[0]["id"]
    D = f"{T(tid)}/approvals/{aid}"
    R.expect("decide bad decision", c.post(D, json={"reviewer": REVIEWER, "decision": "maybe"}), 400)
    R.expect("decide decision 'Approved' (case)", c.post(D, json={"reviewer": REVIEWER, "decision": "Approved"}), 400)
    R.expect("decide empty reviewer", c.post(D, json={"reviewer": "", "decision": "approved"}), 400)
    R.expect("decide whitespace reviewer", c.post(D, json={"reviewer": "   ", "decision": "approved"}), 400)
    R.expect("decide missing reviewer field", c.post(D, json={"decision": "approved"}), 422)
    R.expect("decide reviewer=null", c.post(D, json={"reviewer": None, "decision": "approved"}), 422)
    R.expect("decide unknown aid", c.post(f"{T(tid)}/approvals/deadbeef", json={"reviewer": REVIEWER, "decision": "approved"}), 404)
    R.expect("decide ok", c.post(D, json={"reviewer": REVIEWER, "decision": "approved", "comment": "e2e"}), 200,
             lambda b: b["approval"]["status"] == "approved" and b["approval"]["reviewer"] == REVIEWER and "state" in b)
    R.expect("decide already decided", c.post(D, json={"reviewer": REVIEWER, "decision": "approved"}), 404)

    # module actions before enrolment
    V = lambda mod: f"{T(tid)}/modules/{mod}/view"  # noqa: E731
    A = lambda mod, act: f"{T(tid)}/modules/{mod}/actions/{act}"  # noqa: E731
    for mod in ("predose", "dosing", "postdose"):
        R.expect(f"view {mod} day -1", c.get(V(mod)), 200, lambda b, mod=mod: b["module"] == mod and "status" in b)
    r = c.get(V("nosuch"))
    R.check("view unknown module -> 4xx", 400 <= r.status_code < 500, f"{r.status_code} {r.text[:150]}")
    r = c.post(A("nosuch", "x"), json={"payload": {}})
    R.check("action unknown module -> 4xx", 400 <= r.status_code < 500, f"{r.status_code} {r.text[:150]}")
    for mod in ("predose", "dosing", "postdose"):
        r = c.post(A(mod, "nosuch"), json={"payload": {}})
        R.check(f"action {mod}/nosuch -> 4xx", 400 <= r.status_code < 500, f"{r.status_code} {r.text[:150]}")
    R.expect("action body payload not a dict", c.post(A("dosing", "checkin"), json={"payload": "x"}), 422)
    R.expect("action no body", c.post(A("dosing", "checkin")), 422)
    ptxt = c.get("/api/protocols/example_psilocybin_trd.md").json()["text"]
    R.expect("predose recheck before enrolment (applies)", c.post(A("predose", "recheck"),
             json={"payload": {"text": ptxt + "\n\nE2E edit line.", "editor": REVIEWER}}), 200,
             lambda b: b["result"]["ok"] is True and "version" in b["result"])
    R.expect("predose recheck empty", c.post(A("predose", "recheck"), json={"payload": {"text": ""}}), 200,
             lambda b: b["result"]["ok"] is False)
    good = {"name": "E2E Valid", "age": 35, "phone": "+44 7700 900123", "nearest_site": "Site A (London)",
            "self_reported_diagnosis": "treatment-resistant depression", "failed_antidepressants": 2,
            "current_medication": "none", "history_psychosis": False, "history_bipolar": False,
            "cardiovascular_condition": False, "pregnant_or_breastfeeding": False, "prior_psychedelic_use": "never",
            "months_since_last_psychedelic": "", "can_attend_8_visits": True, "consents_to_chatbot_checkins": True,
            "consents_to_data_sharing": True, "free_text": "", "_hidden_exclusion": True, "id": "HACK-1"}
    b = R.expect("predose apply valid", c.post(A("predose", "apply"), json={"payload": good}), 200,
                 lambda b: b["result"]["ok"] is True and b["result"]["applicant"]["id"].startswith("PORTAL-"))
    R.expect("predose apply age='abc'", c.post(A("predose", "apply"), json={"payload": dict(good, age="abc")}), 200,
             lambda b: b["result"]["ok"] is False)
    r = c.post(A("predose", "apply"), json={"payload": dict(good, age="1e400")})
    R.expect("predose apply age='1e400' (overflow)", r, 200, lambda b: b["result"]["ok"] is False)
    R.check("predose apply age=1e400 gives a field error, not a generic failure",
            r.status_code == 200 and "whole number" in json.dumps(r.json()), r.text[:200])
    R.expect("predose apply applicant=list", c.post(A("predose", "apply"), json={"payload": {"applicant": [1, 2]}}), 200)
    R.expect("dosing checkin before enrolment", c.post(A("dosing", "checkin"), json={"payload": {"participant": "APP-0001"}}), 200,
             lambda b: b["result"]["ok"] is False)
    R.expect("postdose draft_report before lock", c.post(A("postdose", "draft_report"), json={"payload": {}}), 200,
             lambda b: b["result"]["ok"] is False)
    R.expect("postdose sign_off no reviewer", c.post(A("postdose", "sign_off"), json={"payload": {}}), 200,
             lambda b: b["result"]["ok"] is False)
    R.expect("postdose ask_question empty", c.post(A("postdose", "ask_question"), json={"payload": {}}), 200,
             lambda b: b["result"]["ok"] is False)

    # events / record / kpis / messages
    R.expect("events default", c.get(f"{T(tid)}/events"), 200, lambda b: all({"idx", "day", "agent", "text"} <= set(e) for e in b))
    ev_all = c.get(f"{T(tid)}/events?limit=100000").json()
    r0 = c.get(f"{T(tid)}/events?limit=0").json()
    R.check("events limit=0 returns no rows", len(r0) == 0, f"limit=0 returned {len(r0)} of {len(ev_all)} rows")
    r1 = c.get(f"{T(tid)}/events?limit=-1").json()
    R.check("events limit=-1 is rejected or empty", len(r1) == 0, f"limit=-1 returned {len(r1)} of {len(ev_all)} rows")
    R.expect("events limit=abc", c.get(f"{T(tid)}/events?limit=abc"), 422)
    R.expect("events since=5", c.get(f"{T(tid)}/events?since=5"), 200, lambda b: all(e["idx"] >= 5 for e in b))
    R.expect("events module=predose", c.get(f"{T(tid)}/events?module=predose"), 200, lambda b: all(e["module"] == "predose" for e in b))
    R.expect("record all", c.get(f"{T(tid)}/record"), 200, lambda b: "protocol" in b and "events" not in b and "messages" not in b)
    R.expect("record sections=protocol,kpis", c.get(f"{T(tid)}/record?sections=protocol,kpis"), 200, lambda b: set(b) == {"protocol", "kpis"})
    R.expect("record sections=bogus,events", c.get(f"{T(tid)}/record?sections=bogus,events"), 200, lambda b: b == {})
    R.expect("kpis", c.get(f"{T(tid)}/kpis"), 200, lambda b: set(b) == {"predose", "dosing", "postdose"})
    R.expect("messages", c.get(f"{T(tid)}/messages"), 200, lambda b: "edges" in b and "recent" in b)
    R.expect("auto_approve on=abc", c.post(f"{T(tid)}/auto_approve?on=abc"), 422)
    R.expect("auto_approve on=false", c.post(f"{T(tid)}/auto_approve?on=false"), 200, lambda b: b["auto_approve"] is False)

    # approve the rest of setup, enrol, then step timings
    decide_all(c, tid)
    st = c.get(f"{T(tid)}/state").json()
    R.check("enrolled after approving setup", st["counts"]["enrolled"] > 0 and not st["blocked"], st)
    size_by_day = {}
    r = c.post(f"{T(tid)}/step", json={"days": 1}, key="POST step days=1")
    R.expect("step 1", r, 200, lambda b: b["advanced"] and b["day"] == 0 and "state" in b)
    size_by_day[0] = sizes(c, tid)
    R.expect("predose recheck after enrolment (approval)", c.post(A("predose", "recheck"),
             json={"payload": {"text": ptxt + "\n\nAmendment line.", "editor": REVIEWER}}), 200,
             lambda b: b["result"]["ok"] is True and b["result"].get("pending_approval"))
    pid = c.get(f"{T(tid)}/record?sections=enrolled").json()["enrolled"][0]["id"]
    R.expect("dosing checkin valid", c.post(A("dosing", "checkin"), json={"payload": {"participant": pid, "guess": "drug",
             "confidence": 4, "expectancy": 3}}), 200, lambda b: b["result"]["ok"] is True)
    R.expect("dosing checkin free text", c.post(A("dosing", "checkin"), json={"payload": {"participant": pid,
             "answer": "I think I had the real drug, fairly sure, 4 out of 5, expected it to help 3"}}), 200)
    R.expect("dosing checkin incomplete", c.post(A("dosing", "checkin"), json={"payload": {"participant": pid, "answer": "hmm"}}), 200,
             lambda b: b["result"]["ok"] is False and b["result"].get("needs_reask"))
    R.expect("dosing checkin confidence='abc'", c.post(A("dosing", "checkin"), json={"payload": {"participant": pid,
             "guess": "drug", "confidence": "abc", "expectancy": 3}}), 200, lambda b: b["result"]["ok"] is False)
    R.expect("dosing checkin guess='banana'", c.post(A("dosing", "checkin"), json={"payload": {"participant": pid,
             "guess": "banana", "confidence": 4, "expectancy": 3}}), 200, lambda b: b["result"]["ok"] is False)
    for days in (1, 7):
        for _ in range(3):
            decide_all(c, tid)
            c.post(f"{T(tid)}/step", json={"days": days}, key=f"POST step days={days}")
    for days, lab in [(0, "days=0"), (-5, "days=-5"), (1000, "days=1000")]:
        before = c.get(f"{T(tid)}/state").json()["day"]
        r = c.post(f"{T(tid)}/step", json={"days": days}, key=f"POST step {lab}")
        after = r.json().get("day") if r.status_code == 200 else None
        R.check(f"step {lab} clamps (advanced {None if after is None else after - before})", r.status_code == 200 and
                after is not None and 1 <= after - before <= 30, f"{r.status_code} before {before} after {after}")
    advance(c, tid, 45)
    size_by_day[45] = sizes(c, tid)
    R.expect("postdose ask_question", c.post(A("postdose", "ask_question"),
             json={"payload": {"question": "Did participants who guessed drug improve more?", "researcher": REVIEWER}}), 200)
    R.expect("postdose request_export", c.post(A("postdose", "request_export"), json={"payload": {"requested_by": REVIEWER}}), 200)
    R.expect("postdose draft_report after lock?", c.post(A("postdose", "draft_report"), json={"payload": {}}), 200)
    # the remaining 30-day steps are timed individually
    while True:
        st = c.get(f"{T(tid)}/state").json()
        if st["phase"] == "closed":
            break
        decide_all(c, tid)
        r = c.post(f"{T(tid)}/step", json={"days": 30}, key="POST step days=30")
        if r.status_code != 200:
            break
    decide_all(c, tid)
    size_by_day[90] = sizes(c, tid)
    st = c.get(f"{T(tid)}/state").json()
    R.check("trial closed at day 90", st["phase"] == "closed" and st["day"] == 90, st)
    R.expect("step after close", c.post(f"{T(tid)}/step", json={"days": 1}), 200, lambda b: b["day"] == 90)
    R.expect("postdose sign_off after close (nothing pending)", c.post(A("postdose", "sign_off"),
             json={"payload": {"reviewer": REVIEWER}}), 200)

    # size stress: the largest allowed trial (n_applicants=2000), auto-approve, run to close
    big = c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "n_applicants": 2000, "auto_approve": True},
                 key="POST trials (n=2000)").json()
    advance(c, big["trial_id"], 90)
    big_sizes = sizes(c, big["trial_id"])
    R.check("n_applicants=2000 at day 90: GET record under 1 MB", big_sizes["record_all"] < MB,
            f"record_all {big_sizes['record_all']} bytes")
    size_by_day["90_n2000"] = big_sizes

    # latency: repeated GETs on a closed trial (the biggest payloads)
    for _ in range(a.reps):
        for p, k in [("/api/health", None), ("/api/bottlenecks", None), ("/api/protocols", None),
                     (f"/api/protocols/{name}", "GET /api/protocols/{name}"), ("/api/trials", None),
                     (f"{T(tid)}/state", "GET state"), (f"{T(tid)}/record", "GET record"),
                     (f"{T(tid)}/events", "GET events"), (f"{T(tid)}/approvals?status=all", "GET approvals"),
                     (f"{T(tid)}/kpis", "GET kpis"), (f"{T(tid)}/messages", "GET messages"),
                     (f"{T(tid)}/modules/predose/view", "GET view predose"),
                     (f"{T(tid)}/modules/dosing/view", "GET view dosing"),
                     (f"{T(tid)}/modules/postdose/view", "GET view postdose")]:
            c.get(p, key=k)
    for _ in range(3):
        t0 = time.perf_counter()
        c.post("/api/trials", json={"example": "example_psilocybin_trd.md", "seed": 7}, key="POST trials (create)")

    # every response of the run, scanned again in full for privacy (record, events, approvals at day 90)
    for p in ["record", "events?limit=100000", "approvals?status=all", "kpis", "messages", "modules/predose/view",
              "modules/dosing/view", "modules/postdose/view", "state"]:
        R.scan(f"final {p}", c.get(f"{T(tid)}/{p}"))
    R.check("privacy: no '_' keys or participant arm at any depth", not R.privacy, R.privacy[:3])
    R.check("no response over 1 MB", not R.big, R.big)

    ev = None
    if a.evidence:
        R.expect("evidence bad body", c.post("/api/evidence/run", json={}), 422)
        t0 = time.perf_counter()
        try:
            r = c.post("/api/evidence/run", json={"input": "psilocybin treatment resistant depression"}, timeout=90)
            ev = {"status": r.status_code, "s": round(time.perf_counter() - t0, 1), "bytes": len(r.content),
                  "body_head": r.text[:300]}
        except Exception as e:  # noqa: BLE001
            ev = {"error": f"{type(e).__name__}: {e}", "s": round(time.perf_counter() - t0, 1)}
        print("evidence:", ev)

    out = {"base": a.base, "trial": tid, "create_ms": round(create_ms, 1), "checks": R.checks, "privacy": R.privacy,
           "over_1mb": R.big, "arm_key_paths": sorted(R.arm_paths), "sizes_bytes_by_day": size_by_day,
           "latency": c.latency_table(), "evidence": ev}
    os.makedirs(RESULTS, exist_ok=True)
    dump(out, os.path.join(RESULTS, f"contract_{a.label}.json"))
    fails = [x for x in R.checks if not x["ok"]]
    print(f"\n{len(R.checks) - len(fails)} passed, {len(fails)} failed")
    print("sizes (bytes):", json.dumps(size_by_day, indent=1))
    for row in c.latency_table():
        print(f"{row['endpoint']:<45} n={row['n']:<3} p50={row['p50_ms']:>8} ms  max={row['max_ms']:>8} ms")
    print("arm-like key paths:", sorted(R.arm_paths))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
