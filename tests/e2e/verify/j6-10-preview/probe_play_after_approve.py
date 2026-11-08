"""Preview probe for the J9 failure: after approving the shortlist, is Play disabled only briefly (test race)
or does the server keep the trial blocked? Polls the dock button and GET /state for 12 s."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "browser"))
from playwright.sync_api import sync_playwright  # noqa: E402
from harness import Journey, create_trial, decide, dock_button, fresh, parse_args, play, day_number  # noqa: E402

a = parse_args("preview")
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    j = Journey(b, "JP", "probe", a.base_url, a.env, a.prefix)
    p = j.page
    fresh(j)
    tid = create_trial(j, "psilocybin")
    err = decide(j, "confirm shortlist")
    t0 = time.time(); samples = []
    while time.time() - t0 < 12:
        st = p.evaluate("(id) => fetch('/api/trials/' + id + '/state').then(r => r.json())", tid)
        samples.append({"t": round(time.time() - t0, 2), "play_enabled": dock_button(p, "Play").is_enabled(),
                        "blocked": st.get("blocked"), "phase": st.get("phase"), "day": st.get("day")})
        if samples[-1]["play_enabled"]:
            break
        p.wait_for_timeout(1000)
    res = play(j, timeout_s=20) if dock_button(p, "Play").is_enabled() else "disabled"
    out = {"trial": tid, "approve_err": err, "samples": samples, "play_after": res, "day_after": day_number(p),
           "console_errors": j.console_errors, "network_failures": j.network_failures}
    j.shot("play after approve")
    Path(a.out).write_text(json.dumps(out, indent=2, default=str))
    print(json.dumps(out, default=str)[:3000])
    b.close()
