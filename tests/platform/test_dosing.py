"""Offline tests for the dosing module (SYNTHETIC). Run: python -m pytest tests/platform -q

Uses the real Master, World, Vault and ApprovalQueue. Pre-dosing is the labelled
evaluation harness from eval_drift.py so the cohort size is fixed. False-alarm
and delay rates are measured over 20 seeds in eval_drift.py; these tests use one
typical seed (alert on day 43, no false alarm).
"""
import json
import os
import re
from pathlib import Path

import pytest

os.environ["UNBLIND_NO_LLM"] = "1"

from unblind.platform.dosing import stats  # noqa: E402
from unblind.platform.dosing.eval_drift import DRIFT_SITE, run_trial  # noqa: E402
from unblind.platform.dosing.parsing import parse_checkin, parse_debrief  # noqa: E402
from unblind.platform.master.orchestrator import Master  # noqa: E402

SEED = 4
DOSING = Path(__file__).resolve().parents[2] / "unblind" / "platform" / "dosing"


@pytest.fixture(scope="module")
def drift_pending():
    return run_trial(SEED, drift=True, approve=False)


@pytest.fixture(scope="module")
def drift_approved():
    return run_trial(SEED, drift=True, approve=True)


@pytest.fixture(scope="module")
def no_drift():
    return run_trial(SEED, drift=False, approve=False)


def drift_alerts(m, site=None):
    return [a for a in m.rec["alerts"] if a.get("kind") == "rater_drift" and (site is None or a["site"] == site)]


# ------------------------------------------------------------------ contract
def test_master_loads_real_dosing_module():
    m = Master("TEST-DOS-LOAD", use_stub_predose=True)
    assert m.module_status["dosing"] == "real"


def test_agents_never_touch_allocation_or_world_internals():
    bad = re.compile(r"(?<![A-Za-z0-9])_arm\b|_alloc|world\._|world\.cfg|world\.people|world\.v\b|\.v\._|_hidden_exclusion")
    offenders = []
    for p in DOSING.glob("*.py"):
        if p.name == "eval_drift.py":  # evaluation harness reads the planted truth to score agents; agents never do
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if bad.search(line):
                offenders.append(f"{p.name}:{i}: {line.strip()}")
    assert not offenders, offenders


def test_record_never_contains_allocation(drift_approved):
    blob = json.dumps(drift_approved.rec, default=str)
    assert '"arm"' not in blob and '"_arm"' not in blob


def test_event_levels_follow_contract(drift_approved):
    levels = {e["level"] for e in drift_approved.rec["events"] if e["module"] == "dosing"}
    assert levels <= {"info", "decision", "warn", "human"}, levels


def test_rows_follow_contract_shapes(drift_approved):
    rec = drift_approved.rec
    o = rec["outcomes"][0]
    assert {"participant", "site", "day", "visit_week", "madrs", "rater_id", "rater_guess", "patient_guess"} <= set(o)
    c = rec["checkins"][0]
    assert {"participant", "site", "day", "who", "rater_id", "guess", "confidence", "expectancy", "channel"} <= set(c)
    assert all(x["guess"] in ("drug", "control", "dont_know") for x in rec["checkins"])
    b = rec["blinding_metrics"][0]
    assert {"day", "who", "by", "group", "n", "accuracy", "accuracy_lo", "accuracy_hi", "u", "bang_drug", "suppressed"} <= set(b)
    a = drift_alerts(drift_approved)[0]
    assert {"id", "day", "module", "severity", "title", "explanation", "evidence", "approval_id"} <= set(a)
    assert a["severity"] in ("info", "warn", "critical")
    assert {6} <= {x["visit_week"] for x in rec["outcomes"]}


def test_view_and_kpis_follow_view_model(drift_approved):
    m = drift_approved
    v = m.module_view("dosing")
    assert set(v) <= {"module", "title", "kpis", "cards", "charts", "tables", "forms", "status"}
    assert v["module"] == "dosing" and v["status"] == "real"
    assert any("SYNTHETIC" in c["title"] for c in v["charts"]) and all(c["data"] for c in v["charts"])
    for k in v["kpis"]:
        assert {"label", "value", "baseline", "unit", "note", "bottleneck_id"} <= set(k)
    assert v["cards"][0]["title"]  # opens with a bottleneck
    json.dumps(v)  # JSON-able


