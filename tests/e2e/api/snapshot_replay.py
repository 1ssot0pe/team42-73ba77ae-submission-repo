"""Section C measurements for the state-fix decision (in-process, no server).

    .venv/bin/python tests/e2e/api/snapshot_replay.py [--n-applicants 500] [--runs 3]

1. Serialised size of a trial at day 0, 45 and 90: pickle of the Master (after dropping its lock and llm
   references; the first attempt pickles it untouched to show what fails), JSON of the record, and gzip of both.
2. Wall time to replay a full trial from creation to close (same seed, auto_approve).
3. Determinism: two replays with the same seed, compared field by field, to find ids and draws that differ.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
import pickle
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, ROOT)
os.environ.setdefault("UNBLIND_TRIALS_DIR", tempfile.mkdtemp(prefix="parallax-snap-"))

from unblind.platform.master.orchestrator import Master  # noqa: E402

PROTO = open(os.path.join(ROOT, "data", "protocols", "example_psilocybin_trd.md")).read()
KB = 1024


def new(tid, n, seed=42):
    m = Master(tid, protocol={"text": PROTO}, seed=seed, n_applicants=n, auto_approve=True)
    m.setup()
    return m


def try_pickle(obj):
    try:
        return len(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def find_unpicklable(obj, path="m", depth=0, seen=None):
    """Walk attributes to name the parts that will not pickle."""
    seen = seen if seen is not None else set()
    if id(obj) in seen or depth > 4:
        return []
    seen.add(id(obj))
    n, err = try_pickle(obj)
    if err is None:
        return []
    kids = []
    if isinstance(obj, dict):
        kids = [(f"{path}[{k!r}]", v) for k, v in obj.items()]
    elif isinstance(obj, (list, tuple)):
        kids = [(f"{path}[{i}]", v) for i, v in enumerate(obj)]
    elif hasattr(obj, "__dict__"):
        kids = [(f"{path}.{k}", v) for k, v in vars(obj).items()]
    deeper = []
    for p, v in kids:
        deeper += find_unpicklable(v, p, depth + 1, seen)
    return deeper or [f"{path} ({type(obj).__name__}): {err}"]


def strip_for_pickle(m):
    m2 = copy.copy(m)
    m2.lock = None
    m2.ctx = copy.copy(m.ctx)
    m2.ctx.llm = None
    return m2


def measure(m):
    rec_json = json.dumps(m.rec, default=str).encode()
    rec_json_indent = json.dumps(m.rec, indent=1, default=str).encode()   # what TrialRecord.save writes
    raw_n, raw_err = try_pickle(m)
    m2 = strip_for_pickle(m)
    n, err = try_pickle(m2)
    out = {
        "record_json_kb": round(len(rec_json) / KB, 1),
        "record_json_gzip_kb": round(len(gzip.compress(rec_json)) / KB, 1),
        "record_json_indent1_kb (on-disk save)": round(len(rec_json_indent) / KB, 1),
        "pickle_untouched": raw_err or f"{round(raw_n / KB, 1)} KB",
        "pickle_stripped_kb": round(n / KB, 1) if n else None,
        "pickle_stripped_error": err,
        "vault_json_kb": round(len(json.dumps({"alloc": m.vault._alloc, "log": m.vault.access_log}).encode()) / KB, 1),
        "world_pickle_kb": (lambda r: round(r[0] / KB, 1) if r[0] else r[1])(try_pickle(m.world)),
    }
    if n:
        blob = pickle.dumps(m2, protocol=pickle.HIGHEST_PROTOCOL)
        out["pickle_stripped_gzip_kb"] = round(len(gzip.compress(blob)) / KB, 1)
        t = time.perf_counter()
        m3 = pickle.loads(blob)
        out["unpickle_ms"] = round((time.perf_counter() - t) * 1000, 1)
        # does a restored master keep working? (the lock and llm must be re-attached)
        import threading
        from unblind import llm
        m3.lock = threading.RLock()
        m3.ctx.llm = llm
        same_rec = m3.rec is m3.ctx.rec and m3.ctx.bus.rec is m3.rec and m3.ctx.approvals.rec is m3.rec
        out["restored_shares_one_record_object"] = same_rec
        try:
            d0 = m3.rec["day"]
            if m3.rec["phase"] != "closed":
                m3.step(1)
            out["restored_can_step"] = m3.rec["day"] == d0 + 1 or m3.rec["phase"] == "closed"
        except Exception as e:  # noqa: BLE001
            out["restored_can_step"] = f"{type(e).__name__}: {e}"
    return out, raw_err


def strip_volatile(o):
    """Remove fields expected to differ (wall clock), to see what else differs."""
    if isinstance(o, dict):
        return {k: strip_volatile(v) for k, v in o.items() if k not in ("t", "created")}
    if isinstance(o, list):
        return [strip_volatile(x) for x in o]
    return o


def diff(a, b, path="$", out=None, limit=60):
    out = out if out is not None else []
    if len(out) >= limit:
        return out
    if type(a) is not type(b):
        out.append(f"{path}: type {type(a).__name__} vs {type(b).__name__}")
    elif isinstance(a, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out.append(f"{path}.{k}: missing on one side")
            else:
                diff(a[k], b[k], f"{path}.{k}", out, limit)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append(f"{path}: len {len(a)} vs {len(b)}")
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out, limit)
    elif a != b:
        out.append(f"{path}: {str(a)[:40]!r} vs {str(b)[:40]!r}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-applicants", type=int, default=500)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()
    res = {"n_applicants": a.n_applicants, "trials_dir": os.environ["UNBLIND_TRIALS_DIR"]}

    m = new("SNAP-1", a.n_applicants)
    sizes = {}
    m.run_to(0)
    sizes["day0"], raw_err = measure(m)
    if raw_err:
        res["pickle_untouched_fails_on"] = find_unpicklable(m)[:10]
    m.run_to(45)
    sizes["day45"], _ = measure(m)
    m.run_to(90)
    sizes["day90"], _ = measure(m)
    res["sizes"] = sizes

    # replay timing: creation to close, same seed, auto-approve
    times = []
    recs = []
    for i in range(a.runs):
        t = time.perf_counter()
        r = new(f"REPLAY-{i}", a.n_applicants)
        t_setup = time.perf_counter() - t
        r.run_to(90)
        times.append({"total_s": round(time.perf_counter() - t, 3), "setup_s": round(t_setup, 3),
                      "final_day": r.rec["day"], "phase": r.rec["phase"]})
        recs.append(r)
    res["replay"] = times

    # replay without disk writes: how much of the replay is TrialRecord.save()?
    from unblind.platform import core
    orig = core.TrialRecord.save
    core.TrialRecord.save = lambda self: None
    t = time.perf_counter()
    r = new("REPLAY-NOSAVE", a.n_applicants)
    r.run_to(90)
    res["replay_without_save_s"] = round(time.perf_counter() - t, 3)
    core.TrialRecord.save = orig

    # determinism between two replays (trial_id differs by construction; compare everything else)
    A = strip_volatile(json.loads(json.dumps(recs[0].rec, default=str)))
    B = strip_volatile(json.loads(json.dumps(recs[1].rec, default=str)))
    A["trial_id"] = B["trial_id"] = "X"
    d = diff(A, B)
    res["determinism_diffs_sample"] = d[:40]
    kinds = {}
    for line in diff(A, B, limit=100000):
        key = "".join(ch if not ch.isdigit() else "#" for ch in line.split(":")[0])
        kinds[key] = kinds.get(key, 0) + 1
    res["determinism_diff_paths"] = dict(sorted(kinds.items(), key=lambda kv: -kv[1])[:25])
    res["same_alloc"] = recs[0].vault._alloc == recs[1].vault._alloc
    res["same_events_text"] = [e["text"] for e in recs[0].rec["events"]] == [e["text"] for e in recs[1].rec["events"]]

    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    with open(os.path.join(os.path.dirname(__file__), "results", f"snapshot_replay_n{a.n_applicants}.json"), "w") as f:
        json.dump(res, f, indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
