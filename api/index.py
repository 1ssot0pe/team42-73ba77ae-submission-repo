"""Vercel entry point: serves the FastAPI backend as one Python function.

Only /tmp is writable on Vercel, so scratch files and the HTTP cache go there.
Trials live in the shared trial store (unblind/platform/store.py): Postgres when DATABASE_URL (or
POSTGRES_URL) is set, which is what makes trials survive across Vercel instances. Without a database the
store falls back to files in /tmp, which only works while a single instance serves every request.
"""
import os

os.environ.setdefault("UNBLIND_TRIALS_DIR", "/tmp/unblind/trials")
os.environ.setdefault("UNBLIND_CACHE", "/tmp/unblind/cache")
if not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")):
    os.environ.setdefault("UNBLIND_STORE_DIR", "/tmp/unblind/store")   # single-instance fallback only

from backend.main import app  # noqa: E402,F401
