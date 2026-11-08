"""J11: refresh mid-trial on every page, a second tab on the same trial, and deep links (with and without a trial)."""
from harness import JourneyAbort, create_trial, decide, dock_button, fresh, nav_day

ID = "J11"
TITLE = "Refresh mid-trial on each page; second tab; deep links"
PAGES = ["/", "/predose", "/portal", "/dosing", "/postdose"]


def chip(p):
    loc = p.locator(".nav__chip")
    return loc.inner_text() if loc.count() else None


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    decide(j, "confirm shortlist")
    for _ in range(2):
        dock_button(p, r"\+1 week").click()
        p.wait_for_timeout(1500)
    day = nav_day(p)
    j.note(f"trial {tid} at {day}")
    for path in PAGES:
        p.goto(path)
        p.wait_for_timeout(1200)
        with j.timed(f"reload:{path}"):
            p.reload()
            p.wait_for_load_state("networkidle")
            p.wait_for_timeout(800)
        j.check(chip(p) == tid, f"[reload {path}] trial chip {chip(p)!r} != {tid}")
        j.check("No trial yet" not in p.evaluate("document.body.innerText"), f"[reload {path}] page says 'No trial yet'")
        j.check(nav_day(p) == day, f"[reload {path}] day changed {day!r} -> {nav_day(p)!r}")

    t2 = j.new_page()
    t2.goto("/")
    t2.wait_for_timeout(1500)
    j.check(chip(t2) == tid, f"[second tab] trial chip {chip(t2)!r} != {tid}", page=t2)
    # advance in tab 2; tab 1 is stale until it refetches (no live sync): record how long
    dock_button(t2, "Next day").click()
    t2.wait_for_timeout(1500)
    d2 = nav_day(t2)
    p.goto("/")
    p.wait_for_timeout(1500)
    j.check(nav_day(p) == d2, f"[second tab] tab 1 shows {nav_day(p)!r} after navigating, tab 2 shows {d2!r}")
    t2.close()

    for path in PAGES[1:]:
        p.goto(path)
        p.wait_for_timeout(1000)
        j.check(p.locator("h1").count() == 1 and chip(p) == tid, f"[deep link {path} with trial] h1/chip missing")
    # deep links in a brand-new browser context (no trial stored)
    ctx = j.browser.new_context(base_url=j.base_url)
    q = ctx.new_page()
    for path in PAGES[1:]:
        r = q.goto(path)
        q.wait_for_timeout(800)
        txt = q.evaluate("document.body.innerText")
        j.check(r is not None and r.status == 200, f"[deep link {path} fresh] HTTP {r.status if r else None}", page=q)
        j.check("No trial yet" in txt, f"[deep link {path} fresh] no 'No trial yet' empty state", page=q)
    r = q.goto("/no-such-page")
    q.wait_for_timeout(800)
    j.check(q.url.rstrip("/") == j.base_url, f"[unknown path] not redirected to / (at {q.url})", page=q)
    ctx.close()
