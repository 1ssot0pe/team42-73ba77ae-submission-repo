"""Walk a psilocybin trial (seed 42, 500 applicants, manual approvals) to a given day, as in the visuals audit.

Every pending approval is approved by "Dr A. Auditor" except a drift approval raised on the current day, which is
left for one day so the action falls the day after the alert (as in the audit). Usage:
    python tests/e2e/visuals/walk_dosing.py create            -> prints the trial id
    python tests/e2e/visuals/walk_dosing.py <trial_id> <day>  -> advances to that day
"""
import json
import sys
import urllib.request

API = "http://127.0.0.1:8713"


def call(path, body=None):
    req = urllib.request.Request(API + path, method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


def approve_pending(tid, day):
    n = 0
    for a in call(f"/api/trials/{tid}/approvals?status=pending"):
        drift = "rater" in (a.get("title", "") + a.get("summary", "")).lower() and a.get("module") == "dosing"
        if drift and a.get("day") == day:
            continue
        call(f"/api/trials/{tid}/approvals/{a['id']}", {"reviewer": "Dr A. Auditor", "decision": "approved"})
        n += 1
    return n


def walk(tid, target):
    for _ in range(400):
        st = call(f"/api/trials/{tid}/state")
        if approve_pending(tid, st["day"]):
            continue
        if st["day"] >= target:
            return st
        out = call(f"/api/trials/{tid}/step", {"days": 1})
        if out["state"]["day"] == st["day"] and not call(f"/api/trials/{tid}/approvals?status=pending"):
            raise SystemExit(f"stuck at day {st['day']}: {out['state'].get('blocked')}")
    raise SystemExit("too many steps")


if __name__ == "__main__":
    if sys.argv[1] == "create":
        st = call("/api/trials", {"example": "example_psilocybin_trd.md", "n_applicants": 500, "seed": 42,
                                  "auto_approve": False})
        print(st["trial_id"])
    else:
        print(json.dumps(walk(sys.argv[1], int(sys.argv[2])))[:300])
