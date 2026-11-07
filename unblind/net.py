"""Polite, cached, allowlisted HTTP.

* Only hosts on ALLOWED_HOSTS can be fetched. A URL found inside a document
  (e.g. a prompt-injected link) can never send the agent somewhere else.
* Every response is cached on disk, so a demo survives flaky Wi-Fi and
  rate limits, and a judge's input that was fetched once replays instantly.
* UNBLIND_OFFLINE=1 serves from cache only (used by tests and as a fallback).
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

ALLOWED_HOSTS = {
    "clinicaltrials.gov",
    "cdn.clinicaltrials.gov",
    "www.ebi.ac.uk",
    "europepmc.org",
    "generativelanguage.googleapis.com",
}

CACHE_DIR = Path(os.environ.get("UNBLIND_CACHE", Path(__file__).resolve().parent.parent / ".cache"))
USER_AGENT = "UNBLIND-hackathon-prototype/0.1 (research tool; contact via repo)"


class NetError(Exception):
    pass


def offline() -> bool:
    return os.environ.get("UNBLIND_OFFLINE", "") == "1"


def _key(url: str) -> Path:
    return CACHE_DIR / hashlib.sha1(url.encode()).hexdigest()


def host_allowed(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in ALLOWED_HOSTS


def seed_cache(url: str, content: bytes) -> None:
    """Used by tests and by `unblind cache-import` to pre-load responses."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _key(url).write_bytes(content)


def get(url: str, *, timeout: float = 20, retries: int = 3, binary: bool = False,
        max_bytes: int = 25_000_000):
    if not host_allowed(url):
        raise NetError(f"host not on allowlist: {urlparse(url).hostname}")
    p = _key(url)
    if p.exists():
        data = p.read_bytes()
        return data if binary else data.decode("utf-8", errors="replace")
    if offline():
        raise NetError("offline mode and not cached")
    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
            if r.status_code == 429 or r.status_code >= 500:
                wait = float(r.headers.get("Retry-After", 2 * (attempt + 1)))
                time.sleep(min(wait, 10))
                last = NetError(f"HTTP {r.status_code}")
                continue
            if r.status_code == 404:
                raise NetError("HTTP 404")
            r.raise_for_status()
            data = r.content[:max_bytes]
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
            return data if binary else data.decode("utf-8", errors="replace")
        except NetError:
            raise
        except Exception as e:  # network hiccup
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise NetError(f"failed after {retries} tries: {last}")


def post_json(url: str, payload: dict, *, timeout: float = 60) -> dict:
    if not host_allowed(url.split("?")[0]):
        raise NetError("host not on allowlist")
    if offline():
        raise NetError("offline mode")
    r = requests.post(url, json=payload, timeout=timeout, headers={"User-Agent": USER_AGENT})
    if r.status_code >= 400:
        raise NetError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()
