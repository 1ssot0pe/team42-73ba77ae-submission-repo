"""Frontend resilience regression test (Python Playwright, Chromium).

Starts the real backend on 127.0.0.1:8201 and vite on 127.0.0.1:5199, then uses page.route to inject
failures in front of the backend:

  (a) one 503 on a state call and one on a step call must not lose the trial; both succeed after a retry
  (b) a persistent "trial not found" 404 shows the TrialLost state, stops polling, and its button
      clears the stored trial id and goes to the start page
  (c) a refresh mid-trial reattaches to the same trial id
  (d) N-1: after every pending approval is signed, the page shows the server's pending count without a reload

The redesigned UI opens a trial inside a project workspace (/trials/<projectId>/<stage>). Projects live in
localStorage ("parallax.projects.v1"), so each test seeds one project pointing at a trial made through the API,
as a returning visitor would have it. The trial id is read from the nav's Developer panel (the old dock id).

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
    env = dict(os.environ, UNBLIND_TRIALS_DIR=os.path.join(logs, "trials"),
               UNBLIND_STORE_DIR=os.path.join(logs, "store"))
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


PROJECTS_KEY = "parallax.projects.v1"
DEV_KEY = "parallax.developer"


def seed(page: Page, trial_id: str) -> str:
    """On an app page: remember a project for this trial (and the trial id) the way the app stores them.
    Turns on Developer details so the nav panel shows the trial id. Returns the project id."""
    pid = "p-" + trial_id.lower().replace("-", "")[-8:]
    page.evaluate("""([pk, tk, dk, pid, tid]) => {
        const now = new Date().toISOString();
        const items = JSON.parse(localStorage.getItem(pk) || "[]").filter(p => p.id !== pid);
        items.push({id: pid, name: "Resilience " + tid, createdAt: now, updatedAt: now, template: "psilocybin",
                    draft: "", trialId: tid, status: "running"});
        localStorage.setItem(pk, JSON.stringify(items));
        localStorage.setItem(tk, tid);
        localStorage.setItem(dk, "1");
    }""", [PROJECTS_KEY, TRIAL_KEY, DEV_KEY, pid, trial_id])
    return pid


def workspace(pid: str, stage: str = "") -> str:
    return f"{APP}/trials/{pid}" + (f"/{stage}" if stage else "")


def open_trial(page: Page, trial_id: str, stage: str = "") -> str:
    """Load the trial's project workspace as a returning visitor would. Returns the project id."""
    page.goto(APP + "/")
    pid = seed(page, trial_id)
    page.goto(workspace(pid, stage))
    return pid


def expect_trial(page: Page, trial_id: str, timeout: int = 15000) -> None:
    """The workspace has loaded this trial: its stage and time line shows (only once the trial state is in),
    and the nav's Developer panel names the trial id (what the old dock's id showed)."""
    expect(page.locator(".ws__meta .num")).to_be_visible(timeout=timeout)
    page.get_by_role("button", name="More options").click()
    expect(page.locator(".t-id")).to_have_text(trial_id, timeout=timeout)
    page.keyboard.press("Escape")


def day_line(page: Page):
    """The workspace's trial time, e.g. "Dosing · Day 7 of 90" (the old "Day N of 90" headline)."""
    return page.locator(".ws__meta .num").filter(has_text=re.compile(r"Day \d+ of \d+"))


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
    pid = seed(page, tid)
    # fail the first two state loads (React StrictMode mounts the provider twice in dev)
    seen = fail_once(page, r"/api/trials/[^/]+/state$", "GET", times=2)
    page.goto(workspace(pid))
    # the trial loads after the retry: the workspace shows its id, and nothing was forgotten
    expect_trial(page, tid)
    assert seen["failed"] >= 1 and seen["passed"] >= 1
    assert stored_id(page) == tid


def test_one_503_on_step_retries_and_advances(page: Page):
    tid = create_trial()
    open_trial(page, tid)
    expect_trial(page, tid)
    seen = fail_once(page, r"/api/trials/[^/]+/step$", "POST")
    page.get_by_role("button", name="Advance a week").click()
    # the step lands after the retry: the trial time leaves "Before dosing" for "Day N of 90"
    expect(day_line(page)).to_be_visible(timeout=20000)
    assert seen["failed"] == 1 and seen["passed"] == 1
    assert stored_id(page) == tid



