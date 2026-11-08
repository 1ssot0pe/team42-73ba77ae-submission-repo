"""The master exposes the simulator's planted drift onset read-only, labelled simulated (visuals spec R2).

It must report the planted day even after remote raters are approved (the world overwrites cfg.drift_day then),
never reveal it before the clock reaches it, never write it into the record, and change nothing else.
"""
import copy
import json
import os
import pickle

os.environ["UNBLIND_NO_LLM"] = "1"

from unblind.platform.dosing.eval_drift import DRIFT_DAY, DRIFT_SITE, NEVER, run_trial  # noqa: E402
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


def test_truth_is_hidden_before_the_onset_day():
    m = Master("TEST-MV-EARLY", use_stub_predose=True)
    m.rec.save = lambda: None
    m.setup()
    m.run_to(DRIFT_DAY - 1)
    assert m.state()["simulated_truth"] is None
    m.run_to(DRIFT_DAY)
    assert m.state()["simulated_truth"]["drift_onset_day"] == DRIFT_DAY


def test_exposure_stores_nothing_and_changes_nothing():
    m = Master("TEST-MV-PURE", use_stub_predose=True)
    m.rec.save = lambda: None
    m.setup()
    m.run_to(DRIFT_DAY + 2)
    before = copy.deepcopy(dict(m.rec))
    cfg_before = copy.deepcopy(m.world.cfg)
    for _ in range(3):
        m.state()
        m.simulated_truth()
    assert dict(m.rec) == before
    assert m.world.cfg == cfg_before
    assert "drift_onset_day" not in json.dumps(dict(m.rec), default=str)


def test_snapshot_round_trip_and_old_snapshots():
    m = Master("TEST-MV-PICKLE", use_stub_predose=True)
    m.setup()
    m.run_to(DRIFT_DAY)
    back = pickle.loads(pickle.dumps(m))
    assert back.state()["simulated_truth"] == m.state()["simulated_truth"]
    del back.__dict__["_planted_drift_day"]        # a snapshot saved before the field existed
    assert back.simulated_truth()["drift_onset_day"] == DRIFT_DAY
