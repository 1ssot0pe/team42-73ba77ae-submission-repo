"""Command line.

python -m unblind run NCT04670081            # one trial, live trace, JSON report
python -m unblind run "10.1056/NEJMoa..."     # DOI
python -m unblind run --file abstract.txt     # pasted text
python -m unblind search "psilocybin depression"   # list candidate NCT IDs for the corpus
python -m unblind build-corpus ids.txt        # run many trials, write reports for review
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import pipeline, sources


def _print_event(e):
    print(e.line(), file=sys.stderr, flush=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="unblind")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("input", nargs="?"); r.add_argument("--file"); r.add_argument("--out")
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("-n", type=int, default=20)
    b = sub.add_parser("build-corpus"); b.add_argument("ids_file"); b.add_argument("--outdir", default="reports")
    a = ap.parse_args(argv)

    if a.cmd == "run":
        raw = Path(a.file).read_text() if a.file else (a.input or sys.stdin.read())
        rep = pipeline.run(raw, on_event=_print_event)
        out = rep.to_json()
        if a.out:
            Path(a.out).write_text(out)
        print(json.dumps({"nct": rep.nct, "title": rep.title, "correction": rep.correction,
                          "top_change": rep.counterfactuals[:1], "warnings": rep.warnings,
                          "status": rep.status}, indent=2))
        return 0
    if a.cmd == "search":
        for st in sources.ctgov_search(a.query, page_size=a.n,
                                       extra="&filter.advanced=AREA[DesignAllocation]RANDOMIZED"):
            s_ = sources.study_summary(st)
            print(f"{s_['nct']}\t{s_['status']}\t{','.join(s_['phases'])}\tresults={s_['has_results']}\t{s_['title'][:90]}")
        return 0
    if a.cmd == "build-corpus":
        outdir = Path(a.outdir); outdir.mkdir(exist_ok=True)
        ids = [x.strip() for x in Path(a.ids_file).read_text().split() if x.strip()]
        for nct in ids:
            print(f"== {nct}", file=sys.stderr)
            try:
                rep = pipeline.run(nct, on_event=_print_event)
                (outdir / f"{nct}.json").write_text(rep.to_json())
            except Exception as e:  # keep going; a corpus build must not die on one trial
                print(f"   failed: {e}", file=sys.stderr)
        print(f"Reports in {outdir}/. Review each in the app and approve to add it to data/calibration_real.csv.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
