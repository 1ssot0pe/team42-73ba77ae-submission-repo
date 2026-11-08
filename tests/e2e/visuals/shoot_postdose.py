"""After shots for the POSTDOSE charts (effect-estimates, madrs-by-week, report-rater-accuracy-site).

Needs the API on 8714 and vite on 5714 (see docs/visuals-spec.md). Creates a psilocybin trial (seed 42, 500
applicants, auto-approve), drives it to day 90 unless a trial id is given, then shoots each chart at 1440 light,
1440 dark and 390. Usage: python tests/e2e/visuals/shoot_postdose.py [trial_id]
"""
import json, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/testing/visuals/after"
API = "http://127.0.0.1:8714/api"
BASE = "http://127.0.0.1:5714"


def call(path, body=None, method="POST"):
    r = urllib.request.Request(API + path, data=json.dumps(body).encode() if body is not None else None,
                               method=method, headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=600))


def make_trial():
    s = call("/trials", {"example": "example_psilocybin_trd.md", "seed": 42, "n_applicants": 500, "auto_approve": True})
    tid = s["trial_id"]
    while s["day"] < 90:
        s = call(f"/trials/{tid}/step", {"days": max(1, min(30, 90 - max(s["day"], 0)))})["state"]
    return tid


tid = sys.argv[1] if len(sys.argv) > 1 else make_trial()
print("trial", tid)
proj = [{"id": "p-vis", "name": "Psilocybin visuals", "createdAt": "2026-11-08T10:00:00.000Z",
         "updatedAt": "2026-11-08T10:00:00.000Z", "template": "psilocybin", "draft": "", "trialId": tid, "status": "running"}]
SETTINGS = [("1440-light", dict(viewport={"width": 1440, "height": 900}, color_scheme="light"), "light"),
            ("1440-dark", dict(viewport={"width": 1440, "height": 900}, color_scheme="dark"), "dark"),
            ("390", dict(viewport={"width": 390, "height": 844}, color_scheme="light", device_scale_factor=2,
                         is_mobile=True, has_touch=True), "light")]
CHARTS = ["effect-estimates", "madrs-by-week", "report-rater-accuracy-site"]

with sync_playwright() as p:
    b = p.chromium.launch()
    for tag, kw, theme in SETTINGS:
        ctx = b.new_context(**kw)
        ctx.add_init_script(f"try{{localStorage.setItem('parallax.projects.v1',{json.dumps(json.dumps(proj))});"
                            f"localStorage.setItem('unblind.theme','{theme}')}}catch(e){{}}")
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/trials/p-vis/follow-up")
        pg.wait_for_selector("figure[data-chart=effect-estimates] svg", timeout=30000)
        pg.wait_for_timeout(1200)
        key = pg.locator("figure[data-chart=effect-estimates]").first
        key.scroll_into_view_if_needed()
        key.screenshot(path=str(OUT / f"followup-key-chart-{tag}.png"))
        pg.get_by_role("button", name="View all charts").first.click()
        pg.wait_for_selector("[role=dialog] figure[data-chart=report-rater-accuracy-site] svg", timeout=20000)
        pg.wait_for_timeout(1500)
        for cid in CHARTS:
            el = pg.locator(f"[role=dialog] figure[data-chart={cid}]").first
            if not el.count():
                print("missing", cid, tag); continue
            el.scroll_into_view_if_needed()
            pg.wait_for_timeout(200)
            path = OUT / f"{cid}-{tag}.png"
            el.screenshot(path=str(path))
            size = path.stat().st_size
            print(tag, cid, f"{size // 1024} KB", "aria:", (el.locator("[role=img]").first.get_attribute("aria-label") or "")[:90])
            if size > 400 * 1024:
                print("  WARNING over 400 KB")
        sw = pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        print(tag, "scrollWidth/innerWidth", sw, "page errors", errors[:3])
        ctx.close()
    b.close()
