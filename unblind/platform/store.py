"""Trial store: where a trial lives between requests.

Vercel serves requests from many function instances and recycles them at will, so a trial cannot live in one
process's memory. Every request loads the trial from a shared store; every change runs inside a store-level lock
(load, mutate, save) so concurrent writers on different instances never lose an update.

Backends (chosen by `get_store()`):
  * PostgresStore  when DATABASE_URL (or POSTGRES_URL) is set. Table `parallax_trials`, one row per trial,
    the whole Master pickled and zlib-compressed into `blob`, `version` bumped on every write.
    Mutations: one transaction with SELECT ... FOR UPDATE.
  * FileStore      otherwise (local dev and tests). One file per trial in UNBLIND_STORE_DIR
    (default data/trials/_store), fcntl lock file per trial, atomic rename on write. Processes that share the
    directory share trials, the same way production instances share the database.

Both keep a per-process cache {trial_id: (version, Master)} and only unpickle when the stored version changed.

Pickle safety: blobs are written only by this server (never accepted from users), so unpickling them is trusted.
"""
from __future__ import annotations

import copyreg
import fcntl
import importlib
import io
import os
import pickle
import re
import struct
import threading
import time
import types
import zlib
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .core import DATA

TABLE = "parallax_trials"
_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
_MAGIC = b"PX1Z"                       # format tag: zlib-compressed pickle


class TrialNotFound(KeyError):
    pass


# ---------------------------------------------------------------------------
# serialisation
# ---------------------------------------------------------------------------
def _reduce_module(m: types.ModuleType):
    # any module reference (e.g. ctx.llm, or one a module agent keeps) is stored by name and re-imported on load
    return importlib.import_module, (m.__name__,)


_DISPATCH = copyreg.dispatch_table.copy()
_DISPATCH[types.ModuleType] = _reduce_module


def dumps(obj: Any) -> bytes:
    buf = io.BytesIO()
    p = pickle.Pickler(buf, protocol=pickle.HIGHEST_PROTOCOL)
    p.dispatch_table = _DISPATCH
    p.dump(obj)
    return _MAGIC + zlib.compress(buf.getvalue(), 6)


def loads(blob: bytes) -> Any:
    blob = bytes(blob)
    if blob.startswith(_MAGIC):
        blob = zlib.decompress(blob[len(_MAGIC):])
    return pickle.loads(blob)


def valid_id(trial_id: str) -> bool:
    return bool(_ID_RE.match(trial_id or "")) and trial_id not in (".", "..")


# ---------------------------------------------------------------------------
# interface
# ---------------------------------------------------------------------------
class TrialStore:
    kind = "base"

    def __init__(self) -> None:
        self._cache: Dict[str, Tuple[int, Any]] = {}
        self._cache_lock = threading.Lock()
        self.last_mutation_ms: Optional[float] = None    # load + mutate + save, wall clock
        self.last_overhead_ms: Optional[float] = None    # load + save only (excludes the mutation itself)

    # --- cache helpers
    def _cached(self, tid: str, version: int) -> Optional[Any]:
        with self._cache_lock:
            hit = self._cache.get(tid)
        return hit[1] if hit and hit[0] == version else None

    def _remember(self, tid: str, version: int, m: Any) -> None:
        with self._cache_lock:
            self._cache[tid] = (version, m)

    def _forget(self, tid: str) -> None:
        with self._cache_lock:
            self._cache.pop(tid, None)

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()

    # --- API every backend implements
    def create(self, tid: str, master: Any) -> None:
        raise NotImplementedError

    def load(self, tid: str) -> Any:
        """The trial's Master. Raises TrialNotFound."""
        raise NotImplementedError

    def mutate(self, tid: str, fn: Callable[[Any], Any]) -> Any:
        """Run fn(master) under the store lock and save the result. Raises TrialNotFound.
        If fn raises, nothing is saved and the exception propagates."""
        raise NotImplementedError

    def version(self, tid: str) -> Optional[int]:
        raise NotImplementedError

    def list_ids(self, limit: int = 50) -> List[str]:
        raise NotImplementedError

    def count(self) -> int:
        raise NotImplementedError

    def health(self) -> dict:
        raise NotImplementedError

    def _timed(self, t0: float, t_fn: float) -> None:
        total = (time.perf_counter() - t0) * 1000
        self.last_mutation_ms = round(total, 2)
        self.last_overhead_ms = round(total - t_fn * 1000, 2)


