"""F: design and copy on every page, light and dark, desktop and 390 px.

SYNTHETIC labels (band on every page, tag on every chart), no em dashes, Parallax naming with no stray UNBLIND,
text contrast on glass panels measured against the real pixels behind them, and no horizontal scroll at 390 px.
"""
from harness import JourneyAbort, copy_checks, create_trial, decide, dock_button, fresh, glass_contrast

ID = "F"
TITLE = "Design and copy: SYNTHETIC, em dashes, naming, glass contrast, 390 px"
PAGES = ["/", "/predose", "/portal", "/dosing", "/postdose"]


def charts_tagged(j, where):
    p = j.page
    bad = p.evaluate("""() => Array.from(document.querySelectorAll('.recharts-wrapper')).map(w => {
        let e = w; for (let i = 0; i < 6 && e.parentElement; i++) { e = e.parentElement; if (/SYNTHETIC/i.test(e.innerText)) return null; }
        return (w.closest('[class]')?.className || 'chart') + '';
      }).filter(Boolean)""")
    j.check(not bad, f"[{where}] {len(bad)} chart(s) without a SYNTHETIC tag: {bad[:3]}")


def sweep(j, theme, width):
    p = j.page
    p.set_viewport_size({"width": width, "height": 900})
    p.evaluate(f"localStorage.setItem('unblind.theme', '{theme}')")
    for path in PAGES:
        p.goto(path)
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(1200)
        where = f"{path} {theme} {width}"
        copy_checks(j, where, check_scroll=True)
        charts_tagged(j, where)
        if width > 400:
            glass_contrast(j, where)
        if path == "/portal":
            p.get_by_role("button", name="Apply").click()
            p.wait_for_timeout(2000)
            glass_contrast(j, f"{where} with a result")


def run(j):
    p = j.page
    fresh(j)
    for theme in ("light", "dark"):
        p.evaluate(f"localStorage.setItem('unblind.theme', '{theme}')")
        p.reload()
        p.wait_for_timeout(800)
        copy_checks(j, f"start page {theme}")
        glass_contrast(j, f"start page {theme}")
    p.evaluate("localStorage.removeItem('unblind.theme')")
    p.reload()
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    decide(j, "^Protocol fix.*questionnaire")
    decide(j, "confirm shortlist")
    for _ in range(5):
        dock_button(p, r"\+1 week").click()
        p.wait_for_timeout(900)
    for theme in ("light", "dark"):
        sweep(j, theme, 1440)
    sweep(j, "light", 390)
