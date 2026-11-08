"""After shots for the Studio charts (Builder STUDIO). Same file names as shoot_studio.py, written to after/.
Run against a local stack: API on 8712, Vite on 5712 (see docs/visuals-spec.md)."""
import json, pathlib, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/testing/visuals/after"
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5712"
rep = json.load(open(pathlib.Path(__file__).with_name("studio_report_NCT03866174.json")))
seed = json.dumps([{"id": "audit1", "input": "NCT03866174", "title": rep["title"], "createdAt": "2026-11-08T10:00:00.000Z", "report": rep}])
SETTINGS = [("1440-light", dict(viewport={"width": 1440, "height": 900}, color_scheme="light"), "light"),
            ("1440-dark", dict(viewport={"width": 1440, "height": 900}, color_scheme="dark"), "dark"),
            ("390", dict(viewport={"width": 390, "height": 844}, color_scheme="light", device_scale_factor=2, is_mobile=True, has_touch=True), "light")]
TARGETS = [("effect-forest", "figure[data-chart=effect-forest]"),
           ("effect-readout", "section[aria-labelledby=st-effect] .st-tiles"),
           ("blinding-meter", "section[aria-labelledby=st-blinding]"),
           ("design-fixes", "section[aria-labelledby=st-fixes]")]
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    for tag, kw, theme in SETTINGS:
        ctx = b.new_context(**kw)
        ctx.add_init_script(f"try{{localStorage.setItem('parallax.analyses.v1',{json.dumps(seed)});localStorage.setItem('unblind.theme','{theme}')}}catch(e){{}}")
        pg = ctx.new_page()
        pg.goto(BASE + "/studio?a=audit1")
        pg.wait_for_selector("figure[data-chart=effect-forest]", timeout=20000)
        pg.wait_for_timeout(800)
        for cid, sel in TARGETS:
            el = pg.locator(sel).first
            if el.count():
                el.scroll_into_view_if_needed()
                pg.wait_for_timeout(200)
                el.screenshot(path=str(OUT / f"{cid}-{tag}.png"))
            else:
                print("missing", cid, tag)
        sw = pg.evaluate("document.documentElement.scrollWidth")
        print(tag, "scrollWidth", sw, "aria:", pg.locator("figure[data-chart=effect-forest] [role=img]").first.get_attribute("aria-label"))
        ctx.close()
    b.close()
