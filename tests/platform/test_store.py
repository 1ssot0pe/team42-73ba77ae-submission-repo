"""Trial store: a trial survives a round-trip through the store and continues identically, and concurrent
writers (separate store objects, as on separate Vercel instances) never lose an update.

FileStore always runs. PostgresStore runs when TEST_DATABASE_URL points at a scratch database."""
from __future__ import annotations

import itertools
import os
import pickle
import threading
import time
import uuid

import pytest

from unblind.platform import store as store_mod
from unblind.platform.core import TRIALS, digest
from unblind.platform.master.orchestrator import Master
from unblind.platform.store import FileStore, PostgresStore, TrialNotFound, dumps, loads

PG_URL = os.environ.get("TEST_DATABASE_URL")
BACKENDS = ["file"] + (["postgres"] if PG_URL else [])


def _new_id(tag: str) -> str:
    return f"TST-{tag}-{uuid.uuid4().hex[:8]}"


@pytest.fixture(params=BACKENDS)
def make_store(request, tmp_path):
    """Returns a factory: each call gives a NEW store object on the same backing storage (a new 'instance')."""
    made_ids = []
    if request.param == "file":
        def factory():
            return FileStore(tmp_path / "store")
    else:
        def factory():
            return PostgresStore(PG_URL)
    factory.ids = made_ids
    yield factory
    if request.param == "postgres" and made_ids:
        import psycopg
        with psycopg.connect(PG_URL) as conn:
            conn.execute(f"DELETE FROM {store_mod.TABLE} WHERE id = ANY(%s)", (made_ids,))


class _Deterministic:
    """uuid4 / time made repeatable so two runs of the same steps can be compared byte for byte."""

    def __init__(self, monkeypatch):
        self.mp = monkeypatch
        self.reset()
        monkeypatch.setattr(uuid, "uuid4", lambda: uuid.UUID(int=next(self.counter)))
        monkeypatch.setattr(time, "time", lambda: 1_700_000_000.0)
        monkeypatch.setattr(time, "strftime", lambda *a, **k: "2026-01-01T00:00:00")

    def reset(self, start: int = 10_000):
        self.counter = itertools.count(start)


def _trial(day: int, seed: int = 7) -> Master:
    m = Master(f"RT-{seed}-{day}", seed=seed, n_applicants=200, auto_approve=True)
    m.setup()
    if day > 0:
        m.run_to(day)
    return m


def _fingerprint(m: Master) -> dict:
    return {"rec": digest(m.rec), "state": digest(m.state()), "events": digest(m.rec["events"]),
            "ctx_rng": digest(m.ctx.rng.getstate()), "world_rng": digest(m.world.rng.getstate()),
            "world_people": digest(m.world.people), "vault": digest(m.vault._alloc),
            "vault_log": digest(m.vault.access_log), "kpis": digest(m.kpis())}


@pytest.mark.parametrize("day", [0, 45, 90])
def test_round_trip_continues_identically(day, monkeypatch):
    det = _Deterministic(monkeypatch)
    m = _trial(day)
    clone = loads(dumps(m))
    assert _fingerprint(clone) == _fingerprint(m)
    assert clone.ctx.llm is m.ctx.llm                 # the module reference is rebuilt, not lost
    assert clone.lock is not m.lock                   # a fresh lock
    with clone.lock:                                  # and a usable one
        pass
    assert clone.ctx.vault is clone.vault and clone.world.v is clone.vault   # shared references survive
    assert clone.ctx.rec is clone.rec and clone.ctx.bus.rec is clone.rec

    det.reset()
    a = m.step(7)
    det.reset()
    b = clone.step(7)
    assert a == b
    assert _fingerprint(clone) == _fingerprint(m)
    if day == 90:
        assert m.rec["phase"] == "closed"
        for mod in ("predose", "dosing", "postdose"):
            assert digest(clone.module_view(mod)) == digest(m.module_view(mod))


def test_vault_is_in_the_snapshot_not_on_disk():
    m = _trial(5)
    alloc = dict(m.vault._alloc)
    assert alloc
    blob = dumps(m)
    vf = TRIALS / f"{m.rec['trial_id']}.vault.json"
    if vf.exists():
        vf.unlink()                                   # a fresh instance has an empty /tmp
    clone = loads(blob)
    assert clone.vault._alloc == alloc
    assert clone.vault.path == vf


