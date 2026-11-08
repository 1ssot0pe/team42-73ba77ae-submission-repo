"""Vercel entry point: serves the FastAPI backend as one Python function.

Only /tmp is writable on Vercel, so trial files and the HTTP cache go there.
Trials live in memory, so they can vanish between requests if Vercel starts a new instance.
"""
import os

os.environ.setdefault("UNBLIND_TRIALS_DIR", "/tmp/unblind/trials")
os.environ.setdefault("UNBLIND_CACHE", "/tmp/unblind/cache")

from backend.main import app  # noqa: E402,F401
