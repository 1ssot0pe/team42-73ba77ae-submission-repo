"""UNBLIND live demo UI.

    streamlit run app/app.py

Everything shown here comes from unblind.pipeline.Report. Text taken from
fetched documents or uploaded reports is untrusted, so every string is
HTML-escaped before it is rendered and only http(s) links become anchors.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

from unblind import llm, model, net, pipeline, signoff  # noqa: E402
from unblind.synthetic import fill_imputed  # noqa: E402

# ---------------------------------------------------------------------------
# constants and copy
# ---------------------------------------------------------------------------
FIXTURE_IDS = ("NCT99999901", "NCT99999902")
SYNTHETIC_BANNER = "Synthetic calibration: demonstrates the method, not real-world estimates"

BLUE, BLUE_LIGHT = "#2a78d6", "#9cc0ec"
ORANGE = "#eb6834"
RED = "#e34948"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#8a8984"
GRID = "#e6e5e0"

LABELS = {
    "primary_endpoint": "Registered primary endpoint",
    "enrollment": "Enrolment",
    "effect": "Between-group effect, as reported",
    "arm_ns": "Arm sizes (drug / comparator)",
    "g": "Standardised effect g",
    "se_g": "Standard error of g",
    "comparator_type": "Comparator",
    "rater_placement": "Outcome raters",
    "prior_exposure": "Prior psychedelic use",
    "blinding_assessment_planned": "Blinding check planned",
    "guess_acc_participants": "Participants guessing their arm correctly",
    "guess_acc_raters": "Raters guessing the arm correctly",
    "u": "Unblinding u",
    "u_sd": "Uncertainty in u (SD)",
}
ORDER = list(LABELS)
ENUM_TEXT = {
    "inert_placebo": "inert placebo",
    "active_placebo": "active placebo",
    "low_dose_same_drug": "low dose of the same drug",
    "other_active": "another active treatment",
    "waitlist_or_none": "waitlist or no treatment",
    "central_remote": "central, remote and blinded",
    "blinded_unspecified": "blinded, placement not stated",
    "onsite_unblinded": "on site, not blinded",
}
AGENT_TEXT = {
    "orchestrator": "orchestrator",
    "resolver": "resolver",
    "hunter": "paper hunter",
    "outcome": "outcome extractor",
    "design": "design extractor (results-blind)",
    "blinding": "blinding hunter",
    "auditor": "quote auditor",
    "statistician": "statistician (plain code)",
    "advisor": "design advisor",
    "ledger": "ledger",
}

CSS = """
<style>
.block-container {padding-top: 2.2rem; max-width: 1280px;}
.ub-tagline {font-size: 1.15rem; color: #52514e; margin: -0.6rem 0 0.2rem 0;}
.ub-lede {color: #6b6a65; font-size: 0.95rem; max-width: 760px; margin-bottom: 0.4rem;}
.ub-banner {background: #fff4e0; border: 1px solid #f0b24a; border-left: 6px solid #e08a00;
  color: #5a3b00; padding: 0.7rem 1rem; border-radius: 8px; font-weight: 600; margin: 0.4rem 0 0.8rem 0;}
.ub-banner small {display:block; font-weight: 400; color: #7a5a1a; margin-top: 2px;}
.ub-pill {display:inline-block; padding: 0.35rem 0.8rem; border-radius: 999px; font-weight: 700;
  letter-spacing: 0.04em; font-size: 0.85rem;}
.ub-pill.await {background:#fff4e0; color:#8a5300; border:1px solid #f0b24a;}
.ub-pill.approve {background:#e3f5ea; color:#0f6b35; border:1px solid #7fcf9d;}
.ub-pill.reject {background:#fde8e8; color:#9b1c1c; border:1px solid #f1a1a1;}
.ub-pill.needs-changes {background:#fff4e0; color:#8a5300; border:1px solid #f0b24a;}
.ub-chip {display:inline-block; padding: 1px 8px; border-radius: 999px; font-size: 0.75rem; font-weight: 700;
  letter-spacing: 0.03em; text-transform: uppercase; white-space: nowrap;}
.ub-chip.observed {background:#e3f5ea; color:#0f6b35;}
.ub-chip.derived {background:#e4eefb; color:#1d5aa6;}
.ub-chip.imputed {background:#fff1d6; color:#8a5300;}
.ub-chip.unknown {background:#ecebe7; color:#5f5e59;}
.ub-chip.invented {background:#f3e8ff; color:#6b21a8;}
.ub-chip.warn {background:#fff1d6; color:#8a5300;}
.ub-chip.ok {background:#e3f5ea; color:#0f6b35;}
.ub-meta {color:#52514e; font-size: 0.92rem; margin: 0.2rem 0 0.6rem 0;}
.ub-meta b {color: inherit;}
.ub-cards {display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 12px; margin: 0.4rem 0 0.6rem 0;}
@media (max-width: 900px) {.ub-cards {grid-template-columns: repeat(2, minmax(0,1fr));}}
.ub-card {border:1px solid rgba(120,120,110,0.25); border-radius: 10px; padding: 0.75rem 0.9rem;}
.ub-card .k {font-size: 0.8rem; color:#6b6a65; text-transform: uppercase; letter-spacing: 0.04em; font-weight:600;}
.ub-card .v {font-size: 1.9rem; font-weight: 700; line-height: 1.2; margin-top: 2px;}
.ub-card .s {font-size: 0.85rem; color:#52514e; margin-top: 2px;}
.ub-card.main {border: 2px solid #eb6834;}
.ub-sentence {font-size: 1.05rem; margin: 0.2rem 0 0.4rem 0;}
.ub-table {width:100%; border-collapse: collapse; font-size: 0.88rem;}
.ub-table th {text-align:left; font-weight:600; color:#52514e; border-bottom: 2px solid rgba(120,120,110,0.35);
  padding: 6px 8px; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.03em;}
.ub-table td {border-bottom: 1px solid rgba(120,120,110,0.2); padding: 7px 8px; vertical-align: top;}
.ub-table td.f {font-weight: 600; min-width: 150px;}
.ub-table td.f small {display:block; font-weight: 400; color:#8a8984;}
.ub-table td.val {min-width: 130px;}
.ub-quote {font-family: Georgia, 'Times New Roman', serif; border-left: 3px solid rgba(120,120,110,0.35);
  padding-left: 8px; font-style: italic;}
.ub-note {color:#6b6a65; font-size: 0.8rem; margin-top: 3px;}
.ub-src {font-family: ui-monospace, Menlo, monospace; font-size: 0.8rem; overflow-wrap: anywhere;}
.ub-table td.ub-src {min-width: 170px;}
.ub-table td.aud {min-width: 120px;}
.ub-audit-pass {color:#0f6b35; font-weight:600;}
.ub-audit-fail {color:#9b1c1c; font-weight:600;}
.ub-audit-na {color:#8a8984;}
.ub-tr {font-size: 0.86rem; padding: 3px 8px; border-left: 3px solid transparent; margin: 1px 0; border-radius: 3px;}
.ub-tr .a {font-family: ui-monospace, Menlo, monospace; font-size: 0.78rem; color:#6b6a65; margin-right: 6px;}
.ub-tr .d {color:#6b6a65;}
.ub-tr .tag {font-size: 0.68rem; font-weight: 700; letter-spacing: 0.05em; padding: 0 6px; border-radius: 999px; margin-right: 6px;}
.ub-tr.decision {border-left-color:#2a78d6; background: rgba(42,120,214,0.08); font-weight: 600;}
.ub-tr.decision .tag {background:#2a78d6; color:#fff;}
.ub-tr.decision .d {font-weight: 400;}
.ub-tr.warn {border-left-color:#e08a00; background: rgba(240,178,74,0.16);}
.ub-tr.warn .tag {background:#e08a00; color:#fff;}
.ub-tr.error {border-left-color:#c62828; background: rgba(198,40,40,0.10);}
.ub-tr.error .tag {background:#c62828; color:#fff;}
.ub-src-item {padding: 6px 0; border-bottom: 1px solid rgba(120,120,110,0.2); font-size: 0.88rem;}
.ub-src-item .lic {color:#52514e; font-size: 0.82rem;}
.ub-digest {font-family: ui-monospace, Menlo, monospace; font-size: 0.95rem; padding: 2px 6px;
  border-radius: 4px; background: rgba(120,120,110,0.12);}
</style>
"""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def esc(x) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def num(x, nd: int = 2) -> str:
    if x is None:
        return "unknown"
    try:
        return f"{float(x):.{nd}f}"
    except (TypeError, ValueError):
        return esc(x)


def link(url: str, text: str) -> str:
    url = str(url or "")
    if url.startswith(("https://", "http://")):
        return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(text)}</a>'
    return esc(text)


def chip(text: str, cls: str) -> str:
    return f'<span class="ub-chip {esc(cls)}">{esc(text)}</span>'


def is_fixture(nct) -> bool:
    return bool(nct) and str(nct).upper().startswith("NCT999999")


def fact(rep, name: str) -> dict:
    return (rep.facts or {}).get(name) or {}


def fval(rep, name: str):
    f = fact(rep, name)
    return None if f.get("status") == "unknown" else f.get("value")


def is_synthetic(label: str) -> bool:
    return "SYNTHETIC" in (label or "").upper()


def safe(title: str, fn, *args) -> None:
    """A rendering bug in one panel must never take down the page."""
    try:
        fn(*args)
    except Exception as e:  # pragma: no cover - defensive
        st.warning(f"The {title} panel could not be shown ({type(e).__name__}: {e}). The rest of the report is unaffected.")


def event_dict(ev) -> dict:
    if is_dataclass(ev):
        return asdict(ev)
    return dict(ev) if isinstance(ev, dict) else {"agent": "?", "action": str(ev), "detail": "", "level": "info"}


def trace_line(ev: dict) -> str:
    lvl = ev.get("level", "info")
    lvl = lvl if lvl in ("info", "decision", "warn", "error") else "info"
    tag = {"decision": "DECISION", "warn": "WARNING", "error": "ERROR"}.get(lvl, "")
    agent = AGENT_TEXT.get(ev.get("agent", ""), ev.get("agent", ""))
    detail = ev.get("detail") or ""
    return (f'<div class="ub-tr {lvl}"><span class="a">{esc(agent)}</span>'
            + (f'<span class="tag">{tag}</span>' if tag else "")
            + f'{esc(ev.get("action", ""))}'
            + (f' <span class="d">: {esc(detail)}</span>' if detail else "") + "</div>")


# ---------------------------------------------------------------------------
# value formatting for the ledger
# ---------------------------------------------------------------------------
def fmt_value(name: str, v) -> str:
    if v is None:
        return "not found"
    if name == "primary_endpoint" and isinstance(v, dict):
        bits = []
        if v.get("scale"):
            bits.append(str(v["scale"]))
        if v.get("week") is not None:
            bits.append(f"week {v['week']}")
        return ", ".join(bits) or (v.get("measure") or "registered, scale not recognised")
    if name == "effect" and isinstance(v, dict):
        kind = "Mean difference" if v.get("kind") == "md" else "Standardised effect"
        s = f"{kind} {v.get('est')}"
        if v.get("lo") is not None and v.get("hi") is not None:
            s += f" (95% CI {v['lo']} to {v['hi']})"
        return s
    if name == "arm_ns" and isinstance(v, (list, tuple)) and len(v) == 2:
        return f"{v[0]} / {v[1]}"
    if name in ("guess_acc_participants", "guess_acc_raters", "prior_exposure") and isinstance(v, (int, float)):
        return f"{v * 100:.0f}%"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, str):
        return ENUM_TEXT.get(v, v)
    if isinstance(v, float):
        return f"{v:.3g}"
    return str(v)


def fmt_audit(a: str, status: str = "") -> str:
    a = a or ""
    if a == "pass":
        return '<span class="ub-audit-pass">&#10003; quote found word for word</span>'
    if a.startswith("fail"):
        return f'<span class="ub-audit-fail">&#10007; rejected: {esc(a.split(":", 1)[-1])}</span>'
    if status == "unknown":
        return '<span class="ub-audit-na">n/a (nothing found)</span>'
    if status == "imputed":
        return '<span class="ub-audit-na">n/a (imputed, not quoted)</span>'
    return '<span class="ub-audit-na">n/a (computed, not quoted)</span>'


# ---------------------------------------------------------------------------
# calibration data (current corpus)
# ---------------------------------------------------------------------------
def calibration():
    rows, label = model.load_calibration()
    dm = model.design_model(rows)
    rows = fill_imputed([dict(r) for r in rows], dm)
    fit_p = model.fit_metareg(rows, label="primary: observed blinding only")
    fit_s = model.fit_metareg(rows, label="sensitivity: incl. imputed blinding", use_imputed=True)
    return rows, label, dm, fit_p, fit_s


# ---------------------------------------------------------------------------
# panels
# ---------------------------------------------------------------------------
def panel_header(rep) -> None:
    so = st.session_state.signoffs.get(rep.digest())
    if so:
        word = {"approve": "APPROVED", "reject": "REJECTED", "needs-changes": "NEEDS CHANGES"}[so["decision"]]
        pill = f'<span class="ub-pill {esc(so["decision"])}">SIGNED OFF: {word} by {esc(so["reviewer"])}</span>'
    else:
        pill = '<span class="ub-pill await">AWAITING HUMAN SIGN-OFF</span>'
    meta = []
    if rep.title:
        meta.append(f"<b>{esc(rep.title)}</b>")
    if rep.nct:
        meta.append(link(f"https://clinicaltrials.gov/study/{rep.nct}", rep.nct))
    if rep.drug:
        meta.append("Drug: " + esc(", ".join(rep.drug)))
    meta.append(chip("psychedelic trial", "ok") if rep.in_domain else chip("outside fitted domain", "warn"))
    if is_fixture(rep.nct):
        meta.append(chip("INVENTED test trial", "invented"))
    st.html(f'<div>{pill} <span class="ub-meta">&nbsp;Instrument reading, not a verdict.</span></div>'
            f'<div class="ub-meta">{" &middot; ".join(meta)}</div>')
    if not rep.title and not rep.nct:
        st.html(f'<div class="ub-meta">Input: <code>{esc((rep.input or "")[:160])}</code></div>')


def panel_warnings(rep, banner_shown: bool) -> None:
    ws = [w for w in (rep.warnings or []) if not (banner_shown and "SYNTHETIC" in w)]
    for ev in rep.trace or []:
        ev = event_dict(ev)
        act = ev.get("action", "")
        if ev.get("level") != "warn":
            continue
        if "selective reporting" in act:
            ws.append("Blinding agent: a blinding check was planned in the protocol but no result was found anywhere. "
                      "Possible selective reporting.")
        elif act.startswith("REJECTED"):
            ws.append(f"Quote auditor rejected a claim ({act.split(' ', 1)[-1]}): {ev.get('detail', '')}. "
                      "That fact was set to unknown.")
    for w in ws:
        st.warning(w, icon="⚠️")


def panel_headline(rep) -> None:
    st.subheader("Result")
    c = rep.correction
    g, se = fval(rep, "g"), fval(rep, "se_g")
    u, u_st = fval(rep, "u"), fact(rep, "u").get("status")
    u_chip = chip("observed", "observed") if u_st == "derived" else chip("IMPUTED", "imputed")
    u_note = fact(rep, "u").get("note", "")
    if u_st == "derived":
        u_sub = "From the trial's own guess data."
    else:
        u_sub = "Not measured. Estimated from the design, so the interval is wider."

    if c:
        g_lo, g_hi = (g - 1.96 * se, g + 1.96 * se) if (g is not None and se) else (None, None)
        share = ""
        if g and g > 0:
            share = f"{100 * c['bias'] / g:.0f}% of the reported effect."
        extra = (chip("extrapolated", "warn") + " outside the calibration range") if c.get("extrapolated") \
            else chip("within range", "ok") + " of the calibration data"
        st.html(f"""
<div class="ub-cards">
  <div class="ub-card"><div class="k">Reported effect g</div><div class="v">{num(g)}</div>
    <div class="s">95% CI {num(g_lo)} to {num(g_hi)}</div></div>
  <div class="ub-card main"><div class="k">Corrected effect g</div><div class="v">{num(c['corrected'])}</div>
    <div class="s">95% interval {num(c['lo'])} to {num(c['hi'])}</div></div>
  <div class="ub-card"><div class="k">Expectancy bias</div><div class="v">{num(c['bias'])}</div>
    <div class="s">{esc(share)}</div></div>
  <div class="ub-card"><div class="k">Unblinding u &nbsp;{u_chip}</div><div class="v">{num(u)}</div>
    <div class="s">{esc(u_sub)}</div></div>
</div>""")
        lines = [f"The trial reports g = {num(g)}.",
                 f"About {num(c['bias'])} of that is estimated to be expectation.",
                 f"What remains is {num(c['corrected'])}, with a 95% interval of {num(c['lo'])} to {num(c['hi'])}."]
        if c["lo"] <= 0 <= c["hi"]:
            lines.append("That interval includes zero.")
        st.html(f'<div class="ub-sentence">{esc(" ".join(lines))}</div>'
                f'<div class="ub-meta">{extra}. How u was found: {esc(u_note)}</div>')
        st.caption("Read the corrected value as a conservative bound. If patients guessed 'drug' because they "
                   "improved, the correction also removes some real effect. See Limitations.")
    else:
        why = "No correction was possible."
        if fact(rep, "g").get("status") == "unknown" or g is None:
            note = fact(rep, "effect").get("note") or fact(rep, "g").get("note") or ""
            why = ("No between-group effect matching the registered primary endpoint was found, "
                   "so there is no number to correct.")
            m = re.match(r"(\d+) candidates rejected", note)
            if m:
                k = int(m.group(1))
                why += (" No candidate numbers were found in the sources." if k == 0
                        else f" {k} candidate numbers were checked and none matched.")
            elif note:
                why += f" Detail: {note}."
        if not rep.fit_primary and not rep.fit_sensitivity:
            why += " The calibration also had too few trials to fit."
        if not (rep.sources or {}):
            why = "Nothing could be resolved from this input, so there is no trial to correct. Try an NCT ID, a DOI, or paste an abstract."
        st.info(why, icon="ℹ️")
        if u is not None and rep.sources:
            st.html(f'<div class="ub-meta">Unblinding for this design: u = {num(u)} {u_chip}. {esc(u_sub)} '
                    "Design advice below still applies.</div>")


def panel_ledger(rep) -> None:
    st.subheader("Evidence ledger")
    st.caption("Every fact, the exact sentence it came from, and whether the auditor found that sentence word for "
               "word in the cited source. Derived and imputed rows were computed in code. The note says how.")
    facts = rep.facts or {}
    srcs = rep.sources or {}
    names = [n for n in ORDER if n in facts] + [n for n in facts if n not in ORDER]
    counts = {s: sum(1 for n in names if (facts[n] or {}).get("status") == s) for s in ("observed", "derived", "imputed", "unknown")}
    st.html('<div class="ub-meta">' + " ".join(f"{chip(s, s)} {counts[s]}" for s in counts) + "</div>")
    rows = []
    for n in names:
        f = facts[n] or {}
        status = f.get("status", "unknown")
        status = status if status in ("observed", "derived", "imputed", "unknown") else "unknown"
        quote = f.get("quote") or ""
        note = f.get("note") or ""
        qhtml = f'<div class="ub-quote">"{esc(quote)}"</div>' if quote else ""
        if note:
            qhtml += f'<div class="ub-note">{esc(note)}</div>'
        if not qhtml:
            qhtml = '<span class="ub-audit-na">none</span>'
        sid = f.get("source_id") or ""
        s = srcs.get(sid) or {}
        shtml = (link(s.get("url", ""), sid) if s else esc(sid)) if sid else '<span class="ub-audit-na">none</span>'
        agent = AGENT_TEXT.get(f.get("agent", ""), f.get("agent", ""))
        rows.append(
            f'<tr><td class="f">{esc(LABELS.get(n, n))}<small>{esc(n)} &middot; {esc(agent)}</small></td>'
            f'<td class="val">{esc(fmt_value(n, f.get("value")))}</td>'
            f"<td>{chip(status, status)}</td>"
            f"<td>{qhtml}</td>"
            f'<td class="ub-src">{shtml}</td>'
            f"<td class=\"aud\">{fmt_audit(f.get('audit', ''), status)}</td></tr>")
    if not rows:
        st.info("No facts were recorded.")
        return
    st.html('<div style="overflow-x:auto"><table class="ub-table"><thead><tr><th>Field</th><th>Value</th><th>Status</th>'
            '<th>Verbatim quote and note</th><th>Source</th><th>Audit</th></tr></thead><tbody>'
            + "".join(rows) + "</tbody></table></div>")


def panel_chart(rep, cal) -> None:
    rows, label, dm, fit_p, fit_s = cal
    st.subheader("Calibration across trials")
    if is_synthetic(label):
        st.html(f'<div class="ub-meta">{chip("synthetic data", "imputed")} Every calibration point below is a simulated trial.</div>')
    fit = fit_p or fit_s
    if fit is None:
        st.info("Too few calibration trials to fit a line.")
        return
    central = 1.0 if fval(rep, "rater_placement") == "central_remote" else 0.0
    names = fit.names

    def xvec(u):
        return np.array([1.0 if n == "intercept" else (u if n == "u" else (central if n == "central" else 0.0)) for n in names])

    us = np.linspace(0, 1, 101)
    line = np.array([xvec(u) @ np.array([fit.coef[n] for n in names]) for u in us])
    t = model._tcrit(fit.df)
    band = np.array([t * np.sqrt(max(float(xvec(u) @ fit.cov @ xvec(u)), 0.0)) for u in us])

    fig, ax = plt.subplots(figsize=(6.6, 5.0), dpi=110)
    fig.patch.set_facecolor("white")
    umin, umax = fit.u_range
    ax.axvspan(-0.05, umin, color="#f1efe9", zorder=0)
    ax.text(umin / 2 - 0.025, 0.98, "extrapolation", transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=8.5, color=INK_2, style="italic")
    if umax < 1:
        ax.axvspan(umax, 1.03, color="#f1efe9", zorder=0)
        ax.text((umax + 1.03) / 2, 0.98, "extrap.", transform=ax.get_xaxis_transform(), ha="center", va="top",
                fontsize=8.5, color=INK_2, style="italic")

    ax.fill_between(us, line - band, line + band, color=BLUE, alpha=0.13, linewidth=0, zorder=1)
    ax.plot(us, line, color=BLUE, linewidth=2, zorder=2,
            label=f"Primary fit (observed blinding only, k={fit.k}) with 95% band")

    obs = [r for r in rows if r.get("u_status") == "observed" and r.get("g") is not None and r.get("u") is not None]
    imp = [r for r in rows if r.get("u_status") != "observed" and r.get("g") is not None and r.get("u") is not None]
    for grp, filled, lab in ((imp, False, "Calibration trial, blinding imputed"),
                             (obs, True, "Calibration trial, blinding observed")):
        if not grp:
            continue
        x = np.array([float(r["u"]) for r in grp])
        y = np.array([float(r["g"]) for r in grp])
        e = np.array([1.96 * float(r.get("se_g") or 0) for r in grp])
        ax.errorbar(x, y, yerr=e, fmt="none", ecolor=BLUE_LIGHT if filled else "#cfd9e6", elinewidth=1, zorder=2)
        ax.scatter(x, y, s=36, facecolors=BLUE if filled else "white", edgecolors=BLUE, linewidths=1.4,
                   zorder=3, label=lab)

    a0 = float(xvec(0.0) @ np.array([fit.coef[n] for n in names]))
    ax.scatter([0], [a0], marker="D", s=46, color=INK, zorder=5, label=f"Fitted line at u = 0: g = {a0:.2f}")

    c = rep.correction
    g, se, u, usd = fval(rep, "g"), fval(rep, "se_g"), fval(rep, "u"), fval(rep, "u_sd")
    if c and g is not None and u is not None:
        ax.errorbar([u], [g], yerr=[1.96 * (se or 0)], xerr=[1.96 * (usd or 0)], fmt="none", ecolor=ORANGE,
                    elinewidth=1.4, alpha=0.7, zorder=6)
        ax.scatter([u], [g], s=95, color=ORANGE, edgecolors="white", linewidths=1.5, zorder=7,
                   label=f"This trial as reported: g = {g:.2f}")
        ax.errorbar([0.035], [c["corrected"]], yerr=[[c["corrected"] - c["lo"]], [c["hi"] - c["corrected"]]],
                    fmt="s", ms=9, mfc="white", mec=ORANGE, mew=2, ecolor=ORANGE, elinewidth=1.6, capsize=4, zorder=7,
                    label=f"This trial corrected: g = {c['corrected']:.2f}")
        ax.annotate("", xy=(0.06, c["corrected"]), xytext=(u - 0.02, g),
                    arrowprops=dict(arrowstyle="-|>", color=ORANGE, lw=1.6, shrinkA=6, shrinkB=6), zorder=6)

    ax.axhline(0, color=INK_3, linewidth=0.8, zorder=1)
    ax.set_xlim(-0.05, 1.03)
    ax.set_xlabel("Unblinding u  (0 = guessing at chance, 1 = everyone knew)", fontsize=10, color=INK_2)
    ax.set_ylabel("Effect size g  (positive = drug better)", fontsize=10, color=INK_2)
    ax.tick_params(colors=INK_2, labelsize=9.5)
    ax.grid(True, color=GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(INK_3)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=8.5, frameon=False,
              handletextpad=0.4, columnspacing=1.2)
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)
    st.caption(f"Line drawn for {'central, remote' if central else 'on-site'} raters, matching this trial. "
               "Shaded columns mark unblinding levels with no observed calibration trials. Error bars are 95% intervals.")
    if rep.calibration and rep.calibration != label:
        st.warning(f"This report was produced with a different calibration ({rep.calibration}). "
                   "The chart shows the current one; the numbers above are from the report.")

    with st.expander("Fit details"):
        def fit_rows(summary, name):
            if not summary:
                return f"<tr><td>{esc(name)}</td><td colspan='5'>not fitted (too few trials)</td></tr>"
            def cell(k):
                d = summary.get(k)
                return f"{d['est']:.3f} ({d['ci95'][0]:.3f} to {d['ci95'][1]:.3f})" if d else "not in model"
            return (f"<tr><td>{esc(summary.get('label', name))}</td><td>{summary.get('k')}</td><td>{cell('intercept')}</td>"
                    f"<td>{cell('u')}</td><td>{cell('central')}</td><td>{summary.get('tau2')}</td></tr>")
        st.html('<table class="ub-table"><thead><tr><th>Fit</th><th>k</th><th>Intercept a</th>'
                '<th>Slope b (bias per unit u)</th><th>Central raters c</th><th>tau&sup2;</th></tr></thead><tbody>'
                + fit_rows(rep.fit_primary, "primary") + fit_rows(rep.fit_sensitivity, "sensitivity") + "</tbody></table>")
        st.caption(f"Model: g = a + b u + c central, random effects, Knapp-Hartung scaling. Values from this report. "
                   f"Calibration: {rep.calibration}. Imputed blinding comes from: {rep.design_model}.")


def panel_advice(rep) -> None:
    st.subheader("Design advice")
    cfs = rep.counterfactuals or []
    if not cfs:
        msg = ("Nothing was resolved from this input, so there is no design to advise on."
               if not rep.sources else "No design changes could be ranked for this trial.")
        st.info(msg)
        return
    st.caption("Expected change in bias if the trial changed one thing. Ranked by bias reduction times feasibility.")
    vals = [float(c["bias_reduction"]) for c in cfs]
    n = len(cfs)
    fig, ax = plt.subplots(figsize=(6.4, 0.78 * n + 0.85), dpi=110)
    fig.patch.set_facecolor("white")
    y = np.arange(n)[::-1].astype(float)
    span = max(0.05, max(abs(v) for v in vals))
    lo = min(0.0, min(vals)) - (span * 0.95 if min(vals) < 0 else span * 0.05)
    hi = max(0.0, max(vals)) + (span * 0.55 if max(vals) > 0 else span * 0.05)
    ax.barh(y, vals, color=[BLUE if v > 0 else RED for v in vals], height=0.36, zorder=2)
    for i, (yi, v, c) in enumerate(zip(y, vals, cfs)):
        ax.text(0.0, yi + 0.26, f"{i + 1}. {c['change']}", transform=ax.get_yaxis_transform(),
                ha="left", va="bottom", fontsize=9.5, color=INK)
        if v > 0:
            ax.text(v + span * 0.03, yi, f"{v:+.3f}", va="center", ha="left", fontsize=9, color=INK)
        elif v < 0:
            ax.text(v - span * 0.03, yi, f"{v:+.3f}  would increase bias", va="center", ha="right",
                    fontsize=9, color="#9b1c1c")
        else:
            ax.text(span * 0.03, yi, "no change", va="center", ha="left", fontsize=9, color=INK_2)
    ax.set_ylim(-0.5, n - 0.2)
    ax.set_xlim(lo, hi)
    ax.set_yticks([])
    ax.axvline(0, color=INK_3, linewidth=1, zorder=3)
    ax.set_xlabel("Expected bias reduction (g units). Right is better.", fontsize=9, color=INK_2)
    ax.tick_params(axis="x", colors=INK_2, labelsize=8.5)
    ax.grid(True, axis="x", color=GRID, linewidth=0.7, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_3)
    fig.tight_layout()
    st.pyplot(fig, clear_figure=True)
    plt.close(fig)

    if all(v <= 0 for v in vals):
        st.info("None of the modelled changes is predicted to reduce bias for this design.")
    top = cfs[0]
    st.html(
        '<table class="ub-table"><thead><tr><th>#</th><th>Change</th><th>Bias now</th><th>Bias after</th>'
        "<th>Feasibility (team assumption)</th><th>Score</th></tr></thead><tbody>"
        + "".join(f"<tr><td>{i + 1}</td><td>{esc(c['change'])}</td><td>{num(c['expected_bias_before'], 3)}</td>"
                  f"<td>{num(c['expected_bias_after'], 3)}</td><td>{num(c['feasibility_weight'])}</td>"
                  f"<td>{num(c['score'], 3)}</td></tr>" for i, c in enumerate(cfs))
        + "</tbody></table>")
    st.caption("Feasibility weights are team assumptions, not data. They are subjective scores from 0 to 1 "
               f"in data/priors.json and can be edited. Top ranked: {top['change']}.")


def panel_sources(rep) -> None:
    st.subheader("Sources")
    srcs = rep.sources or {}
    if not srcs:
        st.info("No sources were fetched.")
        return
    items = []
    for sid, s in srcs.items():
        title = s.get("title") or sid
        items.append(f'<div class="ub-src-item"><span class="ub-src">{esc(sid)}</span> {chip(s.get("kind", ""), "unknown")}<br>'
                     f'{link(s.get("url", ""), title)} <span class="ub-note">({esc(s.get("chars", 0))} characters read)</span>'
                     f'<div class="lic">Licence: {esc(s.get("licence", "not stated"))}</div></div>')
    st.html("".join(items))


def panel_limits(rep) -> None:
    st.subheader("Limitations")
    with st.expander("What this tool cannot tell you", expanded=True):
        for lim in rep.limitations or pipeline.LIMITATIONS:
            st.markdown(f"- {lim}")


def panel_trace(trace, title: str = "Agent trace") -> None:
    trace = [event_dict(e) for e in (trace or [])]
    nd = sum(1 for e in trace if e.get("level") == "decision")
    nw = sum(1 for e in trace if e.get("level") in ("warn", "error"))
    with st.expander(f"{title}: {len(trace)} steps, {nd} decisions, {nw} warnings", expanded=False):
        st.caption("Blue rows are decisions, where an agent chose its next step. Amber rows are warnings.")
        st.html("".join(trace_line(e) for e in trace) or "<i>No steps recorded.</i>")


def corpus_eligibility(rep):
    if not rep.nct:
        return False, "the report has no registered trial ID"
    if is_fixture(rep.nct):
        return False, "this is an INVENTED test trial"
    if not rep.in_domain:
        return False, "no psychedelic intervention was detected"
    if fval(rep, "g") is None or fval(rep, "se_g") is None:
        return False, "there is no effect size to add"
    return True, ""


def panel_signoff(rep) -> None:
    st.subheader("Human sign-off")
    dig = rep.digest()
    so = st.session_state.signoffs.get(dig)
    st.html(f'<div class="ub-meta">Report fingerprint <span class="ub-digest">{esc(dig)}</span>. '
            "Any later change to the facts, the correction or the advice changes this fingerprint.</div>")
    if so:
        word = {"approve": "Approved", "reject": "Rejected", "needs-changes": "Needs changes"}[so["decision"]]
        msg = f"{word} by {so['reviewer']} at {so['time']}."
        if so.get("comment"):
            msg += f" Comment: {so['comment']}"
        if so.get("added_to_corpus"):
            msg += " Added to the real calibration corpus."
        if so["decision"] == "approve":
            st.success(msg)
        else:
            st.warning(msg)
    else:
        st.html('<span class="ub-pill await">AWAITING HUMAN SIGN-OFF</span>')
        st.caption("Nothing leaves UNBLIND as a recommendation, and nothing joins the calibration corpus, "
                   "until a named person signs here. Decisions are logged to data/signoffs.jsonl with the fingerprint.")
        c1, c2 = st.columns([1, 1])
        with c1:
            reviewer = st.text_input("Reviewer name (required)", key=f"rev_{dig}")
            decision = st.radio("Decision", ["approve", "needs-changes", "reject"], horizontal=True, key=f"dec_{dig}",
                                format_func=lambda d: {"approve": "Approve", "needs-changes": "Needs changes",
                                                       "reject": "Reject"}[d])
        with c2:
            comment = st.text_area("Comment", key=f"com_{dig}", height=100)
        ok, why = corpus_eligibility(rep)
        allowed = ok and decision == "approve"
        add = st.checkbox("Add to calibration corpus", key=f"add_{dig}", disabled=not allowed, value=False,
                          help="Only for approved reports of real, registered psychedelic trials with an effect size.")
        if not ok:
            st.caption(f"Cannot add to the corpus: {why}.")
        elif decision != "approve":
            st.caption("Only approved reports can join the corpus.")
        elif fact(rep, "u").get("status") != "derived":
            st.caption("Blinding was imputed, so this row would join with blinding marked missing and feed only the sensitivity fit.")
        if st.button("Record sign-off", type="primary", key=f"sign_{dig}"):
            if not reviewer.strip():
                st.error("Please enter the reviewer's name.")
            else:
                try:
                    entry = signoff.record(rep, reviewer, decision, comment, add_to_corpus=bool(add and allowed))
                    st.session_state.signoffs[dig] = entry
                    st.rerun()
                except Exception as e:
                    st.error(f"The sign-off could not be saved ({type(e).__name__}: {e}).")

    out = asdict(rep)
    if so:
        out["signoff"] = so
        out["status"] = f"SIGNED OFF ({so['decision']}) by {so['reviewer']} at {so['time']}"
    out["digest"] = dig
    st.download_button("Download report JSON", data=json.dumps(out, indent=2, default=str),
                       file_name=f"unblind_{rep.nct or 'report'}_{dig}.json", mime="application/json")


# ---------------------------------------------------------------------------
# loading a saved report
# ---------------------------------------------------------------------------
def report_from_json(raw: bytes):
    d = json.loads(raw.decode("utf-8"))
    if not isinstance(d, dict):
        raise ValueError("file is not a JSON object")
    names = {f.name for f in fields(pipeline.Report)}
    extra = {k: d.pop(k) for k in list(d) if k not in names}
    missing = [f.name for f in fields(pipeline.Report)
               if f.name not in d and f.name not in ("limitations", "status")]
    if missing:
        raise ValueError("missing fields: " + ", ".join(missing))
    rep = pipeline.Report(**d)
    return rep, extra


# ---------------------------------------------------------------------------
# page
# ---------------------------------------------------------------------------
st.set_page_config(page_title="UNBLIND", page_icon="🔬", layout="wide")
st.html(CSS)
ss = st.session_state
for k, v in (("report", None), ("trace", []), ("run_error", None), ("signoffs", {}), ("loaded_id", None),
             ("query", ""), ("origin", None)):
    if k not in ss:
        ss[k] = v
if "offline" not in ss:
    ss.offline = net.offline()


def _fixture_demo():
    try:
        from tests import fixtures
        fixtures.seed()
        ss.offline = True
        ss.query = "NCT99999901"
        ss.fixture_msg = "Fixtures loaded. Offline mode is on. Press Run."
    except Exception as e:
        ss.fixture_msg = f"Could not load fixtures ({type(e).__name__}: {e})."


# ---- sidebar ----------------------------------------------------------------
with st.sidebar:
    st.markdown("### Mode")
    st.toggle("Offline mode (cached responses only)", key="offline",
              help="When on, UNBLIND replays only responses already in its cache and makes no network calls.")
    if ss.offline:
        os.environ["UNBLIND_OFFLINE"] = "1"
    else:
        os.environ.pop("UNBLIND_OFFLINE", None)
    gem = llm.available()
    st.html(f'<div class="ub-meta">Gemini extraction: <b>{"on (" + esc(llm.model_name()) + ")" if gem else "off"}</b><br>'
            + ("Agents read with Gemini, then every claim is quote-checked in code."
               if gem else "Agents use deterministic rules. Every claim is still quote-checked.")
            + f'<br>Network: <b>{"offline, cache only" if ss.offline else "online, allowlisted hosts only"}</b>'
            f'<br><span class="ub-note">Cache: {esc(net.CACHE_DIR)}</span></div>')

    st.markdown("### Fixture demo")
    st.button("Load fixture demo", on_click=_fixture_demo, use_container_width=True)
    st.caption("Seeds two INVENTED test trials, NCT99999901 and NCT99999902, and turns on offline mode. "
               "They do not exist. Use them to show the method with no internet.")
    if ss.get("fixture_msg"):
        if ss.fixture_msg.startswith("Fixtures"):
            st.success(ss.fixture_msg)
        else:
            st.error(ss.fixture_msg)

    st.markdown("### Review a saved report")
    up = st.file_uploader("Load saved report JSON", type=["json"],
                          help="For reports made with `python -m unblind build-corpus`.")
    if up is not None:
        fid = f"{up.name}:{up.size}"
        if fid != ss.loaded_id:
            try:
                rep_l, extra = report_from_json(up.getvalue())
                ss.report, ss.trace, ss.run_error, ss.origin = rep_l, rep_l.trace, None, f"file {up.name}"
                if isinstance(extra.get("signoff"), dict) and extra["signoff"].get("decision"):
                    ss.signoffs[rep_l.digest()] = extra["signoff"]
                if extra.get("digest") and extra["digest"] != rep_l.digest():
                    ss.digest_mismatch = True
                else:
                    ss.digest_mismatch = False
                ss.loaded_id = fid
                st.success(f"Loaded {up.name}.")
            except Exception as e:
                ss.loaded_id = fid
                st.error(f"That file is not a valid UNBLIND report ({type(e).__name__}: {e}).")

    st.markdown("### How it works")
    st.caption("Resolver, paper hunter, outcome extractor, results-blind design extractor and blinding hunter collect "
               "about seven facts. A code auditor checks every quote. A statistician in plain code fits the "
               "calibration and corrects the effect. A design advisor ranks fixes. A human signs off.")

# ---- header -----------------------------------------------------------------
st.title("UNBLIND")
st.html('<div class="ub-tagline">How much of a psychedelic trial\'s result is expectation?</div>'
        '<div class="ub-lede">Patients in psychedelic trials usually know whether they got the drug. UNBLIND reads a '
        "trial, measures how badly blinding failed, and estimates how much of the reported effect is expectation. "
        "A person signs off every result.</div>")

try:
    CAL = calibration()
except Exception as e:  # pragma: no cover - defensive
    CAL = None
    st.error(f"Calibration data could not be loaded ({type(e).__name__}: {e}).")
banner = bool(CAL and is_synthetic(CAL[1])) or bool(ss.report and is_synthetic(ss.report.calibration))
if banner:
    st.html(f'<div class="ub-banner">{SYNTHETIC_BANNER}'
            "<small>The calibration trials are simulated. Real trials join only after a person approves them.</small></div>")

# ---- input ------------------------------------------------------------------
st.text_area("Trial", key="query", height=96, label_visibility="collapsed",
             placeholder="Paste an NCT ID, DOI, PMID, PMCID, an abstract, or describe the trial in words")
cA, cB = st.columns([1, 6])
run_clicked = cA.button("Run", type="primary", use_container_width=True)
cB.caption("Examples: NCT99999901 or NCT99999902 (INVENTED fixtures, use the sidebar button first), "
           "a real NCT ID, a DOI such as 10.1056/..., or a pasted abstract.")

just_ran = False
if run_clicked:
    q = (ss.query or "").strip()
    if not q:
        st.info("Type or paste something first. An NCT ID is the quickest.")
    else:
        just_ran = True
        events: list = []
        ss.run_error = None
        with st.status("Agents at work", expanded=True) as status:
            st.caption("Blue rows are decisions, where an agent chose its next step. Amber rows are warnings.")
            box = st.container()

            def on_event(ev):
                d = event_dict(ev)
                events.append(d)
                box.html(trace_line(d))

            try:
                rep = pipeline.run(q, on_event=on_event)
                ss.report, ss.trace, ss.origin = rep, events, "run"
                nd = sum(1 for e in events if e.get("level") == "decision")
                status.update(label=f"Done: {len(events)} steps, {nd} decisions", state="complete", expanded=False)
            except Exception as e:
                ss.report, ss.trace = None, events
                ss.run_error = f"{type(e).__name__}: {e}"
                status.update(label="Run stopped before the end", state="error", expanded=True)

# ---- results ----------------------------------------------------------------
if ss.run_error:
    st.error("Something went wrong while reading this trial. Nothing was saved and nothing was signed. "
             "The steps completed before the problem are shown below.")
    with st.expander("Technical detail"):
        st.code(ss.run_error)
    if not just_ran:
        panel_trace(ss.trace, "Steps completed")

rep = ss.report
if rep is not None:
    st.divider()
    if ss.origin and ss.origin.startswith("file"):
        st.caption(f"Reviewing a saved report ({ss.origin[5:]}).")
        if ss.get("digest_mismatch"):
            st.error("The fingerprint stored in this file does not match its contents. It may have been edited.")
    safe("header", panel_header, rep)
    safe("warnings", panel_warnings, rep, banner)
    safe("result", panel_headline, rep)
    if not just_ran:
        safe("trace", panel_trace, ss.trace)
    safe("evidence ledger", panel_ledger, rep)
    left, right = st.columns([1.15, 1], gap="large")
    with left:
        if CAL:
            safe("calibration chart", panel_chart, rep, CAL)
    with right:
        safe("design advice", panel_advice, rep)
    left2, right2 = st.columns([1, 1], gap="large")
    with left2:
        safe("sources", panel_sources, rep)
    with right2:
        safe("limitations", panel_limits, rep)
    st.divider()
    safe("sign-off", panel_signoff, rep)
elif not ss.run_error and not just_ran:
    st.caption("Results, the evidence ledger, the calibration chart and design advice appear here after a run.")