def test_postdose_salt_travels_with_the_snapshot(monkeypatch):
    monkeypatch.delenv("UNBLIND_EXPORT_SALT", raising=False)
    from unblind.platform.postdose.agents import _salt
    m = _trial(0)
    salt = _salt(m.rec["trial_id"])
    blob = dumps(m)
    (TRIALS / f"{m.rec['trial_id']}.salt").unlink()  # the next request lands on an instance without the file
    loads(blob)
    assert _salt(m.rec["trial_id"]) == salt


def test_blob_is_compressed_and_never_raw_pickle():
    m = _trial(0)
    blob = dumps(m)
    assert blob.startswith(store_mod._MAGIC)
    import zlib
    assert len(blob) * 2 < len(zlib.decompress(blob[len(store_mod._MAGIC):]))
    with pytest.raises(Exception):
        pickle.loads(blob)                            # not a bare pickle


def test_create_load_mutate_versions(make_store):
    s1, s2 = make_store(), make_store()
    tid = _new_id("ver")
    make_store.ids.append(tid)
    m = Master(tid, seed=3, n_applicants=100, auto_approve=True)
    m.setup()
    s1.create(tid, m)
    assert s1.version(tid) == 1
    got = s2.load(tid)                                # another instance sees it
    assert got.state()["trial_id"] == tid
    out = s2.mutate(tid, lambda mm: mm.step(3))
    assert out["advanced"] is True
    assert s1.version(tid) == 2
    assert s1.load(tid).rec["day"] == got.rec["day"] == 2   # s1 reloads because the version moved
    with pytest.raises(TrialNotFound):
        s1.load("nope-" + tid)
    with pytest.raises(TrialNotFound):
        s1.mutate("nope-" + tid, lambda mm: None)


def test_failed_mutation_saves_nothing(make_store):
    s = make_store()
    tid = _new_id("fail")
    make_store.ids.append(tid)
    m = Master(tid, seed=3, n_applicants=100)
    m.setup()
    s.create(tid, m)

    def boom(mm):
        mm.rec["config"]["poison"] = True
        raise ValueError("nope")
    with pytest.raises(ValueError):
        s.mutate(tid, boom)
    assert s.version(tid) == 1
    assert "poison" not in s.load(tid).rec["config"]
    assert "poison" not in make_store().load(tid).rec["config"]


def test_concurrent_mutations_lose_no_updates(make_store):
    tid = _new_id("conc")
    make_store.ids.append(tid)
    m = Master(tid, seed=3, n_applicants=100)
    m.setup()
    make_store().create(tid, m)
    n_threads, per = 4, 12
    errors = []

    def bump(mm):
        c = mm.rec["config"].get("counter", 0)
        time.sleep(0.001)                             # widen the read-modify-write window
        mm.rec["config"]["counter"] = c + 1

    def worker():
        s = make_store()                              # its own cache, like a separate instance
        try:
            for _ in range(per):
                s.mutate(tid, bump)
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    ts = [threading.Thread(target=worker) for _ in range(n_threads)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errors, errors
    fresh = make_store()
    assert fresh.load(tid).rec["config"]["counter"] == n_threads * per
    assert fresh.version(tid) == 1 + n_threads * per


def test_file_store_rejects_path_traversal(tmp_path):
    s = FileStore(tmp_path / "store")
    for bad in ("../etc/passwd", "a/b", "", ".."):
        with pytest.raises(TrialNotFound):
            s.load(bad)


def test_database_url_prefers_pooled(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@ep-x.eu.aws.neon.tech/db")
    monkeypatch.setenv("POSTGRES_URL", "postgres://u:p@ep-x-pooler.eu.aws.neon.tech/db")
    assert "-pooler" in store_mod.database_url()
    monkeypatch.delenv("DATABASE_URL")
    assert store_mod.database_url().startswith("postgres://u:p@ep-x-pooler")
    monkeypatch.delenv("POSTGRES_URL")
    assert store_mod.database_url() is None


def test_unreadable_snapshot_is_trial_not_found(tmp_path):
    """A corrupt or incompatible blob must read as a missing trial (API 404), never a 500."""
    import pytest
    from unblind.platform.store import TrialNotFound, loads, _MAGIC
    for blob in (b"garbage", _MAGIC + b"not zlib", _MAGIC + __import__("zlib").compress(b"\x80\x05not a pickle")):
        with pytest.raises(TrialNotFound):
            loads(blob)
