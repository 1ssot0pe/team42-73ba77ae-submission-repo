"""Planted-truth recovery study for the UNBLIND meta-regression.

    python eval/synthetic_recovery.py            # full run (3 scenarios x k in {15,30,60} x 300 reps)
    python eval/synthetic_recovery.py --reps 50  # quick look

Every number this script writes is SYNTHETIC. It shows whether the method
recovers a known effect when its assumptions hold, and how it fails when they
do not. It is not evidence about real-world performance.

For each replicate we simulate k trials with unblind.synthetic.make_trials
(observed_frac 0.35) and compare four estimates of the effect at zero
unblinding (truth = true_g = 0.35):

  naive        DerSimonian-Laird random-effects pooled mean of reported g over
               all k trials, ignoring blinding. This is what a standard
               meta-analysis would report. The BASELINE.
  primary      model.fit_metareg intercept, trials with observed blinding only.
  sensitivity  model.fit_metareg intercept incl. trials whose u was imputed
               from design (model.design_model + synthetic.fill_imputed).

Two extra stress tests use thin wrappers around make_trials defined below (not
edits to unblind/): 'noisy_guess' replaces the observed u with a binomial
guess-accuracy measurement, and 'mixed' adds real expectancy bias on top of
reverse causation.
"""
from __future__ import annotations

import argparse
import copy
import math
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from eval.common import RESULTS, md_table  # noqa: E402
from unblind import model, synthetic  # noqa: E402

TRUE_G = 0.35
B_TRUE = 0.6
OBS_FRAC = 0.35
SCENARIOS = ["expectancy", "reverse_causation", "confounded"]
KS = [15, 30, 60]
METHODS = ["naive", "primary", "sensitivity"]
LABEL = {"naive": "Naive pooled mean (baseline)", "primary": "UNBLIND primary (observed u)",
         "sensitivity": "UNBLIND sensitivity (+ imputed u)"}


# ---------------------------------------------------------------------------
# baseline
# ---------------------------------------------------------------------------
def naive_pooled(rows: List[dict]) -> Tuple[float, float, float]:
    """DerSimonian-Laird random-effects pooled mean with a 95% Wald interval."""
    y = np.array([r["g"] for r in rows], float)
    v = np.array([r["se_g"] for r in rows], float) ** 2
    w = 1 / v
    mu_fe = float(np.sum(w * y) / np.sum(w))
    q = float(np.sum(w * (y - mu_fe) ** 2))
    c = float(np.sum(w) - np.sum(w ** 2) / np.sum(w))
    tau2 = max(0.0, (q - (len(y) - 1)) / c) if c > 0 else 0.0
    wr = 1 / (v + tau2)
    mu = float(np.sum(wr * y) / np.sum(wr))
    se = math.sqrt(1 / float(np.sum(wr)))
    return mu, mu - 1.96 * se, mu + 1.96 * se


# ---------------------------------------------------------------------------
# stress-test wrappers (local to eval; make_trials itself is untouched)
# ---------------------------------------------------------------------------
def make_noisy_guess(k: int, seed: int) -> List[dict]:
    """'expectancy', but observed u is MEASURED: each trial's guess accuracy is a
    binomial draw over its participants, u = max(0, 2*acc - 1). make_trials sets
    observed u to the exact true u, which hides regression dilution and the
    floor at zero."""
    rows = synthetic.make_trials(k=k, true_g=TRUE_G, b_true=B_TRUE, scenario="expectancy",
                                 observed_frac=OBS_FRAC, seed=seed)
    rng = np.random.default_rng(seed + 7_919)
    for r in rows:
        if r["u_status"] != "observed":
            continue
        n = max(10, int(round(4.1 / r["se_g"] ** 2)))     # trial size implied by its SE
        acc_true = (1 + r["u_true"]) / 2
        acc = rng.binomial(n, acc_true) / n
        r["u"] = round(model.u_from_accuracy(acc), 3)
        r["u_sd"] = round(2 * math.sqrt(acc_true * (1 - acc_true) / n), 3)
    return rows


