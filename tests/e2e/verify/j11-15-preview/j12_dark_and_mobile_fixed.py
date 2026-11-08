"""J12: dark mode at 390 px on every page: no horizontal scroll, readable glass, working menu and dock."""
from harness import copy_checks, create_trial, decide, dock_button, fresh, glass_contrast

ID = "J12"  # verifier copy: +1 week only when enabled (it is disabled while approvals are pending)
TITLE = "Dark mode and 390 px width on every page"
CONTEXT = {"viewport": (390, 844), "color_scheme": "dark"}
PAGES = ["/", "/predose", "/portal", "/dosing", "/postdose"]


def run(j):
    p = j.page
    fresh(j)
    copy_checks(j, "start page 390 dark")
    glass_contrast(j, "start page 390 dark")
    tid = create_trial(j, "psilocybin")
    if tid and dock_button(p, r"\+1 week").is_enabled():
        dock_button(p, r"\+1 week").click()
        p.wait_for_timeout(1200)
    for path in PAGES:
        p.goto(path)
        p.wait_for_load_state("networkidle")
        p.wait_for_timeout(1200)
        copy_checks(j, f"{path} 390 dark")
        glass_contrast(j, f"{path} 390 dark")
        j.shot(f"{path} at 390 dark", full_page=True)
    # menu at 390
    p.goto("/")
    btn = p.get_by_role("button", name="Menu")
    j.check(btn.is_visible(), "Menu button not visible at 390 px")
    btn.click()
    menu = p.locator(".nav-menu")
    j.check(menu.is_visible(), "menu did not open")
    menu.get_by_role("link", name="Pre-dosing").click()
    p.wait_for_timeout(500)
    j.check(p.url.endswith("/predose") and not menu.is_visible(), "menu link did not navigate and close")
    # dock fits
    p.goto("/")
    p.wait_for_timeout(800)
    if p.locator(".mc-dock").count():
        box = p.locator(".mc-dock").bounding_box()
        j.check(box["x"] >= 0 and box["x"] + box["width"] <= 390, f"dock overflows the 390 px viewport: {box}")
        decide(j, "confirm shortlist")
        # can the last slip and log be scrolled clear of the dock?
        p.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        p.wait_for_timeout(400)
        j.shot("390 dark bottom of mission control", full_page=False)
