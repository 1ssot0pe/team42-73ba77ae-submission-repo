"""J14: the Gemini status pill matches /api/health (off locally; on in production with GEMINI_API_KEY)."""
from harness import JourneyAbort, api_json, create_trial, fresh

ID = "J14"
TITLE = "Gemini off (local) / on (production): dock pill matches /api/health"


def run(j):
    p = j.page
    fresh(j)
    h = api_json(j, "/api/health")
    j.check(h["status"] == 200, f"/api/health HTTP {h['status']}")
    gem = bool(h["data"].get("gemini")) if isinstance(h["data"], dict) else None
    j.note(f"health gemini={gem}")
    tid = create_trial(j, "psilocybin")
    if not tid:
        raise JourneyAbort("trial was not created")
    pill = p.locator(".mc-dock").get_by_text("Gemini", exact=False).first.inner_text()
    j.note(f"dock pill: {pill!r}")
    j.check(pill.strip().lower().endswith("on" if gem else "off"), f"dock says {pill!r} but /api/health gemini={gem}")
    # with Gemini off every agent must still work (rule-based path): a portal application screens fine
    p.goto("/portal")
    p.get_by_role("button", name="Apply").click()
    p.wait_for_timeout(2500)
    res = " ".join(p.locator(".portal__result").inner_text().split())
    j.check("eligible" in res.lower(), f"portal screening without Gemini did not give a decision: {res[:160]}")