# ---------------------------------------------------------------------------
# file backend
# ---------------------------------------------------------------------------
class FileStore(TrialStore):
    """<dir>/<id>.trial = 8-byte big-endian version + blob; <dir>/<id>.lock is the fcntl lock."""
    kind = "file"

    def __init__(self, root: Optional[os.PathLike] = None) -> None:
        super().__init__()
        self.root = Path(root or os.environ.get("UNBLIND_STORE_DIR") or (DATA / "trials" / "_store"))

    def _path(self, tid: str) -> Path:
        if not valid_id(tid):
            raise TrialNotFound(tid)
        return self.root / f"{tid}.trial"

    def _lock(self, tid: str):
        self.root.mkdir(parents=True, exist_ok=True)
        fh = open(self.root / f"{tid}.lock", "a+")
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        return fh

    def _read(self, p: Path) -> Tuple[int, bytes]:
        data = p.read_bytes()
        return struct.unpack(">Q", data[:8])[0], data[8:]

    def _write(self, p: Path, version: int, blob: bytes) -> None:
        tmp = p.with_name(f".{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        with open(tmp, "wb") as fh:
            fh.write(struct.pack(">Q", version) + blob)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, p)

    def version(self, tid: str) -> Optional[int]:
        try:
            p = self._path(tid)
            with open(p, "rb") as fh:
                head = fh.read(8)
        except (TrialNotFound, FileNotFoundError):
            return None
        return struct.unpack(">Q", head)[0] if len(head) == 8 else None

    def create(self, tid: str, master: Any) -> None:
        p = self._path(tid)
        fh = self._lock(tid)
        try:
            if p.exists():
                raise ValueError(f"trial {tid} already exists")
            self._write(p, 1, dumps(master))
            self._remember(tid, 1, master)
        finally:
            fh.close()

    def load(self, tid: str) -> Any:
        p = self._path(tid)
        v = self.version(tid)
        if v is None:
            raise TrialNotFound(tid)
        hit = self._cached(tid, v)
        if hit is not None:
            return hit
        try:
            v, blob = self._read(p)
        except FileNotFoundError:
            raise TrialNotFound(tid)
        m = loads(blob)
        self._remember(tid, v, m)
        return m

    def mutate(self, tid: str, fn: Callable[[Any], Any]) -> Any:
        p = self._path(tid)
        t0 = time.perf_counter()
        fh = self._lock(tid)
        try:
            if not p.exists():
                raise TrialNotFound(tid)
            v = self.version(tid)
            m = self._cached(tid, v)
            if m is None:
                v, blob = self._read(p)
                m = loads(blob)
            t1 = time.perf_counter()
            try:
                out = fn(m)
            except BaseException:
                self._forget(tid)            # the in-memory copy may be half changed; reload next time
                raise
            t_fn = time.perf_counter() - t1
            self._write(p, v + 1, dumps(m))
            self._remember(tid, v + 1, m)
            self._timed(t0, t_fn)
            return out
        finally:
            fh.close()

    def list_ids(self, limit: int = 50) -> List[str]:
        if not self.root.exists():
            return []
        files = sorted(self.root.glob("*.trial"), key=lambda q: q.stat().st_mtime, reverse=True)
        return [f.name[:-len(".trial")] for f in files[:limit]]

    def count(self) -> int:
        return len(list(self.root.glob("*.trial"))) if self.root.exists() else 0

    def health(self) -> dict:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            ok = os.access(self.root, os.W_OK)
        except OSError:
            ok = False
        return {"store": self.kind, "store_ok": ok}


# ---------------------------------------------------------------------------
# Postgres backend
# ---------------------------------------------------------------------------
def database_url() -> Optional[str]:
    """DATABASE_URL, falling back to POSTGRES_URL (both set by the Neon integration). If both are set,
    the pooled one (Neon host contains '-pooler') wins."""
    urls = [u for u in (os.environ.get("DATABASE_URL"), os.environ.get("POSTGRES_URL")) if u and u.strip()]
    if not urls:
        return None
    pooled = [u for u in urls if "-pooler" in u]
    return (pooled or urls)[0].strip()


