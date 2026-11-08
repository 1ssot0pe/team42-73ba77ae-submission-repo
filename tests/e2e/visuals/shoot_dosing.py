"""After screenshots of the Dosing charts (Builder DOSING). Needs the stack from the visuals brief:
    API  8713: UNBLIND_STORE_DIR=/tmp/vis-dosing/store .venv/bin/python -m uvicorn backend.main:app --port 8713
    vite 5713: cd frontend && VITE_API_TARGET=http://127.0.0.1:8713 npx vite --port 5713 --strictPort
and a trial walked with tests/e2e/visuals/walk_dosing.py (psilocybin, seed 42, 500 applicants, manual approvals).

    python tests/e2e/visuals/shoot_dosing.py <trial_id> [suffix]

suffix "" shoots the D62 set, "-d90" the D90 variants of the key chart and the CUSUM, "-predecision" the key chart and the CUSUM
while the drift approval is still pending. Files land in
docs/testing/visuals/after/<chart id><suffix>-{1440-light,1440-dark,390}.png (element crops, each under 400 KB).
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "testing" / "visuals" / "after"
BASE = "http://127.0.0.1:5713"
SETTINGS = [
    ("1440-light", dict(viewport={"width": 1440, "height": 900}, color_scheme="light"), "light"),
    ("1440-dark", dict(viewport={"width": 1440, "height": 900}, color_scheme="dark"), "dark"),
    ("390", dict(viewport={"width": 390, "height": 1800}, color_scheme="light", device_scale_factor=2, is_mobile=True,
                 has_touch=True), "light"),
]
DRAWER = ["rater-accuracy-by-rater", "cusum-site", "participant-accuracy-site"]


def main(tid: str, suffix: str = "") -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    project = [{"id": "p-dosing", "name": "Psilocybin TRD (visuals)", "createdAt": "2026-11-08T10:00:00.000Z",
                "updatedAt": "2026-11-08T10:00:00.000Z", "template": "psilocybin", "draft": "", "trialId": tid,
                "status": "running"}]
    drawer = ["cusum-site"] if suffix == "-d90" else ["cusum-site"] if suffix == "-predecision" else DRAWER
    with sync_playwright() as p:
        b = p.chromium.launch()
        for tag, kw, theme in SETTINGS:
            ctx = b.new_context(**kw)
            ctx.add_init_script(
                f"try{{localStorage.setItem('parallax.projects.v1',{json.dumps(json.dumps(project))});"
                f"localStorage.setItem('unblind.theme','{theme}')}}catch(e){{}}")
            pg = ctx.new_page()
            pg.goto(f"{BASE}/trials/p-dosing/dosing")
            key = pg.locator('figure.chart[data-chart="rater-accuracy-site"]').first
            key.wait_for(timeout=30000)
            pg.wait_for_selector('figure.chart[data-chart="rater-accuracy-site"] .recharts-surface', timeout=30000)
            pg.wait_for_timeout(900)
            key.scroll_into_view_if_needed()
            key.screenshot(path=str(OUT / f"rater-accuracy-site{suffix}-{tag}.png"))
            pg.get_by_role("button", name="View all charts").first.click()
            dlg = pg.locator("[role=dialog]:visible").last
            dlg.wait_for(timeout=10000)
            pg.wait_for_timeout(900)
            for cid in drawer:
                el = dlg.locator(f'figure.chart[data-chart="{cid}"]').first
                if not el.count():
                    print("missing", cid, tag)
                    continue
                el.evaluate("e => e.scrollIntoView({block: 'center'})")
                pg.wait_for_timeout(300)
                el.screenshot(path=str(OUT / f"{cid}{suffix}-{tag}.png"))
            ctx.close()
        b.close()
    for f in sorted(OUT.glob("*.png")):
        if f.stat().st_size > 400_000:
            print("TOO BIG", f.name, f.stat().st_size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")