def test_four_502s_on_step_still_advance(page: Page):
    """NEW-1: during a backend outage one step can hit 502 several times in a row. 502/503 mean the
    function never ran, so the client keeps retrying (up to 5 attempts) instead of stopping Play."""
    tid = create_trial()
    open_trial(page, tid)
    expect_trial(page, tid)
    seen = fail_once(page, r"/api/trials/[^/]+/step$", "POST", status=502, times=4)
    page.get_by_role("button", name="Advance a week").click()
    expect(day_line(page)).to_be_visible(timeout=30000)
    assert seen["failed"] == 4 and seen["passed"] == 1
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
    # the TrialLost screen (a <main role="alert">) replaces the workspace; stage panels may show the same
    # sentence as their own fetch error before it, so look for it in TrialLost only
    lost = page.locator("main[role='alert']").get_by_text("This trial is no longer on the server", exact=False)
    expect(lost).to_be_visible(timeout=15000)
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
    pid = open_trial(page, tid)
    expect_trial(page, tid)
    page.get_by_role("button", name="Advance a week").click()
    line = day_line(page)
    expect(line).to_be_visible(timeout=20000)
    expect(page.get_by_role("button", name="Advance a week")).to_be_enabled(timeout=20000)
    label = line.inner_text()
    url = page.url
    page.reload()
    expect_trial(page, tid)
    expect(page.locator(".ws__meta .num")).to_have_text(label)
    assert page.url == url
    assert stored_id(page) == tid
    # a deep link in a second tab reattaches too (an old /dosing link lands on /trials, then the project)
    other = page.context.new_page()
    other.goto(APP + "/dosing")
    expect(other).to_have_url(re.compile(r"/trials$"))
    other.goto(workspace(pid))
    expect_trial(other, tid)
    expect(other.locator(".ws__meta .num")).to_have_text(label)
    other.close()


# ------------------------------------------------------------------ (d) stale refresh after an approval (N-1)
def test_state_is_fresh_after_approvals_while_a_slow_refresh_is_in_flight(page: Page):
    """N-1 (seen on the Vercel preview): after the last approval the header kept "N to sign" and Play stayed
    disabled, while the server had nothing pending. A refresh that started before an approval was saved was
    reused for the refresh after it, so the page kept the old state. Here every /state response is held for
    4 s (with data from when it was requested), which makes that overlap certain.

    In the redesigned workspace the pending approvals before dosing are on the Design review stage: the
    protocol fixes in one panel ("Approve selected": one decision per fix, then the last state is adopted)
    and the clinician shortlist as a slip (decide, then refresh). Fixes are signed first because approving
    the shortlist starts dosing, which expires unsigned fixes. The approvals render without waiting for the
    trial state, so a person can sign them all while the page's first /state is still in flight, which is
    the overlap here. The pending count shows in the workspace clock's watch line, "Waiting for a human:
    N decisions to sign in this stage." (the old "N to sign" pill)."""
    body = json.dumps({"example": "example_psilocybin_trd.md", "n_applicants": 60, "seed": 7,
                       "auto_approve": False}).encode()
    req = urllib.request.Request(f"{API}/api/trials", data=body, method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        tid = json.load(r)["trial_id"]
    with urllib.request.urlopen(f"{API}/api/trials/{tid}/approvals", timeout=30) as r:
        assert len(json.load(r)) >= 2, "needs at least two pending approvals"

    # In the page: a /state response is received at once (data as of the request) but handed to the app
    # 4 s later, without blocking other requests. (A Playwright route handler can't do this: it runs
    # handlers one at a time, so later responses would be fetched late and come back fresh.)
    page.add_init_script("""
      window.__slowState = true;
      const realFetch = window.fetch.bind(window);
      window.fetch = async (input, init) => {
        const res = await realFetch(input, init);
        const url = typeof input === "string" ? input : input.url;
        if (window.__slowState && /\\/api\\/trials\\/[^/]+\\/state$/.test(url)) await new Promise(r => setTimeout(r, 4000));
        return res;
      };
    """)
    open_trial(page, tid, "design-review")
    slips = page.locator("article.slip").filter(has=page.locator("input[id$='-reviewer']"))
    fixes = page.get_by_role("button", name="Approve selected")
    expect(fixes.or_(slips).first).to_be_visible(timeout=15000)
    signed = 0
    for _ in range(12):                          # sign everything pending, without waiting for refreshes
        if fixes.count() > 0 and fixes.is_visible():
            page.locator("#rv-fixes-reviewer").fill("Test Reviewer")
            n = page.locator("input.rv-check:checked").count()
            fixes.click()
            expect(page.locator(".rv-progress")).to_contain_text("approved", timeout=15000)
            signed += n
        elif slips.count() > 0:
            s = slips.first
            s.scroll_into_view_if_needed()
            s.locator("input[id$='-reviewer']").fill("Test Reviewer")
            s.get_by_role("button", name="Approve").click()
            signed += 1
        else:
            break
        page.wait_for_timeout(300)
    assert signed >= 2
    expect_trial(page, tid)
    with urllib.request.urlopen(f"{API}/api/trials/{tid}/state", timeout=30) as r:
        server = json.load(r)
    to_sign = page.locator(".clock__line").filter(has_text=re.compile(r"\b[1-9]\d* decisions? to sign\b"))
    page.wait_for_timeout(9000)                  # past every held /state response
    if server["pending_approvals"] == 0:
        # the page must catch up without a reload: no "N decisions to sign" line, and the clock can advance
        expect(to_sign).to_have_count(0, timeout=12000)
        if not server.get("blocked"):
            expect(page.get_by_role("button", name="Advance a day")).to_be_enabled(timeout=12000)
    else:
        n = server["pending_approvals"]
        expect(page.get_by_text(f"{n} {'decision' if n == 1 else 'decisions'} to sign", exact=False).first).to_be_visible(timeout=12000)
