"""Before/after side-by-side images for every chart shot that exists in both folders.

    .venv/bin/python tests/e2e/visuals/make_compare.py

Writes docs/testing/visuals/compare/<name>.png (before left, after right), each under 400 KB, and lists
after-only shots (new charts) at the end. Run it again after re-shooting.
"""
from __future__ import annotations

import base64
import subprocess
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
VIS = ROOT / "docs" / "testing" / "visuals"
BEFORE, AFTER, OUT = VIS / "before", VIS / "after", VIS / "compare"
LIMIT = 400 * 1024


def data_uri(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def page_html(name: str, before: Path, after: Path) -> str:
    dark = "1440-dark" in name
    bg, fg = ("#171614", "#f5f3f1") if dark else ("#f5f3f1", "#2b2825")
    cell = lambda label, p: (f'<figure><figcaption>{label}</figcaption><img src="{data_uri(p)}"></figure>')
    return f"""<!doctype html><meta charset="utf-8"><style>
      body {{ margin: 0; padding: 16px; background: {bg}; color: {fg}; font: 600 14px/1.3 sans-serif; }}
      h1 {{ font-size: 15px; margin: 0 0 12px; }}
      .row {{ display: flex; gap: 16px; align-items: flex-start; }}
      figure {{ margin: 0; flex: 1 1 0; min-width: 0; }}
      figcaption {{ margin-bottom: 6px; }}
      img {{ width: 100%; height: auto; border: 1px solid #8884; display: block; }}
    </style><h1>{name}</h1><div class="row">{cell("Before", before)}{cell("After", after)}</div>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = sorted(p.name for p in AFTER.glob("*.png") if (BEFORE / p.name).exists())
    new = sorted(p.name for p in AFTER.glob("*.png") if not (BEFORE / p.name).exists())
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1600, "height": 900})
        for name in pairs:
            pg.set_content(page_html(name, BEFORE / name, AFTER / name))
            pg.wait_for_timeout(100)
            out = OUT / name
            pg.screenshot(path=str(out), full_page=True)
            size = 1600
            while out.stat().st_size > LIMIT and size > 600:
                size -= 200
                subprocess.run(["sips", "-Z", str(size), str(out)], capture_output=True, check=False)
        b.close()
    lines = ["# Before and after", "", "Each image: before on the left, after on the right.", ""]
    lines += [f"- [{n}]({n})" for n in pairs]
    if new:
        lines += ["", "## New charts (after only, no before shot)", ""] + [f"- [../after/{n}](../after/{n})" for n in new]
    (OUT / "README.md").write_text("\n".join(lines) + "\n")
    print(f"{len(pairs)} pairs, {len(new)} after-only")


if __name__ == "__main__":
    main()
