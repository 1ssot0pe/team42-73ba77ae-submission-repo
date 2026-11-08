"""Predose view: design_history rescoring is read only and matches the audit table."""
import copy
import uuid

import pytest

from unblind.platform.master.orchestrator import Master

FIX_ORDER = ["central_raters", "blinding_questionnaire", "expectancy_measure", "alternative_control",
             "stratify_prior_use"]


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    monkeypatch.setenv("UNBLIND_OFFLINE", "1")   # rule-based path only; no Gemini calls in tests
    monkeypatch.setenv("UNBLIND_STORE_DIR", str(tmp_path))


def _trial(fixes=FIX_ORDER):
    m = Master("TEST-" + uuid.uuid4().hex[:6], seed=42, n_applicants=500)
    m.setup()
    for fid in fixes:
        a = next(a for a in m.rec["approvals"] if a["status"] == "pending"
                 and (a.get("action") or {}).get("fix") == fid)
        m.decide(a["id"], "Dr Test", "approved")
    return m


def test_single_version_history_is_the_stored_risk():
    m = _trial(fixes=[])
    h = m.module_view("predose")["design_history"]
    assert len(h) == 1 and h[0]["source"] == "stored"
    assert h[0]["u"] == m.rec["design_review"]["risk"]["u"]


def test_history_rescores_every_version_without_touching_the_record():
    m = _trial()
    before = copy.deepcopy(dict(m.rec))
    h = m.module_view("predose")["design_history"]
    assert dict(m.rec) == before, "view() must not mutate the record"
    assert len(h) == len(m.rec["protocol_versions"]) == 6
    assert [r["version"] for r in h] == [1, 2, 3, 4, 5, 6]
    assert [r["source"] for r in h] == ["stored"] + ["rescored"] * 4 + ["stored"]
    assert [r["fix"] for r in h] == [None] + FIX_ORDER
    # the audit table (docs/testing/visuals/audit-trial.md, chart 1)
    assert [r["u"] for r in h] == pytest.approx([0.786, 0.786, 0.786, 0.786, 0.570, 0.550], abs=1e-3)
    assert [r["expected_bias_g"] for r in h] == pytest.approx([0.705, 0.674, 0.674, 0.674, 0.489, 0.472], abs=1e-3)
    assert [r["band"] for r in h] == ["high"] * 4 + ["medium"] * 2
    assert h[0]["u"] == m.rec["design_review"]["baseline_risk"]["u"]
    assert h[-1]["u"] == m.rec["design_review"]["risk"]["u"]
    # the rescored last version agrees with the stored one (no gap in this walk)
    p = m.modules["predose"]
    again = p.codesigner.risk(p.parser._rules(m.rec["protocol_versions"][-1]["text"]))
    assert again["u"] == h[-1]["u"] and again["expected_bias_g"] == h[-1]["expected_bias_g"]
    assert all(r["u_sd"] is not None for r in h)
