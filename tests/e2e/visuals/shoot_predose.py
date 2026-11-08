"""After shots for the PREDOSE charts (risk-scale, screening-funnel, version-history).

Needs the API on :8715 and vite on :5715 (see docs/visuals-spec.md). Creates two psilocybin trials
(seed 42, 500 applicants, manual approvals): one left at the baseline, one with the five design fixes
and the clinician shortlist approved in the audit's order. Writes element crops at 1440 light,
1440 dark and 390 (2x) to docs/testing/visuals/after/.
"""
import json
import pathlib
import sys
import urllib.request as u

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/testing/visuals/after"
API = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8715/api"
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:5715"
FIXES = ["central_raters", "blinding_questionnaire", "expectancy_measure", "alternative_control", "stratify_prior_use"]


def req(method, path, body=None):
    r = u.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                  headers={"content-type": "application/json"})
    return json.load(u.urlopen(r))


def new_trial():
    return req("POST", "/trials", {"example": "example_psilocybin_trd.md", "n_applicants": 500, "seed": 42,
                                   "auto_approve": False})["trial_id"]


def approve(tid, key):
    rows = req("GET", f"/trials/{tid}/approvals")
    a = next(a for a in rows if (a.get("action") or {}).get("fix") == key or (a.get("action") or {}).get("type") == key)
    req("POST", f"/trials/{tid}/approvals/{a['id']}", {"reviewer": "Dr A. Auditor", "decision": "approved", "comment": "ok"})


base_tid = new_trial()
full_tid = new_trial()
for k in FIXES + ["shortlist"]:
    approve(full_tid, k)


def project(pid, tid):
    now = "2026-11-08T10:00:00.000Z"
    return {"id": pid, "name": f"Psilocybin TRD ({pid})", "createdAt": now, "updatedAt": now, "template": "psilocybin",
            "draft": "", "trialId": tid, "status": "running"}


seed = json.dumps([project("p-after01", full_tid), project("p-base01", base_tid)])
SETTINGS = [("1440-light", dict(viewport={"width": 1440, "height": 900}, color_scheme="light"), "light"),
            ("1440-dark", dict(viewport={"width": 1440, "height": 900}, color_scheme="dark"), "dark"),
            ("390", dict(viewport={"width": 390, "height": 844}, color_scheme="light", device_scale_factor=2,
                         is_mobile=True, has_touch=True), "light")]
SHOTS = [("risk-scale", "p-after01", "design-review", "figure.chart[data-chart=risk-scale]"),
         ("risk-scale-baseline", "p-base01", "design-review", "figure.chart[data-chart=risk-scale]"),
         ("version-history", "p-after01", "design-review", "ledger:Version history"),
         ("screening-funnel", "p-after01", "screening", "figure.chart[data-chart=screening-funnel]"),
         ("screening-funnel-preshortlist", "p-base01", "screening", "figure.chart[data-chart=screening-funnel]")]

OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    for tag, kw, theme in SETTINGS:
        ctx = b.new_context(**kw)
        ctx.add_init_script(f"try{{localStorage.setItem('parallax.projects.v1',{json.dumps(seed)});"
                            f"localStorage.setItem('unblind.theme','{theme}')}}catch(e){{}}")
        pg = ctx.new_page()
        for cid, pid, stage, sel in SHOTS:
            pg.goto(f"{BASE}/trials/{pid}/{stage}")
            if sel.startswith("ledger:"):
                el = pg.locator("section.ledger").filter(has=pg.locator("h3.ledger__title", has_text=sel[7:])).first
            else:
                el = pg.locator(sel).first
            try:
                el.wait_for(timeout=20000)
            except Exception:
                print("missing", cid, tag)
                continue
            pg.wait_for_timeout(700)
            el.scroll_into_view_if_needed()
            # keep the sticky glass nav and stepper off the crop
            pg.add_style_tag(content="header, nav, [class*=glass], [class*=stepper] { visibility: hidden !important; }")
            pg.wait_for_timeout(200)
            path = OUT / f"{cid}-{tag}.png"
            el.screenshot(path=str(path))
            kb = path.stat().st_size // 1024
            print(f"{cid}-{tag}.png {kb} KB" + ("  OVER 400 KB" if kb > 400 else ""))
            if tag == "1440-light" and cid == "risk-scale":
                print("  title:", el.locator("h3").first.inner_text())
                print("  aria:", el.locator("[role=img]").first.get_attribute("aria-label"))
        ctx.close()
    b.close()
print("trials", full_tid, base_tid)