def make_mixed(k: int, seed: int, b_mix: float = 0.3) -> List[dict]:
    """reverse_causation (u partly caused by efficacy) PLUS a real expectancy bias
    b_mix * u. Neither the naive mean nor the correction is right here."""
    rows = synthetic.make_trials(k=k, true_g=TRUE_G, b_true=B_TRUE, scenario="reverse_causation",
                                 observed_frac=OBS_FRAC, seed=seed)
    for r in rows:
        r["g"] = round(r["g"] + b_mix * r["u_true"], 3)
    return rows


def gen(scenario: str, k: int, seed: int) -> List[dict]:
    if scenario == "noisy_guess":
        return make_noisy_guess(k, seed)
    if scenario == "mixed":
        return make_mixed(k, seed)
    return synthetic.make_trials(k=k, true_g=TRUE_G, b_true=B_TRUE, scenario=scenario,
                                 observed_frac=OBS_FRAC, seed=seed)


# ---------------------------------------------------------------------------
def one_replicate(scenario: str, k: int, seed: int) -> Dict[str, Optional[Tuple[float, float, float]]]:
    rows = gen(scenario, k, seed)
    out: Dict[str, Optional[Tuple[float, float, float]]] = {"naive": naive_pooled(rows)}
    fp = model.fit_metareg(copy.deepcopy(rows), label="primary")
    out["primary"] = fp.reference() if fp else None
    dm = model.design_model(rows)
    filled = synthetic.fill_imputed(copy.deepcopy(rows), dm)
    fs = model.fit_metareg(filled, label="sensitivity", use_imputed=True)
    out["sensitivity"] = fs.reference() if fs else None
    return out


def summarise(results: List[Dict[str, Optional[tuple]]], truth: float) -> Dict[str, dict]:
    s = {}
    for m in METHODS:
        got = [r[m] for r in results if r[m] is not None]
        n_all = len(results)
        if not got:
            s[m] = {"n": 0, "fail": 1.0}
            continue
        est = np.array([g[0] for g in got])
        lo = np.array([g[1] for g in got])
        hi = np.array([g[2] for g in got])
        err = est - truth
        cov = float(np.mean((lo <= truth) & (truth <= hi)))
        s[m] = {
            "n": len(got), "fail": 1 - len(got) / n_all,
            "bias": float(err.mean()), "bias_mcse": float(err.std(ddof=1) / math.sqrt(len(err))) if len(err) > 1 else float("nan"),
            "median_bias": float(np.median(err)),
            "rmse": float(math.sqrt(np.mean(err ** 2))),
            "coverage": cov, "coverage_mcse": math.sqrt(cov * (1 - cov) / len(got)),
            "ci_width": float(np.median(hi - lo)),
            "est": est,
        }
    return s


def fmt(x: float, nd: int = 3, sign: bool = False) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def table_rows(summary: Dict[Tuple[str, int], Dict[str, dict]], scenarios, ks) -> List[List[str]]:
    rows = []
    for sc in scenarios:
        for k in ks:
            for m in METHODS:
                d = summary[(sc, k)][m]
                if d["n"] == 0:
                    rows.append([sc, k, LABEL[m], "n/a", "n/a", "n/a", "n/a", "n/a", fmt(100 * d["fail"], 0) + "%"])
                    continue
                rows.append([sc, k, LABEL[m],
                             f"{fmt(d['bias'], sign=True)} ± {fmt(1.96 * d['bias_mcse'])}",
                             fmt(d["median_bias"], sign=True), fmt(d["rmse"]),
                             f"{100 * d['coverage']:.0f}% ± {100 * 1.96 * d['coverage_mcse']:.0f}",
                             fmt(d["ci_width"], 2), f"{100 * d['fail']:.0f}%"])
    return rows


HEADER = ["scenario", "k", "estimator", "mean bias (± MC 95%)", "median bias", "RMSE",
          "95% CI coverage (± MC 95%)", "median CI width", "fits failed"]


# ---------------------------------------------------------------------------
def _kde(x: np.ndarray, lo: float, hi: float, n: int = 300):
    """Gaussian kernel density on a grid (Silverman bandwidth), no scipy."""
    xs = np.linspace(lo, hi, n)
    sd = float(np.std(x)) or 0.05
    bw = max(1.06 * sd * len(x) ** (-0.2), 0.01)
    dens = np.exp(-0.5 * ((xs[:, None] - x[None, :]) / bw) ** 2).sum(axis=1)
    return xs, dens


