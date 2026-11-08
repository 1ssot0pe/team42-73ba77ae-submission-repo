"""The master exposes the simulator's planted drift onset read-only, labelled simulated (visuals spec R2).

It must report the planted day even after remote raters are approved (the world overwrites cfg.drift_day then),
never reveal it before the clock reaches it, never act as an oracle while a drift approval is pending (review S-1,
S-2), never write it into the record, and change nothing else.
"""
import copy
import json
import os
import pickle

os.environ["UNBLIND_NO_LLM"] = "1"

from unblind.platform.dosing.eval_drift import DRIFT_DAY, DRIFT_SITE, NEVER, EvalPredose, run_trial  # noqa: E402
from unblind.platform.world import WorldConfig  # noqa: E402
from unblind.platform.master.orchestrator import Master  # noqa: E402

SEED = 4


def test_drift_onset_survives_the_approved_action():
    m = run_trial(SEED, drift=True, approve=True)
    assert m.world.cfg.drift_day == NEVER          # the world switched the drift off after approval
    truth = m.state()["simulated_truth"]
    assert truth == {"synthetic": True, "label": "simulated", "drift_site": DRIFT_SITE, "drift_onset_day": DRIFT_DAY}


def test_no_truth_when_no_drift_was_planted():
    m = run_trial(SEED, drift=False, approve=False)
    assert m.state()["simulated_truth"] is None


def manual_trial(tid):
    """The eval harness cohort with manual approvals, stepped by the test."""
    m = Master(tid, seed=SEED, world_cfg=WorldConfig(seed=SEED, drift_day=DRIFT_DAY), auto_approve=False)
    m.modules["predose"], m.module_status["predose"] = EvalPredose(24, 2), "eval harness"
    m.rec.save = lambda: None
    m.setup()
    return m


def pending_drift(m):
    """Step until the planted site's drift alert is raised; return it (approval still pending)."""
    while m.rec["day"] < 89:
        al = [a for a in m.rec["alerts"] if a.get("kind") == "rater_drift" and a["site"] == DRIFT_SITE]
        if al:
            return al[-1]
        m.step(1)
    raise AssertionError("no drift alert")


def test_truth_is_hidden_before_the_onset_day():
    m = manual_trial("TEST-MV-EARLY")
    m.run_to(DRIFT_DAY - 1)
    assert m.state()["simulated_truth"] is None


def test_truth_is_withheld_while_the_drift_approval_is_pending():
    m = manual_trial("TEST-MV-PEND")
    a = pending_drift(m)
    assert a["status"] == "open" and m.ctx.approvals.get(a["approval_id"])["status"] == "pending"
    assert m.rec["day"] >= DRIFT_DAY
    assert m.state()["simulated_truth"] is None
    m.decide(a["approval_id"], "Dr Test", "approved")
    truth = m.state()["simulated_truth"]
    assert truth and truth["drift_site"] == DRIFT_SITE and truth["drift_onset_day"] == DRIFT_DAY


def test_truth_after_a_rejection():
    m = manual_trial("TEST-MV-REJ")
    a = pending_drift(m)
    m.decide(a["approval_id"], "Dr Test", "rejected", "want more data")
    assert m.state()["simulated_truth"]["drift_onset_day"] == DRIFT_DAY


def test_truth_after_close_even_without_a_decision():
    m = run_trial(SEED, drift=True, approve=False)
    assert m.rec["phase"] == "closed"
    assert m.state()["simulated_truth"]["drift_onset_day"] == DRIFT_DAY


def test_exposure_stores_nothing_and_changes_nothing():
    m = manual_trial("TEST-MV-PURE")
    a = pending_drift(m)
    m.decide(a["approval_id"], "Dr Test", "approved")
    before = copy.deepcopy(dict(m.rec))
    cfg_before = copy.deepcopy(m.world.cfg)
    for _ in range(3):
        m.state()
        m.simulated_truth()
    assert dict(m.rec) == before
    assert m.world.cfg == cfg_before
    assert "drift_onset_day" not in json.dumps(dict(m.rec), default=str)


def test_snapshot_round_trip_and_old_snapshots():
    m = run_trial(SEED, drift=False, approve=False)       # no lambdas on the record, so it pickles
    del m.rec.__dict__["save"]                            # the harness's in-memory save hook cannot be pickled
    m._planted_drift_day = DRIFT_DAY                      # as if drift had been planted; the trial is closed
    back = pickle.loads(pickle.dumps(m))
    assert back.state()["simulated_truth"] == m.state()["simulated_truth"] is not None
    del back.__dict__["_planted_drift_day"]               # a snapshot saved before the field existed
    back.world.cfg.drift_day = DRIFT_DAY
    assert back.simulated_truth()["drift_onset_day"] == DRIFT_DAY