class PostgresStore(TrialStore):
    kind = "postgres"

    def __init__(self, url: str, connect_timeout: int = 5) -> None:
        super().__init__()
        self.url = url
        self.connect_timeout = connect_timeout
        self._ready = False
        self._ready_lock = threading.Lock()

    def _connect(self):
        import psycopg
        # prepare_threshold=None: Neon's pooled endpoint is PgBouncer in transaction mode (no prepared statements)
        return psycopg.connect(self.url, connect_timeout=self.connect_timeout, prepare_threshold=None)

    def _conn(self):
        conn = self._connect()
        if not self._ready:
            with self._ready_lock:
                if not self._ready:
                    with conn.transaction():
                        conn.execute(
                            f"CREATE TABLE IF NOT EXISTS {TABLE} (id text PRIMARY KEY, version bigint NOT NULL, "
                            "blob bytea NOT NULL, created_at timestamptz DEFAULT now(), "
                            "updated_at timestamptz DEFAULT now())")
                    self._ready = True
        return conn

    def version(self, tid: str) -> Optional[int]:
        with self._conn() as conn:
            row = conn.execute(f"SELECT version FROM {TABLE} WHERE id = %s", (tid,)).fetchone()
        return row[0] if row else None

    def create(self, tid: str, master: Any) -> None:
        blob = dumps(master)
        with self._conn() as conn:
            with conn.transaction():
                conn.execute(f"INSERT INTO {TABLE} (id, version, blob) VALUES (%s, 1, %s)", (tid, blob))
        self._remember(tid, 1, master)

    def load(self, tid: str) -> Any:
        with self._conn() as conn:
            row = conn.execute(f"SELECT version FROM {TABLE} WHERE id = %s", (tid,)).fetchone()
            if not row:
                raise TrialNotFound(tid)
            hit = self._cached(tid, row[0])
            if hit is not None:
                return hit
            row = conn.execute(f"SELECT version, blob FROM {TABLE} WHERE id = %s", (tid,)).fetchone()
        if not row:
            raise TrialNotFound(tid)
        m = loads(row[1])
        self._remember(tid, row[0], m)
        return m

    def mutate(self, tid: str, fn: Callable[[Any], Any]) -> Any:
        t0 = time.perf_counter()
        with self._conn() as conn:
            with conn.transaction():
                row = conn.execute(f"SELECT version FROM {TABLE} WHERE id = %s FOR UPDATE", (tid,)).fetchone()
                if not row:
                    raise TrialNotFound(tid)
                v = row[0]
                m = self._cached(tid, v)
                if m is None:
                    blob = conn.execute(f"SELECT blob FROM {TABLE} WHERE id = %s", (tid,)).fetchone()[0]
                    m = loads(blob)
                t1 = time.perf_counter()
                try:
                    out = fn(m)
                except BaseException:
                    self._forget(tid)
                    raise                     # leaving the transaction block rolls back and releases the lock
                t_fn = time.perf_counter() - t1
                conn.execute(f"UPDATE {TABLE} SET version = version + 1, blob = %s, updated_at = now() "
                             "WHERE id = %s", (dumps(m), tid))
            self._remember(tid, v + 1, m)
        self._timed(t0, t_fn)
        return out

    def list_ids(self, limit: int = 50) -> List[str]:
        with self._conn() as conn:
            rows = conn.execute(f"SELECT id FROM {TABLE} ORDER BY updated_at DESC LIMIT %s", (limit,)).fetchall()
        return [r[0] for r in rows]

    def count(self) -> int:
        with self._conn() as conn:
            return conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()[0]

    def health(self) -> dict:
        try:
            with self._conn() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"store": self.kind, "store_ok": True}
        except Exception as e:  # noqa: BLE001 - report reachability, never the URL
            return {"store": self.kind, "store_ok": False, "store_error": type(e).__name__}


# ---------------------------------------------------------------------------
_STORE: Optional[TrialStore] = None
_STORE_LOCK = threading.Lock()


def get_store() -> TrialStore:
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                url = database_url()
                _STORE = PostgresStore(url) if url else FileStore()
    return _STORE


def set_store(store: Optional[TrialStore]) -> None:
    """Tests: swap the process-wide store."""
    global _STORE
    _STORE = store
