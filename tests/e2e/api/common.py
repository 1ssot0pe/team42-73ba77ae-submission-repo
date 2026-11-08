"""Shared helpers for the API end-to-end scripts (stdlib + requests only).

    Client(base)      : thin requests wrapper that times every call and keeps a log
    privacy_scan(obj) : recursive walk; finds '_' keys and allocation / arm assignment leaks
    pct(xs, p)        : percentile
"""
from __future__ import annotations

import json
import re
import statistics
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

import requests

ARM_VALUES = {"drug", "control", "placebo", "active"}
ARM_KEYS = {"arm", "alloc", "allocation", "assignment", "assigned", "assigned_arm", "true_arm", "treatment_arm",
            "group_assignment", "randomised_to", "randomized_to"}
PID_KEYS = {"participant", "participant_id", "pid", "id"}
PID_RE = re.compile(r"^(APP|PORTAL|P)-\d+$")
MB = 1024 * 1024


def privacy_scan(obj: Any, path: str = "$") -> List[str]:
    """Return a list of violations: underscore keys, or a participant-level arm assignment at any depth.
    Aggregates ({arm, guess, n, mean_change}) are allowed; a row with a participant id plus an arm is a leak,
    and so is a {participant_id: 'drug'|'control'} mapping."""
    out: List[str] = []
    if isinstance(obj, dict):
        keys = {str(k) for k in obj}
        pid_like = [k for k in keys if PID_RE.match(k)]
        if pid_like and sum(1 for k in pid_like if str(obj[k]).lower() in ARM_VALUES) >= 1:
            out.append(f"{path}: participant->arm mapping ({len(pid_like)} participant keys)")
        has_pid = bool(keys & PID_KEYS) and any(PID_RE.match(str(obj.get(k, ""))) for k in keys & PID_KEYS)
        for k, v in obj.items():
            ks = str(k)
            if ks.startswith("_"):
                out.append(f"{path}.{ks}: private key")
            if ks.lower() in ARM_KEYS and str(v).lower() in ARM_VALUES and has_pid:
                out.append(f"{path}.{ks}={v}: arm assignment next to a participant id")
            out.extend(privacy_scan(v, f"{path}.{ks}"))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            out.extend(privacy_scan(x, f"{path}[{i}]"))
    return out


def arm_key_paths(obj: Any, path: str = "$") -> List[str]:
    """Every path whose key is arm-like (for manual review; aggregates are expected here)."""
    out: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in ARM_KEYS:
                out.append(re.sub(r"\[\d+\]", "[]", f"{path}.{k}"))
            out.extend(arm_key_paths(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            out.extend(arm_key_paths(x, f"{path}[{i}]"))
    return out


def norm_key(method: str, path: str) -> str:
    """'GET /api/trials/T-123456-ab12/approvals/deadbeef?x' -> 'GET /api/trials/{tid}/approvals/{aid}'."""
    p = path.split("?")[0]
    p = re.sub(r"/api/trials/[^/]+", "/api/trials/{tid}", p) if p.count("/") > 3 else p
    p = re.sub(r"/approvals/[^/]+$", "/approvals/{aid}", p)
    p = re.sub(r"^/api/protocols/.+$", "/api/protocols/{name}", p)
    return f"{method} {p}"


def pct(xs: List[float], p: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = (len(xs) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


class Client:
    def __init__(self, base: str, timeout: float = 120.0, headers: Optional[dict] = None):
        self.base = base.rstrip("/")
        self.s = requests.Session()
        if headers:
            self.s.headers.update(headers)
        self.timeout = timeout
        self.log: List[dict] = []
        self.lat: Dict[str, List[float]] = defaultdict(list)

    def call(self, method: str, path: str, key: Optional[str] = None, **kw) -> requests.Response:
        t = time.perf_counter()
        r = self.s.request(method, self.base + path, timeout=kw.pop("timeout", self.timeout), **kw)
        dt = time.perf_counter() - t
        key = key or norm_key(method, path)
        self.lat[key].append(dt)
        self.log.append({"key": key, "method": method, "path": path, "status": r.status_code, "ms": round(dt * 1000, 1),
                         "bytes": len(r.content), "backend": r.headers.get("X-RR-Backend"),
                         "vercel_id": r.headers.get("x-vercel-id")})
        return r

    def get(self, path, key=None, **kw):
        return self.call("GET", path, key, **kw)

    def post(self, path, key=None, **kw):
        return self.call("POST", path, key, **kw)

    def latency_table(self, ok_only: bool = False) -> List[dict]:
        """p50/max per endpoint; ok_only keeps only responses with status < 400 (prod 404s are fast fails)."""
        rows = []
        lat = self.lat
        if ok_only:
            lat = defaultdict(list)
            for r in self.log:
                if r["status"] < 400:
                    lat[r["key"]].append(r["ms"] / 1000)
        for k, xs in sorted(lat.items()):
            rows.append({"endpoint": k, "n": len(xs), "p50_ms": round(pct(xs, .5) * 1000, 1),
                         "max_ms": round(max(xs) * 1000, 1)})
        return rows


def dump(obj: Any, path: str) -> None:
    with open(path, "w") as f:
        json.dump(obj, f, indent=1, default=str)


def median(xs):
    return statistics.median(xs) if xs else None
