"""Shared Playwright harness for the production browser journeys (Tester BROWSER-PROD).

Each journey gets a fresh browser context (empty localStorage) and records:
  * console errors and uncaught page errors
  * every /api/ response: method, path, status, duration (ms), x-vercel-id, and body for status >= 400
  * failed network requests (requestfailed)
  * trial losses: 404 on /api/trials/{id}/..., with the call and the time since journey start
  * screenshots at failure points: docs/testing/screenshots/prod-<journey>-<n>.png
Results go to tests/e2e/prod/results/<journey>.json.

Usage from a journey script:
    with Run("J1") as r:
        r.page.goto(PROD)
        ...
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Page, sync_playwright

PROD = os.environ.get("PROD_URL", "https://parallax-two-tau.vercel.app").rstrip("/")
ROOT = Path(__file__).resolve().parents[3]
SHOTS = ROOT / "docs" / "testing" / "screenshots"
RESULTS = Path(__file__).resolve().parent / "results"
TRIAL_PATH = re.compile(r"/api/trials/([^/?]+)/([^?]+)")
REVIEWER = "E2E Prod Tester"
# SERIAL=1: an init script queues the page's /api/ fetches so the page never has two API calls in flight.
# Test-only workaround (no product code changes): sequential requests stay on the one warm Vercel instance,
# concurrent ones overflow to fresh instances that do not hold the trial. Results get a -serial suffix.
SERIAL = os.environ.get("SERIAL") == "1"
SERIAL_GAP_MS = int(os.environ.get("SERIAL_GAP_MS", "0"))
SERIAL_JS = """(() => {
  const GAP_MS = %d;""" % SERIAL_GAP_MS + """
  const orig = window.fetch.bind(window);
  let q = Promise.resolve();
  window.fetch = (input, init) => {
    const url = typeof input === 'string' ? input : (input && input.url) || '';
    if (!url.includes('/api/')) return orig(input, init);
    const p = q.then(() => orig(input, init));
    const gap = () => new Promise(res => setTimeout(res, GAP_MS));
    q = p.then(r => r.clone().arrayBuffer().catch(() => null), () => null).then(gap);
    return p;
  };
})();"""


class Run:
    def __init__(self, name: str, *, viewport: Optional[Dict[str, int]] = None, color_scheme: str = "light",
                 seed_reviewer: bool = True, headless: bool = True):
        self.name = name + ("-serial" if SERIAL else "")
        self.viewport = viewport or {"width": 1440, "height": 1000}
        self.color_scheme = color_scheme
        self.seed_reviewer = seed_reviewer
        self.headless = headless
        self.t0 = time.time()
        self.console_errors: List[Dict[str, Any]] = []
        self.page_errors: List[str] = []
        self.api: List[Dict[str, Any]] = []
        self.failed: List[Dict[str, Any]] = []
        self.trial_404: List[Dict[str, Any]] = []
        self.shots: List[str] = []
        self.notes: List[str] = []
        self.timings: Dict[str, float] = {}
        self.checks: List[Dict[str, Any]] = []
        self._starts: Dict[Any, float] = {}
        self._shot_n = 0

    # ------------------------------------------------------------ lifecycle
    def __enter__(self) -> "Run":
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch(headless=self.headless)
        self.context = self.browser.new_context(viewport=self.viewport, color_scheme=self.color_scheme)
        if SERIAL:
            self.context.add_init_script(SERIAL_JS)
        if self.seed_reviewer:
            self.context.add_init_script(
                f"try {{ if (!localStorage.getItem('unblind.reviewer')) localStorage.setItem('unblind.reviewer', {json.dumps(REVIEWER)}); }} catch (e) {{}}")
        self.page = self.new_page()
        return self

    def new_page(self) -> Page:
        p = self.context.new_page()
        p.set_default_timeout(30_000)
        p.on("console", lambda m: self._console(m))
        p.on("pageerror", lambda e: self.page_errors.append(str(e)))
        p.on("request", lambda rq: self._starts.__setitem__(id(rq), time.time()))
        p.on("response", lambda rs: self._response(rs))
        p.on("requestfailed", lambda rq: self.failed.append(
            {"t": self.el(), "method": rq.method, "url": rq.url, "failure": rq.failure}))
        return p

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.notes.append(f"EXCEPTION {exc_type.__name__}: {exc}")
            try:
                self.shot("exception")
            except Exception:
                pass
        self.save()
        try:
            self.context.close()
            self.browser.close()
        finally:
            self._pw.stop()
        return False  # re-raise

    # ------------------------------------------------------------ recording
    def el(self) -> float:
        return round(time.time() - self.t0, 2)

    def _console(self, m) -> None:
        if m.type == "error":
            self.console_errors.append({"t": self.el(), "text": m.text, "url": self.page.url if hasattr(self, "page") else ""})

    def _response(self, rs) -> None:
        url = rs.url
        if "/api/" not in url:
            if rs.status >= 400:
                self.failed.append({"t": self.el(), "method": rs.request.method, "url": url, "status": rs.status})
            return
        start = self._starts.pop(id(rs.request), None)
        dur = round((time.time() - start) * 1000) if start else None
        path = url.split(PROD, 1)[-1]
        row: Dict[str, Any] = {"t": self.el(), "method": rs.request.method, "path": path, "status": rs.status,
                               "ms": dur, "vercel_id": rs.headers.get("x-vercel-id")}
        if rs.status >= 400:
            try:
                row["body"] = rs.text()[:500]
            except Exception as e:  # body may be gone after navigation
                row["body"] = f"<unreadable: {e}>"
            self.failed.append(row)
            m = TRIAL_PATH.search(path)
            if m and rs.status == 404:
                self.trial_404.append({"t": self.el(), "trial": m.group(1), "call": f"{rs.request.method} {m.group(2)}",
                                       "page": self.page.url.split(PROD, 1)[-1], "vercel_id": row["vercel_id"],
                                       "body": row.get("body")})
        self.api.append(row)

    def shot(self, label: str = "", page: Optional[Page] = None, full: bool = False) -> str:
        self._shot_n += 1
        SHOTS.mkdir(parents=True, exist_ok=True)
        path = SHOTS / f"prod-{self.name}-{self._shot_n}.png"
        (page or self.page).screenshot(path=str(path), full_page=full)
        rel = str(path.relative_to(ROOT))
        self.shots.append(f"{rel} {label}".strip())
        return rel

    def note(self, s: str) -> None:
        print(f"[{self.name} {self.el():7.1f}s] {s}", flush=True)
        self.notes.append(f"{self.el()}s {s}")

    def check(self, what: str, ok: bool, detail: str = "") -> bool:
        self.checks.append({"check": what, "ok": bool(ok), "detail": detail})
        self.note(f"{'PASS' if ok else 'FAIL'} {what} {detail}")
        if not ok:
            try:
                self.shot(f"FAIL {what}")
            except Exception:
                pass
        return bool(ok)

    def save(self) -> None:
        RESULTS.mkdir(parents=True, exist_ok=True)
        api_calls = [a for a in self.api if a["path"].startswith("/api/")]
        trial_calls = [a for a in api_calls if TRIAL_PATH.search(a["path"])]
        out = {
            "journey": self.name, "url": PROD, "elapsed_s": self.el(), "viewport": self.viewport,
            "color_scheme": self.color_scheme, "serial": SERIAL,
            "api_calls": len(api_calls), "trial_calls": len(trial_calls), "trial_404": self.trial_404,
            "trial_404_rate": round(len(self.trial_404) / len(trial_calls), 4) if trial_calls else None,
            "console_errors": self.console_errors, "page_errors": self.page_errors, "failed": self.failed,
            "checks": self.checks, "timings": self.timings, "screenshots": self.shots, "notes": self.notes,
            "api_latency": latency_summary(api_calls), "api": self.api,
        }
        (RESULTS / f"{self.name}.json").write_text(json.dumps(out, indent=1))
        print(f"[{self.name}] saved: {len(api_calls)} api calls, {len(trial_calls)} trial calls, "
              f"{len(self.trial_404)} trial 404s, {len(self.console_errors)} console errors, "
              f"{sum(1 for c in self.checks if not c['ok'])} failed checks", flush=True)


def latency_summary(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    by: Dict[str, List[int]] = {}
    for r in rows:
        key = r["method"] + " " + re.sub(r"/api/trials/[^/?]+", "/api/trials/{id}", r["path"].split("?")[0])
        key = re.sub(r"/approvals/[^/]+$", "/approvals/{aid}", key)
        if r["ms"] is not None:
            by.setdefault(key, []).append(r["ms"])
    out = {}
    for k, v in sorted(by.items()):
        v = sorted(v)
        out[k] = {"n": len(v), "p50": v[len(v) // 2], "max": v[-1]}
    return out


# ---------------------------------------------------------------- UI helpers
def goto(r: Run, path: str = "/", page: Optional[Page] = None) -> float:
    p = page or r.page
    t = time.time()
    p.goto(PROD + path, wait_until="networkidle")
    return round((time.time() - t) * 1000)


def on_start_screen(p: Page) -> bool:
    return p.get_by_role("heading", name="Start a trial").is_visible()


def create_trial(r: Run, example: Optional[str] = "psilocybin", text: Optional[str] = None, auto: bool = False) -> Optional[str]:
    """From the Mission control start screen. Returns the trial id shown in the header, or None."""
    p = r.page
    p.get_by_role("heading", name="Start a trial").wait_for()
    ta = p.locator("#mc-protocol")
    if text is not None:
        ta.fill(text)
    elif example:
        p.locator("button.tab", has_text=re.compile(example, re.I)).first.click()
        p.wait_for_function("() => document.querySelector('#mc-protocol')?.value.length > 50")
    if auto:
        p.get_by_label("Auto-approve (demo fast-forward)").check()
    t = time.time()
    with p.expect_response(lambda rs: rs.url.endswith("/api/trials") and rs.request.method == "POST", timeout=60_000) as resp:
        p.get_by_role("button", name="Create trial").click()
    rs = resp.value
    r.timings.setdefault("create_ms", []).append(round((time.time() - t) * 1000))  # type: ignore[attr-defined]
    if rs.status != 200:
        r.note(f"create trial -> {rs.status} {rs.text()[:200]}")
        return None
    tid = rs.json()["trial_id"]
    r.note(f"created {tid}")
    p.wait_for_load_state("networkidle")
    return tid


def state_text(p: Page) -> str:
    try:
        return p.locator("header.mc-head").first.inner_text(timeout=3000)
    except Exception:
        return ""


def pending_slips(p: Page):
    return p.locator("article.slip")


def approve_all(r: Run, decision: str = "Approve", max_n: int = 20, page: Optional[Page] = None, match: Optional[str] = None) -> List[str]:
    """Sign pending slips on the current page, one at a time. Returns the titles signed."""
    p = page or r.page
    done: List[str] = []
    for _ in range(max_n):
        slips = pending_slips(p)
        if match:
            slips = slips.filter(has_text=re.compile(match, re.I))
        if slips.count() == 0:
            break
        s = slips.first
        try:
            title = s.locator(".slip__title").inner_text(timeout=5000)
            aid = s.get_attribute("aria-labelledby", timeout=5000)
            s = p.locator(f'article.slip[aria-labelledby="{aid}"]')
            inp = s.get_by_placeholder("Your name")
            if not inp.input_value(timeout=5000):
                inp.fill(REVIEWER)
        except Exception as e:
            r.note(f"slip re-rendered while reading it: {e}")
            p.wait_for_timeout(1000)
            continue
        try:
            with p.expect_response(lambda rs: "/approvals/" in rs.url and rs.request.method == "POST", timeout=60_000) as resp:
                s.get_by_role("button", name=decision, exact=True).click()
            st = resp.value.status
        except Exception as e:
            r.note(f"sign '{title}' failed: {e}")
            break
        r.note(f"{decision} '{title}' -> {st}")
        done.append(f"{title} -> {st}")
        p.wait_for_load_state("networkidle")
        if st != 200:
            break
    return done


def dock_button(p: Page, name: str):
    return p.get_by_role("toolbar", name="Trial controls").get_by_role("button", name=name, exact=True)


def play_until_stop(r: Run, timeout_s: float = 240) -> Dict[str, Any]:
    """Press Play and wait until the loop stops (blocked, closed, error). Returns step stats."""
    p = r.page
    n0 = len([a for a in r.api if a["path"].endswith("/step")])
    t = time.time()
    dock_button(p, "Play").click()
    try:
        dock_button(p, "Play").wait_for(timeout=timeout_s * 1000)
    except Exception:
        r.note("play did not stop within timeout; pausing")
        try:
            dock_button(p, "Pause").click()
        except Exception:
            pass
    p.wait_for_load_state("networkidle")
    steps = [a for a in r.api if a["path"].endswith("/step")][n0:]
    return {"s": round(time.time() - t, 1), "steps": len(steps), "statuses": sorted({a["status"] for a in steps}),
            "max_ms": max((a["ms"] or 0 for a in steps), default=0)}


def headline(p: Page) -> str:
    try:
        return p.locator("h1").first.inner_text(timeout=3000).replace("\n", " ")
    except Exception:
        return ""


def api_get(r: Run, path: str) -> Dict[str, Any]:
    rs = r.context.request.get(PROD + path)
    return {"status": rs.status, "json": (rs.json() if rs.ok else rs.text()[:300])}


def toasts(p: Page) -> List[str]:
    try:
        return [t.strip() for t in p.locator(".toast").all_inner_texts()]
    except Exception:
        return []