def test_charts_are_complete(drift_approved):
    """Every chart has one row per day from 1 to today, and every row carries every series key."""
    m = drift_approved
    v = m.module_view("dosing")
    titles = [c["title"] for c in v["charts"]]
    assert any("by site" in t for t in titles) and any("by rater" in t for t in titles)
    for c in v["charts"]:
        keys = [s["key"] for s in c["series"]]
        assert [d["day"] for d in c["data"]] == list(range(1, m.rec["day"] + 1)), c["title"]
        assert all(set(keys) <= set(d) for d in c["data"]), c["title"]
        assert any(d[k] is not None for d in c["data"] for k in keys), c["title"]
    rater = next(c for c in v["charts"] if "by site, last 3" in c["title"])
    labels = [mk["label"] for mk in rater["markers"]]
    assert any("onset" in x for x in labels) and any("Alert" in x for x in labels)
    cus = next(c for c in v["charts"] if "CUSUM" in c["title"])
    alert = drift_alerts(m, DRIFT_SITE)[0]
    peak = next(d for d in cus["data"] if d["day"] == alert["day"])
    assert peak["Site B"] >= stats.H, "the alarm crossing must stay visible on the alert day"
    assert next(d for d in cus["data"] if d["day"] == alert["action_day"] + 1)["Site B"] == 0.0
    tl = next(t for t in v["tables"] if t["title"].startswith("Drift timeline"))
    assert [r[0] for r in tl["rows"]] == sorted(r[0] for r in tl["rows"]) and len(tl["rows"]) >= 3


# ------------------------------------------------------------------ security
def test_monitor_windows_disjoint_and_at_least_five(drift_pending):
    rows = [r for r in drift_pending.rec["blinding_metrics"] if r.get("module") == "dosing"]
    assert rows
    by: dict = {}
    for r in rows:
        by.setdefault((r["who"], r["by"], r["group"]), []).append(r)
    for key, bs in by.items():
        assert all(b["window_n"] >= 5 for b in bs), key
        for prev, nxt in zip(bs, bs[1:]):
            assert nxt["window_from"] == prev["window_to"] + 1, key


def test_vault_access_is_logged(drift_pending):
    assert any(e["who"] == "dosing.blinding_monitor" for e in drift_pending.vault.access_log)


# ------------------------------------------------------------------ detection
def test_drift_fires_after_day_28_at_site_b(drift_pending):
    al = drift_alerts(drift_pending)
    assert al and all(a["site"] == DRIFT_SITE for a in al)
    a = al[0]
    assert a["day"] > 28 and a["status"] == "open"
    ev = a["evidence"]
    assert ev["cusum"] >= stats.H and ev["ci_since_onset"][0] > stats.P0
    assert abs(ev["onset_day_estimate"] - 28) <= 7
    assert "95% interval" in a["explanation"] and "Likely cause" in a["explanation"]
    assert any(m["kind"] == "rater_drift" and m["from"] == "drift_action_agent" for m in drift_pending.rec["messages"])


def test_no_drift_alert_when_drift_disabled(no_drift):
    assert drift_alerts(no_drift) == []


def test_participant_unblinding_is_information_only(drift_pending):
    info = [a for a in drift_pending.rec["alerts"] if a.get("kind") == "participant_unblinding"]
    assert info and all(a["severity"] == "info" and a["approval_id"] is None for a in info)


# ------------------------------------------------------------------ human gate
def test_approval_required_before_action(drift_pending):
    m = drift_pending
    a = drift_alerts(m)[0]
    assert m.ctx.approvals.get(a["approval_id"])["status"] == "pending"
    assert not [x for x in m.rec["actions"] if x.get("type") == "remote_raters"]


