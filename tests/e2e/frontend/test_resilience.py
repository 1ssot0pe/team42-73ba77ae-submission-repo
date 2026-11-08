"""Frontend resilience regression test (Python Playwright, Chromium).

Starts the real backend on 127.0.0.1:8201 and vite on 127.0.0.1:5199, then uses page.route to inject
failures in front of the backend:

  (a) one 503 on a state call and one on a step call must not lose the trial; both succeed after a retry
  (b) a persistent "trial not found" 404 shows the TrialLost state, stops polling, and its button
      clears the stored trial id and goes to the start page
  (c) a refresh mid-trial reattaches to the same trial id

Opt-in, because it needs node, vite and Chromium:
    PARALLAX_E2E_FRONTEND=1 .venv/bin/python -m pytest -q tests/e2e/frontend
Override the ports with PARALLAX_E2E_API_PORT and PARALLAX_E2E_VITE_PORT.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

if os.environ.get("PARALLAX_E2E_FRONTEND") != "1":
    pytest.skip("set PARALLAX_E2E_FRONTEND=1 to run the browser resilience test", allow_module_level=True)

from playwright.sync_api import Page, Route, expect, sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
API_PORT = int(os.environ.get("PARALLAX_E2E_API_PORT", "8201"))
VITE_PORT = int(os.environ.get("PARALLAX_E2E_VITE_PORT", "5199"))
API = f"http://127.0.0.1:{API_PORT}"
APP = f"http://127.0.0.1:{VITE_PORT}"
TRIAL_KEY = "unblind.trialId"


def _wait_port(port: int, timeout: float = 60.0) -> None:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.25)
    raise RuntimeError(f"port {port} did not open")


@pytest.fixture(scope="module")
def servers():
    procs = []
    logs = tempfile.mkdtemp(prefix="parallax-fe-e2e-")
    env = dict(os.environ, UNBLIND_TRIALS_DIR=os.path.join(logs, "trials"))
    procs.append(subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(API_PORT)],
        cwd=ROOT, env=env, stdout=open(os.path.join(logs, "api.log"), "w"), stderr=subprocess.STDOUT))
    procs.append(subprocess.Popen(
        ["npx", "vite", "--port", str(VITE_PORT), "--strictPort"],
        cwd=ROOT / "frontend", env=dict(os.environ, VITE_API_TARGET=API),
        stdout=open(os.path.join(logs, "vite.log"), "w"), stderr=subprocess.STDOUT))
    try:
        _wait_port(API_PORT)
        _wait_port(VITE_PORT)
        yield
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


@pytest.fixture(scope="module")
def browser(servers):
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    p = ctx.new_page()
    yield p
    ctx.close()


def create_trial() -> str:
    body = json.dumps({"example": "example_psilocybin_trd.md", "n_applicants": 60, "seed": 7, "auto_approve": True}).encode()
    req = urllib.request.Request(f"{API}/api/trials", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)["trial_id"]


def open_trial(page: Page, trial_id: str) -> None:
    """Load the app with this trial remembered, as a returning visitor would."""
    page.goto(APP + "/")
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [TRIAL_KEY, trial_id])
    page.reload()


def stored_id(page: Page):
    return page.evaluate("k => localStorage.getItem(k)", TRIAL_KEY)


def fail_once(page: Page, pattern: str, method: str, status: int = 503, times: int = 1) -> dict:
    """Answer the first `times` matching requests with `status`, pass the rest through. Returns hit counters."""
    seen = {"failed": 0, "passed": 0}

    def handler(route: Route) -> None:
        if route.request.method != method:
            route.continue_()
            return
        if seen["failed"] < times:
            seen["failed"] += 1
            route.fulfill(status=status, content_type="application/json",
                          body=json.dumps({"detail": "Service Unavailable"}))
        else:
            seen["passed"] += 1
            route.continue_()

    page.route(re.compile(pattern), handler)
    return seen


# ------------------------------------------------------------------ (a) transient 503
def test_one_503_on_state_does_not_lose_the_trial(page: Page):
    tid = create_trial()
    page.goto(APP + "/")
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [TRIAL_KEY, tid])
    # fail the first two state loads (React StrictMode mounts the provider twice in dev)
    seen = fail_once(page, r"/api/trials/[^/]+/state$", "GET", times=2)
    page.reload()
    # the trial loads after the retry: the dock shows its id, and nothing was forgotten
    expect(page.locator(".mc-dock__id")).to_have_text(tid, timeout=15000)
    assert seen["failed"] >= 1 and seen["passed"] >= 1
    assert stored_id(page) == tid


def test_one_503_on_step_retries_and_advances(page: Page):
    tid = create_trial()
    open_trial(page, tid)
    expect(page.locator(".mc-dock__id")).to_have_text(tid, timeout=15000)
    seen = fail_once(page, r"/api/trials/[^/]+/step$", "POST")
    page.get_by_role("button", name="+1 week").click()
    # the step lands after the retry: the headline leaves "Setup before day 1" for "Day N of 90"
    expect(page.get_by_role("heading", name=re.compile(r"^Day \d+ of "))).to_be_visible(timeout=20000)
    assert seen["failed"] == 1 and seen["passed"] == 1
    assert stored_id(page) == tid


# ------------------------------------------------------------------ (b) trial truly gone
def test_persistent_trial_not_found_shows_lost_state_and_stops_polling(page: Page):
    tid = create_trial()
    hits: list[str] = []

    def gone(route: Route) -> None:
        hits.append(route.request.url)
        route.fulfill(status=404, content_type="application/json", body=json.dumps({"detail": "trial not found"}))

    page.route(re.compile(r"/api/trials/[^/?]+/.*"), gone)
    open_trial(page, tid)
    expect(page.get_by_text("This trial is no longer on the server", exact=False)).to_be_visible(timeout=15000)
    # it re-checked before giving up, and the id is kept until the person chooses to start again
    assert any(u.endswith("/state") for u in hits)
    assert stored_id(page) == tid

    # polling has stopped: no further trial requests while the lost state is showing
    n = len(hits)
    page.wait_for_timeout(4000)
    assert len(hits) == n, hits[n:]

    page.get_by_role("button", name="Start a new trial").click()
    expect(page.get_by_text("This trial is no longer on the server", exact=False)).to_have_count(0)
    assert stored_id(page) is None
    assert page.url.rstrip("/") == APP


# ------------------------------------------------------------------ (c) refresh reattaches
def test_refresh_mid_trial_reattaches_to_the_same_trial(page: Page):
    tid = create_trial()
    open_trial(page, tid)
    expect(page.locator(".mc-dock__id")).to_have_text(tid, timeout=15000)
    page.get_by_role("button", name="+1 week").click()
    heading = page.get_by_role("heading", name=re.compile(r"^Day \d+ of"))
    expect(heading).to_be_visible(timeout=20000)
    expect(page.get_by_role("button", name="+1 week")).to_be_enabled(timeout=20000)
    label = heading.get_attribute("aria-label")
    page.reload()
    expect(page.locator(".mc-dock__id")).to_have_text(tid, timeout=15000)
    expect(page.get_by_role("heading", name=label)).to_be_visible()
    assert stored_id(page) == tid
    # a deep link in a second tab reattaches too
    other = page.context.new_page()
    other.goto(APP + "/dosing")
    other.goto(APP + "/")
    expect(other.locator(".mc-dock__id")).to_have_text(tid, timeout=15000)
    other.close()
