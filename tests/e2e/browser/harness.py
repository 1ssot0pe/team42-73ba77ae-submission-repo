"""Shared helpers for the Parallax browser journeys (Python Playwright, Chromium).

Every journey gets a fresh browser context (fresh localStorage), and records:
  console errors and uncaught page errors, failed network requests (status, URL, body, X-RR-Backend),
  every toast the app showed, screenshots at failure points and per-step timings.

Nothing here is specific to the local stack: point --base-url at the vite dev server (local) or at a
deployment such as https://parallax-two-tau.vercel.app and the same journeys run.
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from playwright.sync_api import Browser, Locator, Page

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SHOTS = REPO / "docs" / "testing" / "screenshots"
RESULTS = HERE / "results"

REVIEWER = "QA Tester"
EM_DASH = "—"

# Records every toast the app shows (they vanish after 4 s), so journeys can assert on them later.
TOAST_SPY = """
(() => {
  window.__toasts = [];
  const seen = new WeakSet();
  const scan = () => document.querySelectorAll('.toast').forEach(t => {
    if (seen.has(t)) return; seen.add(t);
    window.__toasts.push({t: Date.now(), cls: t.className, text: (t.innerText || '').trim()});
  });
  new MutationObserver(scan).observe(document, {subtree: true, childList: true});
})();
"""


class JourneyAbort(Exception):
    """Raised when a journey cannot continue (for example the app lost the trial)."""


class Journey:
    def __init__(self, browser: Browser, jid: str, title: str, base_url: str, env: str, shot_prefix: str,
                 viewport=(1440, 900), color_scheme: str = "light", timeout_ms: int = 20000):
        self.browser = browser
        self.jid, self.title, self.base_url, self.env = jid, title, base_url.rstrip("/"), env
        self.shot_prefix = shot_prefix
        self.context = browser.new_context(base_url=self.base_url, viewport={"width": viewport[0], "height": viewport[1]},
                                           color_scheme=color_scheme, reduced_motion="reduce")
        self.context.set_default_timeout(timeout_ms)
        self.context.add_init_script(TOAST_SPY)
        # Protected Vercel previews: PARALLAX_BYPASS_FILE names a file holding the protection-bypass secret.
        # The header goes only to the deployment's own origin (not to Google Fonts, where a custom
        # header would trigger a CORS preflight). The secret is never logged.
        bypass_file = os.environ.get("PARALLAX_BYPASS_FILE")
        if bypass_file:
            secret = Path(bypass_file).read_text().strip()
            self.context.route(f"{self.base_url}/**", lambda route: route.continue_(
                headers={**route.request.headers, "x-vercel-protection-bypass": secret}))
        self.console_errors: List[Dict[str, Any]] = []
        self.network_failures: List[Dict[str, Any]] = []
        self.failures: List[Dict[str, Any]] = []
        self.notes: List[str] = []
        self.timings: Dict[str, float] = {}
        self.shots: List[str] = []
        self.api_calls = 0
        self._n = 0
        self.t0 = time.time()
        self.page = self.new_page()

    # ------------------------------------------------------------ wiring
    def new_page(self) -> Page:
        p = self.context.new_page()
        p.on("console", lambda m: m.type == "error" and self.console_errors.append(
            {"t": round(time.time() - self.t0, 2), "text": m.text[:500], "url": p.url}))
        p.on("pageerror", lambda e: self.console_errors.append(
            {"t": round(time.time() - self.t0, 2), "text": f"pageerror: {e}"[:500], "url": p.url}))
        p.on("response", self._on_response)
        p.on("requestfailed", lambda r: self.network_failures.append(
            {"t": round(time.time() - self.t0, 2), "method": r.method, "url": r.url, "status": None,
             "error": r.failure, "body": None}))
        return p

    def _on_response(self, r):
        if "/api/" in r.url:
            self.api_calls += 1
        if r.status < 400:
            return
        try:
            body = r.text()[:400]
        except Exception as e:  # body gone after navigation
            body = f"<unavailable: {e}>"
        self.network_failures.append({"t": round(time.time() - self.t0, 2), "method": r.request.method, "url": r.url,
                                      "status": r.status, "backend": r.headers.get("x-rr-backend"), "body": body})

    # ------------------------------------------------------------ evidence
    def shot(self, label: str = "", full_page: bool = True, page: Optional[Page] = None) -> str:
        self._n += 1
        SHOTS.mkdir(parents=True, exist_ok=True)
        path = SHOTS / f"{self.shot_prefix}-{self.jid}-{self._n}.png"
        try:
            (page or self.page).screenshot(path=str(path), full_page=full_page)
        except Exception as e:
            self.notes.append(f"screenshot failed: {e}")
            return ""
        rel = str(path.relative_to(REPO))
        self.shots.append(f"{rel} ({label})" if label else rel)
        return rel

    def check(self, ok: bool, msg: str, shot: bool = True, page: Optional[Page] = None) -> bool:
        if not ok:
            path = self.shot(msg[:40], page=page) if shot else ""
            self.failures.append({"t": round(time.time() - self.t0, 2), "msg": msg, "shot": path, "url": (page or self.page).url})
            print(f"    FAIL {self.jid}: {msg}", flush=True)
        return ok

    def note(self, msg: str) -> None:
        self.notes.append(msg)
        print(f"    note {self.jid}: {msg}", flush=True)

    @contextlib.contextmanager
    def timed(self, name: str):
        t = time.time()
        try:
            yield
        finally:
            self.timings[name] = round(time.time() - t, 2)

    def toasts(self, page: Optional[Page] = None) -> List[str]:
        try:
            return [x["text"] for x in (page or self.page).evaluate("window.__toasts || []")]
        except Exception:
            return []

    def result(self, error: Optional[str] = None) -> Dict[str, Any]:
        api_fail = [n for n in self.network_failures if "/api/" in n["url"]]
        return {
            "id": self.jid, "title": self.title, "env": self.env, "base_url": self.base_url,
            "passed": not self.failures and error is None, "error": error,
            "duration_s": round(time.time() - self.t0, 1), "timings": self.timings,
            "failures": self.failures, "notes": self.notes,
            "console_errors": self.console_errors[:60], "console_error_count": len(self.console_errors),
            "network_failures": api_fail[:60] + [n for n in self.network_failures if n not in api_fail][:20],
            "network_failure_count": len(self.network_failures), "api_calls": self.api_calls,
            "toasts": self.toasts()[-40:], "shots": self.shots,
        }

    def close(self):
        with contextlib.suppress(Exception):
            self.context.close()


def run_journey(browser: Browser, mod, base_url: str, env: str, prefix: str, **kw) -> Dict[str, Any]:
    """Run one journey module (it exposes ID, TITLE and run(j)). Uncaught errors become a failure with a screenshot."""
    opts = dict(getattr(mod, "CONTEXT", {}))
    opts.update(kw)
    j = Journey(browser, mod.ID, mod.TITLE, base_url, env, prefix, **opts)
    err = None
    print(f"== {mod.ID} {mod.TITLE} [{env}]", flush=True)
    try:
        mod.run(j)
    except JourneyAbort as e:
        err = f"aborted: {e}"
        j.check(False, err)
    except Exception as e:  # noqa: BLE001
        err = f"{type(e).__name__}: {str(e).splitlines()[0][:300]}"
        j.check(False, f"exception: {err}")
        j.notes.append(traceback.format_exc()[-1500:])
    res = j.result(err)
    j.close()
    print(f"   -> {'PASS' if res['passed'] else 'FAIL'} in {res['duration_s']}s, {len(res['failures'])} failures, "
          f"{res['console_error_count']} console errors, {res['network_failure_count']} network failures", flush=True)
    return res


# ================================================================ app helpers
def trial_id(page: Page) -> Optional[str]:
    return page.evaluate("localStorage.getItem('unblind.trialId')")


def api_json(j: Journey, path: str, method: str = "GET", body: Any = None, page: Optional[Page] = None) -> Any:
    """Call the API the way the app does (same origin, so it goes through whatever the app goes through)."""
    p = page or j.page
    r = p.request.fetch(j.base_url + path, method=method, data=json.dumps(body) if body is not None else None,
                        headers={"content-type": "application/json"})
    try:
        data = r.json()
    except Exception:
        data = r.text()
    return {"status": r.status, "data": data, "backend": r.headers.get("x-rr-backend")}


def fresh(j: Journey, path: str = "/") -> None:
    """Open the app with empty localStorage."""
    j.page.goto(path)
    j.page.evaluate("localStorage.clear()")
    j.page.goto(path)


def on_start_page(page: Page) -> bool:
    return page.get_by_role("heading", name="Start a trial").is_visible()


def running(page: Page) -> bool:
    return page.locator(".mc-dock").is_visible()


def create_trial(j: Journey, example: Optional[str] = "psilocybin", text: Optional[str] = None,
                 auto: bool = False, settle_s: float = 2.0) -> Optional[str]:
    """From the Start a trial page: pick an example (substring of the tab label) or paste text, then Create trial.

    Returns the trial id when the Mission control dock is still showing settle_s after creation, else None.
    """
    p = j.page
    if not on_start_page(p):
        p.goto("/")
        p.get_by_role("heading", name="Start a trial").wait_for()
    create = p.get_by_role("button", name="Create trial")
    if example:
        tab = p.locator(".tabs .tab", has_text=re.compile(example, re.I)).first
        tab.wait_for()
        tab.click()
        p.wait_for_function("document.querySelector('#mc-protocol').value.length > 50")
    if text is not None:
        p.locator("#mc-protocol").fill(text)
    if auto:
        p.get_by_label("Auto-approve (demo fast-forward)").check()
    p.wait_for_function("!document.querySelector('.mc-start__create')?.disabled")
    with j.timed("create_trial"):
        create.click()
        try:
            p.locator(".mc-dock").wait_for(timeout=30000)
        except Exception:
            j.check(False, "Create trial did not reach the running Mission control view")
            return None
    p.wait_for_timeout(int(settle_s * 1000))
    tid = trial_id(p)
    if not running(p):
        j.check(False, f"Trial {tid} vanished right after creation (page fell back to 'Start a trial')")
        return None
    return tid


def ensure_running(j: Journey, where: str) -> None:
    """Abort the journey if the app has dropped the trial (the stateless-backend symptom)."""
    if on_start_page(j.page) or (j.page.locator(".mc-dock").count() == 0 and j.page.url.rstrip("/") == j.base_url):
        raise JourneyAbort(f"trial lost {where}: Mission control is back on 'Start a trial'")


def slips(page: Page, title: Optional[str] = None) -> Locator:
    loc = page.locator("article.slip")
    if title:
        loc = loc.filter(has=page.locator(".slip__title", has_text=re.compile(title, re.I)))
    return loc


def wait_slip(j: Journey, title: str, timeout: int = 20000) -> bool:
    try:
        slips(j.page, title).first.wait_for(timeout=timeout)
        return True
    except Exception:
        return False


def decide(j: Journey, title: str, decision: str = "approved", reviewer: str = REVIEWER, comment: str = "",
           page: Optional[Page] = None) -> Optional[str]:
    """Sign the first slip whose title matches. Returns None on success, else the error text shown."""
    p = page or j.page
    s = slips(p, title).first
    s.wait_for()
    s.scroll_into_view_if_needed()
    sid = s.locator("input[id$='-reviewer']").get_attribute("id")
    s.locator("input[id$='-reviewer']").fill(reviewer)
    if comment:
        s.locator("input[id$='-comment']").fill(comment)
    with j.timed(f"decide:{title[:30]}"):
        s.get_by_role("button", name="Approve" if decision == "approved" else "Reject").click()
        # success: the slip turns into a stamp (the input disappears); failure: .slip__error appears
        try:
            p.wait_for_function(
                """(id) => { const i = document.getElementById(id);
                   if (!i) return 'ok';
                   const e = i.closest('article')?.querySelector('.slip__error');
                   return e ? 'err:' + e.innerText : false; }""", arg=sid, timeout=15000)
        except Exception:
            return "no response within 15 s"
    err = p.evaluate("""(id) => { const i = document.getElementById(id); if (!i) return null;
        const e = i.closest('article')?.querySelector('.slip__error'); return e ? e.innerText : null; }""", sid)
    return err


def dock_button(page: Page, name: str) -> Locator:
    return page.locator(".mc-dock").get_by_role("button", name=re.compile(f"^{name}$"))


def nav_day(page: Page) -> Optional[str]:
    loc = page.locator(".nav__day")
    return loc.inner_text() if loc.count() else None


def day_number(page: Page) -> Optional[int]:
    d = nav_day(page)
    if not d:
        return None
    m = re.search(r"D([+-]?\d+)", d.replace("−", "-"))
    if m:
        return int(m.group(1))
    m = re.search(r"(-?\d+)\s*/", d)
    return int(m.group(1)) if m else None


def play(j: Journey, stop_when: Optional[Callable[[], bool]] = None, timeout_s: float = 240) -> str:
    """Press Play and wait until the loop stops by itself, or stop_when() is true (then press Pause).

    Returns "stopped" (loop ended: blocked, closed or error), "condition" or "timeout".
    """
    p = j.page
    btn = dock_button(p, "Play")
    # After a decision the app refreshes state before enabling Play: ~0.06 s locally, ~0.3 s on Vercel.
    # Give it up to 8 s rather than checking once (that raced on the preview).
    t0 = time.time()
    while not btn.is_enabled() and time.time() - t0 < 8:
        p.wait_for_timeout(200)
    if not btn.is_enabled():
        return "disabled"
    btn.click()
    t = time.time()
    while time.time() - t < timeout_s:
        p.wait_for_timeout(250)
        if not running(p):
            return "lost"
        if stop_when and stop_when():
            pause = dock_button(p, "Pause")
            if pause.count():
                pause.click()
            p.wait_for_timeout(600)
            return "condition"
        if dock_button(p, "Play").count() and not dock_button(p, "Pause").count():
            return "stopped"
    if dock_button(p, "Pause").count():
        dock_button(p, "Pause").click()
    return "timeout"


def heading_text(page: Page) -> str:
    h = page.locator("h1").first
    return h.inner_text() if h.count() else ""


def now_line(page: Page) -> str:
    loc = page.locator(".mc-head__now")
    return loc.inner_text() if loc.count() else ""


# ================================================================ design and copy checks (F)
TEXT_CHECKS_JS = r"""
() => {
  const txt = document.body.innerText;
  const attrs = [];
  document.querySelectorAll('[aria-label],[title],[placeholder],img[alt]').forEach(e => {
    for (const a of ['aria-label','title','placeholder','alt']) { const v = e.getAttribute(a); if (v) attrs.push(v); }
  });
  const all = txt + '\n' + attrs.join('\n') + '\n' + document.title;
  const lines = (re) => all.split('\n').filter(l => re.test(l)).map(l => l.trim()).slice(0, 12);
  const de = document.documentElement;
  // elements that stick out past the viewport (the cause of any horizontal scroll)
  const wide = [];
  if (de.scrollWidth > de.clientWidth) {
    document.querySelectorAll('body *').forEach(e => {
      const r = e.getBoundingClientRect();
      if (r.width && r.right > de.clientWidth + 1 && getComputedStyle(e).position !== 'fixed') {
        wide.push((e.className && typeof e.className === 'string' ? '.' + e.className.split(' ').join('.') : e.tagName) + ' right=' + Math.round(r.right));
      }
    });
  }
  return {
    title: document.title,
    em: lines(/—/), unblind: lines(/\bUNBLIND\b/),
    synthetic: /SYNTHETIC/i.test(txt), band: !!document.querySelector('.band'),
    scrollW: de.scrollWidth, clientW: de.clientWidth, wide: wide.slice(0, 8),
    charts: Array.from(document.querySelectorAll('.recharts-wrapper')).length,
  };
}
"""


def copy_checks(j: Journey, where: str, page: Optional[Page] = None, check_scroll: bool = True) -> Dict[str, Any]:
    p = page or j.page
    r = p.evaluate(TEXT_CHECKS_JS)
    j.check(not r["em"], f"[{where}] em dash in UI text: {r['em'][:4]}", page=p)
    j.check(not r["unblind"], f"[{where}] stray 'UNBLIND' in UI text: {r['unblind'][:4]}", shot=False, page=p)
    j.check(r["synthetic"] and r["band"], f"[{where}] no SYNTHETIC label / specimen band", page=p)
    if check_scroll:
        j.check(r["scrollW"] <= r["clientW"], f"[{where}] horizontal scroll: scrollWidth {r['scrollW']} > {r['clientW']}; "
                f"overflowing: {r['wide'][:4]}", page=p)
    return r


# Contrast of text on glass, measured against the real pixels behind it (specimen field and all):
# 1) record each text element's colour and box, 2) make all text transparent and screenshot,
# 3) take the median background pixel under each box and compute the WCAG ratio.
GLASS_TEXT_JS = r"""
() => {
  const out = [];
  document.querySelectorAll('.glass').forEach(g => {
    if (g.closest('[hidden]')) return;
    g.querySelectorAll('*').forEach(e => {
      const own = Array.from(e.childNodes).some(n => n.nodeType === 3 && n.textContent.trim());
      if (!own) return;
      const cs = getComputedStyle(e);
      if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) === 0) return;
      if (e.closest('.visually-hidden')) return;
      const r = e.getBoundingClientRect();
      if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight) return;
      // walk up for the nearest opaque-ish own background (pills have their own fill)
      out.push({text: e.innerText.trim().slice(0, 40), color: cs.color, size: parseFloat(cs.fontSize),
                weight: parseInt(cs.fontWeight), x: r.left, y: r.top, w: r.width, h: r.height,
                glass: (g.className || '').toString().split(' ').filter(c => c && c !== 'glass').join('.')});
    });
  });
  return out;
}
"""


def _lum(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast(a, b) -> float:
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _parse_rgb(s: str):
    nums = [float(x) for x in re.findall(r"[\d.]+", s)]
    return nums[:3], (nums[3] if len(nums) > 3 else 1.0)


def glass_contrast(j: Journey, where: str, min_ratio: float = 4.5, page: Optional[Page] = None) -> List[Dict[str, Any]]:
    """Check text contrast on every visible glass panel. Returns the low-contrast items."""
    import io
    from PIL import Image
    import numpy as np

    p = page or j.page
    items = p.evaluate(GLASS_TEXT_JS)
    if not items:
        return []
    p.add_style_tag(content="* { color: transparent !important; text-shadow: none !important; caret-color: transparent !important; }"
                            " svg { visibility: hidden !important; } .toast-stack { display:none !important; }")
    p.wait_for_timeout(150)
    img = np.asarray(Image.open(io.BytesIO(p.screenshot())).convert("RGB")).astype(float)
    p.evaluate("document.querySelectorAll('style').forEach(s => { if (s.textContent.includes('color: transparent !important')) s.remove(); })")
    dpr = p.evaluate("devicePixelRatio")
    bad = []
    for it in items:
        x0, y0 = int(it["x"] * dpr), int(it["y"] * dpr)
        x1, y1 = int((it["x"] + it["w"]) * dpr), int((it["y"] + it["h"]) * dpr)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(img.shape[1], max(x0 + 1, x1)), min(img.shape[0], max(y0 + 1, y1))
        patch = img[y0:y1, x0:x1].reshape(-1, 3)
        if not len(patch):
            continue
        bg = np.median(patch, axis=0)
        rgb, alpha = _parse_rgb(it["color"])
        fg = [alpha * c + (1 - alpha) * b for c, b in zip(rgb, bg)]
        ratio = contrast(fg, bg)
        large = it["size"] >= 24 or (it["size"] >= 18.66 and it["weight"] >= 700)
        need = 3.0 if large else min_ratio
        if ratio < need:
            bad.append({**{k: it[k] for k in ("text", "color", "size", "glass")}, "bg": [int(c) for c in bg],
                        "ratio": round(ratio, 2), "need": need})
    j.check(not bad, f"[{where}] {len(bad)} low-contrast text items on glass: " +
            "; ".join(f"'{b['text']}' {b['ratio']}:1 in .{b['glass']}" for b in bad[:6]), page=p)
    return bad


# ================================================================ CLI
def parse_args(default_prefix: str = "local"):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://127.0.0.1:5173", help="app origin (vite dev server or a deployment)")
    ap.add_argument("--env", default="local-proxy", help="label stored in the results (local-proxy, local-single, prod)")
    ap.add_argument("--prefix", default=default_prefix, help="screenshot file prefix: <prefix>-<journey>-<n>.png")
    ap.add_argument("--only", default="", help="comma list of journeys, e.g. J1,J3,F,G")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--out", default="", help="results JSON path (default tests/e2e/browser/results/<env>.json)")
    return ap.parse_args()