def plot(summary, path: Path, reps: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    colours = {"naive": "#eb6834", "primary": "#2a78d6", "sensitivity": "#1baf7a"}
    ink, ink2, grid, bg = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    titles = {"expectancy": "Expectancy: bias comes only from unblinding (model assumptions hold)",
              "reverse_causation": "Reverse causation: improvement causes correct guessing, no real bias planted "
                                   "(the method's key failure mode)",
              "confounded": "Confounded: better-blinded trials also had lower true effects"}
    plt.rcParams.update({"font.size": 10, "font.family": "DejaVu Sans"})
    fig, axes = plt.subplots(len(SCENARIOS), len(KS), figsize=(13, 10.5), sharex=True, sharey=True)
    fig.patch.set_facecolor(bg)
    xlo, xhi = -1.0, 1.4
    order = list(reversed(METHODS))              # naive drawn on top row of each panel
    for i, sc in enumerate(SCENARIOS):
        for j, k in enumerate(KS):
            ax = axes[i, j]
            ax.set_facecolor(bg)
            for y, m in enumerate(order):
                d = summary[(sc, k)][m]
                if d["n"] == 0:
                    continue
                est = d["est"]
                inside = est[(est >= xlo) & (est <= xhi)]
                xs, dens = _kde(inside, xlo, xhi)
                dens = 0.38 * dens / dens.max()
                keep = dens > 0.004
                ax.fill_between(xs[keep], y - dens[keep], y + dens[keep], color=colours[m], alpha=0.28, lw=0)
                q1, med, q3 = np.percentile(est, [25, 50, 75])
                ax.plot([max(q1, xlo), min(q3, xhi)], [y, y], color=colours[m], lw=4, solid_capstyle="round")
                ax.plot([min(max(med, xlo), xhi)], [y], "o", ms=7, color="white", mec=colours[m], mew=2, zorder=5)
                n_fail = int(round(d["fail"] * reps))
                n_out = int(len(est) - len(inside))
                bits = []
                if n_fail:
                    bits.append(f"{n_fail}/{reps} fits failed")
                if n_out:
                    bits.append(f"{n_out} beyond axis")
                if bits:
                    ax.text(xlo + 0.03, y + 0.40, ", ".join(bits), ha="left", va="center", fontsize=7.5, color=ink2)
            ax.axvline(TRUE_G, color=ink, lw=1.4, ls=(0, (4, 2)), zorder=4)
            ax.set_yticks([])
            ax.set_xlim(xlo, xhi)
            ax.set_ylim(-0.55, len(METHODS) - 0.35)
            ax.grid(axis="x", color=grid, lw=0.8)
            ax.set_axisbelow(True)
            for sp in ("top", "right", "left"):
                ax.spines[sp].set_visible(False)
            ax.spines["bottom"].set_color(ink2)
            ax.tick_params(axis="x", colors=ink2, labelsize=9)
            ax.set_title(f"k = {k} trials", fontsize=9.5, color=ink2, pad=4, loc="left")
            if i == 0 and j == 0:
                ax.annotate("truth 0.35", xy=(TRUE_G, len(METHODS) - 0.45), xytext=(6, 0), textcoords="offset points",
                            fontsize=8.5, color=ink, va="center")
        # scenario heading above the row
        top = axes[i, 0].get_position().y1
        fig.text(0.04, top + 0.032, titles[sc], fontsize=11.5, color=ink, fontweight="bold", ha="left", va="bottom")

    fig.suptitle("SYNTHETIC DATA. Can UNBLIND recover a planted drug effect?", fontsize=14, color=ink,
                 x=0.04, ha="left", y=0.985, fontweight="bold")
    fig.text(0.04, 0.945, f"Each shape is the spread of estimates from {reps} simulated meta-analyses (35% of trials report "
             "blinding). Bar = middle 50%, circle = median.\nDashed line = the planted true effect at zero unblinding. "
             "Closer to the line is better. Not real-world performance.", fontsize=9.5, color=ink2, ha="left", va="top")
    handles = [Line2D([], [], color=colours[m], lw=6, alpha=0.6, label=LABEL[m]) for m in METHODS]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.04, 0.905), ncol=3, frameon=False, fontsize=9.5,
               handlelength=1.6, columnspacing=2.0)
    fig.supxlabel("Estimated effect at zero unblinding (Hedges' g)", fontsize=10, color=ink2, y=0.012)
    fig.subplots_adjust(left=0.04, right=0.985, top=0.80, bottom=0.07, wspace=0.06, hspace=0.62)
    # headings need final axes positions, so place them after layout
    for t in list(fig.texts):
        if t.get_text() in titles.values():
            t.remove()
    for i, sc in enumerate(SCENARIOS):
        top = axes[i, 0].get_position().y1
        fig.text(0.04, top + 0.030, titles[sc], fontsize=11.5, color=ink, fontweight="bold", ha="left", va="bottom")
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)