def test_after_approval_drift_stops(drift_approved):
    m = drift_approved
    al = drift_alerts(m, DRIFT_SITE)
    assert len(al) == 1 and al[0]["status"] == "resolved"
    act = [x for x in m.rec["actions"] if x["type"] == "remote_raters"]
    assert act and act[0]["reviewer"] and "remote" in act[0]["effect"]
    assert al[0]["post_action"]["accuracy"] < 0.75


def test_rejection_dismisses_and_changes_nothing():
    m = run_trial(SEED, drift=True, approve=False)
    a = drift_alerts(m)[0]
    m.decide(a["approval_id"], "Dr Test Reviewer", "rejected", "want more data first")
    assert a["status"] == "dismissed"
    assert not [x for x in m.rec["actions"] if x.get("type") == "remote_raters"]
    with pytest.raises(ValueError):
        m.ctx.approvals.decide(a["approval_id"], "  ", "approved")


# ------------------------------------------------------------------ data flow
def test_primary_lock_posts_once(drift_approved):
    msgs = [x for x in drift_approved.rec["messages"] if x["kind"] == "primary_locked"]
    assert len(msgs) == 1 and msgs[0]["to"] == "master"
    assert drift_approved.rec["primary_lock_day"] == msgs[0]["day"]


def test_missing_data_is_chased(drift_approved):
    md = drift_approved.rec["missing_data"]
    assert md and {"recovered", "lost"} & {m["status"] for m in md}
    k = drift_approved.modules["dosing"].kpis(drift_approved.rec)
    assert next(x for x in k if x["label"] == "Blinding check-ins completed")["value"] > 90


def test_everything_synthetic(drift_approved):
    for s in ("sessions", "checkins", "debriefs", "outcomes", "blinding_metrics"):
        rows = drift_approved.rec[s]
        assert rows and all(r.get("synthetic") for r in rows), s


# ------------------------------------------------------------------ judge input and parsers
def test_play_a_patient():
    m = Master("TEST-DOS-JUDGE", use_stub_predose=True)
    m.setup()
    m.run_to(5)
    pid = m.rec["enrolled"][0]["id"]
    r = m.module_action("dosing", "checkin", {"participant": pid, "answer": "no clue honestly"})
    assert r["ok"] is False and r["needs_reask"] and "0 to 10" in r["message"]
    r = m.module_action("dosing", "checkin", {"participant": pid, "answer": "I think it was the placebo, 70%, expect 4/10"})
    assert r["ok"] and r["checkin"]["guess"] == "control" and r["checkin"]["judge_input"]
    r = m.module_action("dosing", "checkin", {"participant": pid, "guess": "drug", "confidence": "80", "expectancy": "7"})
    assert r["ok"] and r["checkin"]["expectancy"] == 7
    assert m.module_action("dosing", "checkin", {"participant": "NOPE", "guess": "drug"})["ok"] is False


@pytest.mark.parametrize("text,guess,conf,exp", [
    ("I think I got the real drug. Confidence 80%. Expectancy 7/10.", "drug", 80, 7),
    ("placebo I reckon. Confidence 60%. Expectancy 3/10.", "control", 60, 3),
    ("I genuinely don't know. Expectancy 5/10.", "dont_know", 0, 5),
])
def test_parse_checkin(text, guess, conf, exp):
    p = parse_checkin(text)
    assert (p["guess"], p["confidence"], p["expectancy"], p["missing"]) == (guess, conf, exp, [])


def test_parse_debrief_on_world_text():
    d = parse_debrief("Participant was tearful and described a 'profound' experience. Blood pressure rose to 150/95 at 2 hours, "
                      "settled by 4 hours. Outcome rater came into the room briefly during the session.")
    assert {a["term"] for a in d["adverse_events"]} == {"raised blood pressure"}
    assert d["unblinding_cues"][0]["type"] == "rater_contact"
    s = parse_debrief("Participant disclosed suicidal thoughts during integration. They said it was of great benefit.")
    assert [a["term"] for a in s["adverse_events"]] == ["suicidal ideation"] and s["adverse_events"][0]["serious"]
