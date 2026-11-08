import json, sys
from playwright.sync_api import sync_playwright
OUT="/Users/dannybud/Desktop/unblind/.claude/worktrees/visuals/docs/testing/visuals/before"
BASE="http://127.0.0.1:5602"
rep=json.load(open(__import__("pathlib").Path(__file__).with_name("studio_report_NCT03866174.json")))
seed=json.dumps([{"id":"audit1","input":"NCT03866174","title":rep["title"],"createdAt":"2026-11-08T10:00:00.000Z","report":rep}])
SETTINGS=[("1440-light",dict(viewport={"width":1440,"height":900},color_scheme="light"),"light"),
          ("1440-dark",dict(viewport={"width":1440,"height":900},color_scheme="dark"),"dark"),
          ("390",dict(viewport={"width":390,"height":844},color_scheme="light",device_scale_factor=2,is_mobile=True,has_touch=True),"light")]
TARGETS=[("effect-forest","figure.studio-chart"),
         ("effect-readout","section[aria-labelledby=st-effect]"),
         ("blinding-meter","section[aria-labelledby=st-blinding]"),
         ("source-facts","section[aria-labelledby=st-facts]"),
         ("design-fixes","section[aria-labelledby=st-fixes]"),
         ("studio-mode-badge",".studio-form__meta")]
with sync_playwright() as p:
    b=p.chromium.launch()
    for tag,kw,theme in SETTINGS:
        ctx=b.new_context(**kw)
        ctx.add_init_script(f"try{{localStorage.setItem('parallax.analyses.v1',{json.dumps(seed)});localStorage.setItem('unblind.theme','{theme}')}}catch(e){{}}")
        pg=ctx.new_page()
        pg.goto(BASE+"/studio?a=audit1"); pg.wait_for_selector("figure.studio-chart",timeout=20000); pg.wait_for_timeout(800)
        for cid,sel in TARGETS:
            el=pg.locator(sel).first
            if el.count(): el.scroll_into_view_if_needed(); el.screenshot(path=f"{OUT}/{cid}-{tag}.png")
            else: print("missing",cid,tag)
        pg.screenshot(path=f"{OUT}/studio-report-page-{tag}.png", full_page=True)
        # tooltip check: hover dot
        print(tag,"svg aria:",pg.locator("figure.studio-chart svg").get_attribute("aria-label"))
        print(tag,"title elems in svg:",pg.locator("figure.studio-chart svg title").count())
        print(tag,"html data-theme:",pg.evaluate("document.documentElement.getAttribute('data-theme')"))
        # fact drawer audit badge
        pg.locator(".studio-fact").first.click(); pg.wait_for_timeout(500)
        d=pg.locator(".studio-drawer").first
        if d.count(): d.screenshot(timeout=5000,path=f"{OUT}/fact-drawer-{tag}.png")
        pg.keyboard.press("Escape")
        pg.goto(BASE+"/"); pg.wait_for_timeout(1000)
        pg.screenshot(path=f"{OUT}/home-page-{tag}.png", full_page=True)
        ctx.close()
    # live run progress (1440 light) to confirm UI path works
    ctx=b.new_context(viewport={"width":1440,"height":900}); pg=ctx.new_page()
    pg.goto(BASE+"/studio"); pg.fill("#studio-input","NCT03866174"); pg.click("button.studio-run")
    pg.wait_for_selector(".studio-progress",timeout=10000); pg.wait_for_timeout(11000)
    pg.locator(".studio-progress").screenshot(path=f"{OUT}/progress-steps-1440-light.png")
    pg.wait_for_selector("figure.studio-chart",timeout=180000); print("live run ok")
    b.close()