# ---------------------------------------------------------------------------
def interpretation(S) -> str:
    def g(sc, k, m, key):
        return S[(sc, k)][m].get(key, float("nan"))

    e_n, e_s = g("expectancy", 60, "naive", "bias"), g("expectancy", 60, "sensitivity", "bias")
    e_pc, e_nc = g("expectancy", 60, "primary", "coverage"), g("expectancy", 60, "naive", "coverage")
    r_n, r_p = g("reverse_causation", 60, "naive", "bias"), g("reverse_causation", 60, "primary", "bias")
    r_pc = g("reverse_causation", 60, "primary", "coverage")
    c_n, c_p = g("confounded", 60, "naive", "bias"), g("confounded", 60, "primary", "bias")
    f15 = g("expectancy", 15, "primary", "fail")
    e_p = g("expectancy", 60, "primary", "bias")
    rm15_p, rm15_n = g("expectancy", 15, "primary", "rmse"), g("expectancy", 15, "naive", "rmse")
    return (
        f"When its assumptions hold (expectancy), the naive meta-analysis overstates the drug effect by {e_n:+.2f} g and "
        f"its intervals almost never contain the truth ({100 * e_nc:.0f}% coverage at k=60). The UNBLIND primary estimate (a + c) "
        f"is close to unbiased ({e_p:+.3f} g; sensitivity fit {e_s:+.3f} g) and contains the truth {100 * e_pc:.0f}% of the "
        f"time, but its intervals are several times wider because the fit extrapolates to zero unblinding, and with 15 "
        f"trials its RMSE ({rm15_p:.2f}) is worse than the naive one ({rm15_n:.2f}): too few trials report blinding for the "
        f"correction to pay for its own noise. "
        f"Under reverse causation we planted no expectancy bias at all, so the naive mean is nearly right (bias {r_n:+.3f}, "
        f"the averaged on-site rater inflation) and the correction over-subtracts (bias {r_p:+.3f}, coverage {100 * r_pc:.0f}%): "
        f"this is the method's key failure mode, and why the report calls the corrected value a conservative bound. "
        f"Under cross-trial confounding both are wrong in opposite directions (naive {c_n:+.2f}, primary {c_p:+.2f}), and the "
        f"correction is the worse of the two because the confounder lines up exactly with blinding quality. "
        f"With 15 trials only about 5 report blinding, so the primary fit fails in {100 * f15:.0f}% of runs. "
        f"These are synthetic results: they show the method works when its assumptions hold and how it breaks when they "
        f"do not. They are not real-world performance."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--reps", type=int, default=300)
    ap.add_argument("--stress-reps", type=int, default=300)
    ap.add_argument("--out", default=str(RESULTS))
    a = ap.parse_args(argv)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    S = {}
    for si, sc in enumerate(SCENARIOS + ["noisy_guess", "mixed"]):
        ks = KS if sc in SCENARIOS else [30]
        reps = a.reps if sc in SCENARIOS else a.stress_reps
        for ki, k in enumerate(ks):
            base = 1_000_000 * (si + 1) + 10_000 * ki          # distinct seeds for every (scenario, k, rep)
            res = [one_replicate(sc, k, base + r) for r in range(reps)]
            S[(sc, k)] = summarise(res, TRUE_G)
            print(f"{sc:18s} k={k:3d}  " + "  ".join(
                f"{m}: bias {S[(sc, k)][m].get('bias', float('nan')):+.3f} cov {S[(sc, k)][m].get('coverage', float('nan')):.2f} "
                f"fail {S[(sc, k)][m]['fail']:.2f}" for m in METHODS), flush=True)

    main_tbl = md_table(HEADER, table_rows(S, SCENARIOS, KS))
    stress_tbl = md_table(HEADER, table_rows(S, ["noisy_guess", "mixed"], [30]))
    elapsed = time.time() - t0
    md = f"""# Synthetic recovery: can UNBLIND find a planted drug effect?

**SYNTHETIC DATA. These numbers are not real-world performance.** Every trial below is simulated by
`unblind.synthetic.make_trials` (rows labelled `provenance=SYNTHETIC`). They test the statistics, not the agents.

Setup: true effect at zero unblinding `true_g = {TRUE_G}`, planted bias slope `b_true = {B_TRUE}` per unit of
unblinding, on-site raters inflate g by `r_onsite = 0.10` (truth is the central-rater, zero-unblinding effect; the estimator is the fitted a + c), 35% of trials report blinding data. {a.reps} replicate
meta-analyses per row, each with its own seed. Bias, RMSE and coverage are measured against `true_g` and computed
only over fits that succeeded. "± MC 95%" is Monte Carlo error from the finite number of replicates.

* **Naive pooled mean (baseline)**: DerSimonian-Laird random-effects mean of reported g over all k trials, ignoring
  blinding. What a standard meta-analysis would report.
* **UNBLIND primary**: `model.fit_metareg` intercept, trials with observed blinding only (about 0.35 x k trials).
* **UNBLIND sensitivity**: same, adding trials whose unblinding was imputed from design.

## Main scenarios

{main_tbl}

## What this means

{interpretation(S)}

## Stress tests (k = 30, local wrappers in `eval/synthetic_recovery.py`)

* `noisy_guess`: the expectancy scenario, but observed unblinding is *measured* from a binomial count of correct
  guesses instead of being the exact true value. `make_trials` gives the model noiseless u, which flatters it.
* `mixed`: reverse causation **plus** a real expectancy bias of 0.3 x u. Arguably the most realistic case:
  the naive mean is too high and the correction too low, so the truth lies between them.

{stress_tbl}

## Scenario notes and caveats

* In `confounded`, trials with a non-inert comparator have a true effect 0.25 lower (0.10 instead of 0.35). The
  table scores against 0.35, the effect in the inert-placebo population. The trial-averaged true effect is about 0.25.
  Either way the correction lands far below both, because extrapolating to zero unblinding means extrapolating into
  the low-efficacy designs.
* In `reverse_causation`, `make_trials` adds `0.5 x g_i` to every trial's u, pushing about 19% of trials to the
  ceiling u = 1. That compresses the u range and makes the over-subtraction smaller than an unclipped version would show.
* In `reverse_causation` the sensitivity fit is less biased than the primary fit. That is not a virtue of imputation
  in general: imputed u comes from design only, so it carries none of the efficacy-driven part of u and acts like an
  instrument. It only helps if the design model is right.
* The rater term `c` is fitted when raters vary and the reported estimate is a + c. The naive mean averages over
  rater placement, which is why its bias in `reverse_causation` is about +0.065 (65% on-site raters x 0.10) rather than zero.
* Coverage of the UNBLIND intervals is above 95% when unbiased because `fit_metareg` uses a Knapp-Hartung scale
  floored at 1 (conservative). High coverage under reverse causation reflects wide intervals, not a correct centre.
* Runtime {elapsed:.0f} s. Reproduce with `python eval/synthetic_recovery.py`.
"""
    (out / "synthetic_recovery.md").write_text(md)
    plot(S, out / "synthetic_recovery.png", a.reps)
    print(f"\nwrote {out / 'synthetic_recovery.md'} and {out / 'synthetic_recovery.png'} in {elapsed:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
