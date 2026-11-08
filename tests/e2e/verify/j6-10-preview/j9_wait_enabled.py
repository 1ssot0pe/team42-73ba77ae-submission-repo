"""J9 rerun on the preview with one change: before pressing Play, wait up to 5 s for the button to be enabled
(the shared play() checks once, right after the approve, while the post-approve state refresh is still in flight)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "browser"))
from playwright.sync_api import sync_playwright  # noqa: E402
import harness  # noqa: E402

_play = harness.play


def play_wait(j, *a, **kw):
    try:
        harness.dock_button(j.page, "Play").wait_for(state="visible", timeout=5000)
        j.page.wait_for_function("() => [...document.querySelectorAll('.mc-dock button')]"
                                 ".some(b => b.textContent.trim() === 'Play' && !b.disabled)", timeout=5000)
    except Exception:
        pass
    return _play(j, *a, **kw)


harness.play = play_wait
import j09_drift_decisions as j9  # noqa: E402
j9.play = play_wait

a = harness.parse_args("preview")
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    r = harness.run_journey(b, j9, a.base_url, a.env, a.prefix)
    Path(a.out).write_text(json.dumps(r, indent=2, default=str))
    print("J9", "PASS" if r["passed"] else "FAIL", r["duration_s"], r["timings"], r["failures"], r["notes"],
          "console", len(r["console_errors"]), "netfail", len(r["network_failures"]))
    b.close()
