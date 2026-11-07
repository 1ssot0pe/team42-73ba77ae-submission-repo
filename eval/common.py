"""Shared helpers for the eval scripts: paths, fixture seeding, and running the
pipeline while keeping the exact source texts it fetched.

Nothing in unblind/ is modified. To capture sources we swap the Ledger class
that unblind.pipeline instantiates for a subclass that remembers its instance.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EVAL = ROOT / "eval"
RESULTS = EVAL / "results"
DATA = ROOT / "data"
GOLD = DATA / "gold.csv"
GOLD_TEMPLATE = DATA / "gold_template.csv"


def use_fixtures() -> Path:
    """Offline mode with the invented test fixtures seeded into a fresh temp cache.

    Must be called before the pipeline runs. Returns the cache directory."""
    os.environ["UNBLIND_OFFLINE"] = "1"
    os.environ.pop("GEMINI_API_KEY", None)
    cache = Path(tempfile.mkdtemp(prefix="unblind-eval-cache-"))
    os.environ["UNBLIND_CACHE"] = str(cache)
    from unblind import net
    net.CACHE_DIR = cache
    from tests import fixtures
    fixtures.seed()
    return cache


def run_with_sources(raw: str) -> Tuple[object, Dict[str, dict]]:
    """Run unblind.pipeline.run and also return {source_id: {kind, url, licence, text}}."""
    from unblind import ledger, pipeline

    captured: List[ledger.Ledger] = []

    class CapturingLedger(ledger.Ledger):
        def __init__(self) -> None:
            super().__init__()
            captured.append(self)

    orig = pipeline.Ledger
    pipeline.Ledger = CapturingLedger
    try:
        rep = pipeline.run(raw)
    finally:
        pipeline.Ledger = orig
    srcs = {}
    if captured:
        for sid, s in captured[-1].sources.items():
            srcs[sid] = {"id": sid, "kind": s.kind, "url": s.url, "licence": s.licence, "title": s.title, "text": s.text}
    return rep, srcs


def run_dir(nct: str, base: Optional[Path] = None) -> Path:
    return (base or RESULTS / "runs") / nct


def get_run(nct: str, rerun: bool = False, base: Optional[Path] = None) -> Tuple[dict, Dict[str, dict]]:
    """Pipeline report (as a dict) and its sources, cached under eval/results/runs/<nct>/.

    The run folder holds fetched source text, so it carries a .gitignore: publisher
    text must not be redistributed unless its licence allows it."""
    d = run_dir(nct, base)
    rp, sp = d / "report.json", d / "sources.json"
    if rp.exists() and sp.exists() and not rerun:
        return json.loads(rp.read_text()), json.loads(sp.read_text())
    rep, srcs = run_with_sources(nct)
    d.mkdir(parents=True, exist_ok=True)
    gi = d.parent / ".gitignore"
    if not gi.exists():
        gi.write_text("# fetched source text and reports; licences vary, do not commit\n*\n")
    rp.write_text(rep.to_json())
    sp.write_text(json.dumps(srcs, indent=1))
    return json.loads(rp.read_text()), srcs


def md_table(header: List[str], rows: List[List[object]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    for r in rows:
        out.append("| " + " | ".join("" if x is None else str(x) for x in r) + " |")
    return "\n".join(out)
