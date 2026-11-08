"""J15: every nav link, the wordmark, the '3 to sign' pill and the Evidence engine link."""
import re

from harness import JourneyAbort, create_trial, fresh

ID = "J15"
TITLE = "Every nav link, including Evidence engine"
LINKS = [("Mission control", "/"), ("Pre-dosing", "/predose"), ("Volunteer portal", "/portal"),
         ("Dosing", "/dosing"), ("Post-dosing", "/postdose")]


def run(j):
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    nav = p.locator("nav.nav")
    for label, path in LINKS:
        nav.get_by_role("link", name=label, exact=True).click()
        p.wait_for_timeout(700)
        j.check(p.url.rstrip("/").endswith(path.rstrip("/")) or (path == "/" and p.url.rstrip("/") == j.base_url),
                f"[{label}] went to {p.url}")
        active = nav.locator(".nav__link.is-active").all_inner_texts()
        j.check(active == [label], f"[{label}] active link is {active}")
        j.check(p.locator("h1").count() == 1, f"[{label}] no single h1")
    p.goto("/postdose")
    nav.get_by_role("link", name=re.compile("Parallax", re.I)).first.click()
    p.wait_for_timeout(500)
    j.check(p.url.rstrip("/") == j.base_url, f"wordmark did not go home: {p.url}")
    p.goto("/dosing")
    sign = nav.locator(".nav__sign")
    if sign.count():
        sign.click()
        p.wait_for_timeout(500)
        j.check(p.url.rstrip("/") == j.base_url, "the 'N to sign' pill did not go to Mission control")
    ev = nav.get_by_role("link", name=re.compile("Evidence engine"))
    href = ev.get_attribute("href")
    j.note(f"Evidence engine href: {href}")
    j.check(not re.match(r"https?://(localhost|127\.0\.0\.1)", href or ""),
            f"Evidence engine link points at {href}, which only works on the developer's machine")
    with p.context.expect_page(timeout=10000) as info:
        ev.click()
    tab = info.value
    try:
        tab.wait_for_load_state("domcontentloaded", timeout=8000)
    except Exception:
        pass
    j.note(f"Evidence engine tab url after click: {tab.url}")
    title = ""
    try:
        title = tab.title()
    except Exception:
        pass
    j.check(tab.url.startswith("http") and "chrome-error" not in tab.url and title != "",
            f"Evidence engine tab did not load (url {tab.url}, title {title!r})", page=tab)
    tab.close()
