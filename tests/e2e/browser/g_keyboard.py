"""G: keyboard-only smoke test. Tab through the nav, the dock, an approval slip and the portal form;
every focused control must show a visible focus indicator, and Enter/Space must operate it."""
from harness import JourneyAbort, create_trial, fresh, slips

ID = "G"
TITLE = "Keyboard through nav, dock, approvals and forms; visible focus"

FOCUS_JS = r"""
() => {
  const e = document.activeElement;
  if (!e || e === document.body) return null;
  const cs = getComputedStyle(e);
  const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) ||
               (cs.boxShadow && cs.boxShadow !== 'none');
  const r = e.getBoundingClientRect();
  const label = (e.getAttribute('aria-label') || e.innerText || e.value || e.id || e.tagName).trim().split('\n')[0].slice(0, 40);
  return {tag: e.tagName, id: e.id, cls: (e.className || '').toString().slice(0, 60), label, ring,
          outline: cs.outlineStyle + ' ' + cs.outlineWidth + ' ' + cs.outlineColor, shadow: cs.boxShadow.slice(0, 60),
          onscreen: r.bottom > 0 && r.top < innerHeight && r.width > 0};
}
"""


def tab_walk(j, n, where):
    p = j.page
    seen = []
    for _ in range(n):
        p.keyboard.press("Tab")
        f = p.evaluate(FOCUS_JS)
        if f:
            seen.append(f)
    noring = [f"{f['tag']}:{f['label']}" for f in seen if not f["ring"]]
    j.check(not noring, f"[{where}] focus not visible on: {sorted(set(noring))[:8]}")
    return seen


def run(j):
    p = j.page
    fresh(j)
    # start page: tabs and form
    seen = tab_walk(j, 16, "start page")
    labels = [f["label"] for f in seen]
    j.note(f"start page tab order: {labels}")
    j.check(any("Mission control" in x for x in labels) and any("Create trial" in x for x in labels),
            "Tab does not reach both the nav and Create trial")
    # create a trial with the keyboard: focus Create trial, press Enter
    p.get_by_role("button", name="Create trial").focus()
    p.keyboard.press("Enter")
    try:
        p.locator(".mc-dock").wait_for(timeout=20000)
    except Exception:
        raise JourneyAbort("Enter on Create trial did not create a trial")
    p.wait_for_timeout(1000)
    p.locator("body").focus()
    p.evaluate("window.scrollTo(0,0); document.activeElement && document.activeElement.blur()")
    seen = tab_walk(j, 60, "mission control")
    order = [f"{f['tag']}:{f['label']}" for f in seen]
    j.note(f"mission control tab order (first 60): {order}")
    j.check(any("Approve" in o for o in order), "Tab never reaches an Approve button")
    j.check(any("Next day" in o for o in order), "Tab never reaches the dock (Next day)")
    off = [f"{f['tag']}:{f['label']}" for f in seen if not f["onscreen"]]
    if off:
        j.note(f"focused while off screen: {off[:6]}")
    # sign a slip by keyboard only
    s = slips(p, "confirm shortlist").first
    s.locator("input[id$='-reviewer']").focus()
    p.keyboard.type("Keyboard Reviewer")
    p.keyboard.press("Tab")   # comment
    p.keyboard.press("Tab")   # Approve (or View evidence summary comes before?)
    f = p.evaluate(FOCUS_JS)
    j.note(f"after reviewer + 2 Tabs focus is on {f}")
    if f and f["label"] == "Approve":
        p.keyboard.press("Enter")
        p.wait_for_timeout(1500)
        j.check(slips(p, "confirm shortlist").count() == 0, "Enter on Approve did not sign the slip")
    else:
        j.check(False, f"Approve is not the next stop after the comment field (got {f and f['label']})")
    # dock by keyboard
    nd = p.locator(".mc-dock").get_by_role("button", name="Next day")
    nd.focus()
    day0 = p.locator(".nav__day").inner_text()
    p.keyboard.press("Space")
    p.wait_for_timeout(1500)
    j.check(p.locator(".nav__day").inner_text() != day0, "Space on Next day did not advance the day")
    # focused control hidden behind the floating dock?
    p.locator("body").focus()
    hidden = p.evaluate("""() => { const d = document.querySelector('.mc-dock')?.getBoundingClientRect(); if (!d) return [];
        return Array.from(document.querySelectorAll('a,button,input,select,textarea')).filter(e => {
          e.focus({preventScroll: false}); const r = e.getBoundingClientRect();
          return !e.closest('.mc-dock') && r.height > 0 && r.top < d.bottom && r.bottom > d.top + 4 && r.left < d.right && r.right > d.left;
        }).map(e => (e.innerText || e.id || e.tagName).trim().slice(0, 30)).slice(0, 8); }""")
    j.check(not hidden, f"controls hidden under the dock when focused (scrolled into view): {hidden}")
    # portal form by keyboard
    p.goto("/portal")
    p.wait_for_timeout(800)
    seen = tab_walk(j, 30, "portal")
    j.note(f"portal tab order: {[f['label'] for f in seen]}")
    p.locator("#portal-age").focus()
    p.keyboard.press("ControlOrMeta+a")
    p.keyboard.type("17")
    p.keyboard.press("Enter")       # implicit submit
    p.wait_for_timeout(2000)
    j.check("excluded" in p.locator(".portal__result").inner_text().lower(), "Enter in the age field did not submit the form")
    # mobile menu: Enter opens, Escape closes and returns focus
    p.set_viewport_size({"width": 390, "height": 844})
    p.wait_for_timeout(300)
    btn = p.get_by_role("button", name="Menu")
    btn.focus()
    p.keyboard.press("Enter")
    p.wait_for_timeout(300)
    j.check(p.locator(".nav-menu").is_visible(), "Enter on Menu did not open the menu")
    first = p.evaluate("document.activeElement.innerText")
    j.check("Mission control" in first, f"focus did not move into the menu (on {first!r})")
    p.keyboard.press("Escape")
    p.wait_for_timeout(300)
    j.check(not p.locator(".nav-menu").is_visible(), "Escape did not close the menu")
    j.check(p.evaluate("document.activeElement.innerText").strip() == "Menu", "focus did not return to Menu")
