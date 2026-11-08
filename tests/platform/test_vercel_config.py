"""vercel.json: hashed assets are cached for a year, API responses are never cached (API-7)."""
import json
from pathlib import Path

CFG = json.loads((Path(__file__).resolve().parents[2] / "vercel.json").read_text())


def _header(source):
    for rule in CFG.get("headers", []):
        if rule["source"] == source:
            return {h["key"].lower(): h["value"] for h in rule["headers"]}
    return {}


def test_assets_are_immutable():
    assert "immutable" in _header("/assets/(.*)").get("cache-control", "")


def test_api_is_not_cached():
    assert _header("/api/(.*)").get("cache-control") == "no-store"


def test_api_routes_to_function_and_spa_fallback_excludes_assets():
    srcs = {r["source"]: r["destination"] for r in CFG["rewrites"]}
    assert srcs["/api/(.*)"] == "/api/index"
    assert srcs["/((?!assets/).*)"] == "/index.html"
