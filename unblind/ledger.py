"""Evidence ledger: every fact the agents produce, with the sentence it came from.

A fact is only worth something if a scientist can check it. So each Fact
carries its value, the verbatim quote that supports it, the source it came
from (with licence), which agent produced it, and a status:

    observed  - read directly from a source, quote verified verbatim
    derived   - computed in code from observed facts (e.g. SE from a CI)
    imputed   - estimated from other facts because the source is silent
    unknown   - not found, or failed the audit
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

STATUSES = ("observed", "derived", "imputed", "unknown")


@dataclass
class Source:
    id: str                      # e.g. "ctgov:NCT01234567", "pmc:PMC123", "protocol:NCT..."
    kind: str                    # registry | paper | supplement | protocol | pasted
    url: str
    licence: str
    title: str = ""
    text: str = ""               # full plain text the auditor checks quotes against
    sections: Dict[str, str] = field(default_factory=dict)  # section title -> text

    def brief(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "url": self.url,
                "licence": self.licence, "title": self.title,
                "chars": len(self.text)}


@dataclass
class Fact:
    name: str
    value: Any
    status: str = "observed"
    quote: str = ""
    source_id: str = ""
    agent: str = ""
    note: str = ""
    audit: str = ""              # pass | fail:<reason> | n/a

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"bad status {self.status}")


@dataclass
class TraceEvent:
    t: float
    agent: str
    action: str
    detail: str = ""
    level: str = "info"          # info | decision | warn | error

    def line(self) -> str:
        tag = {"decision": "→", "warn": "!", "error": "✗"}.get(self.level, "·")
        return f"[{self.agent}] {tag} {self.action}" + (f": {self.detail}" if self.detail else "")


class Ledger:
    def __init__(self) -> None:
        self.facts: Dict[str, Fact] = {}
        self.sources: Dict[str, Source] = {}
        self.trace: List[TraceEvent] = []
        self._listeners: List[Any] = []

    # ---- trace -------------------------------------------------------
    def on_event(self, fn) -> None:
        self._listeners.append(fn)

    def log(self, agent: str, action: str, detail: str = "", level: str = "info") -> None:
        ev = TraceEvent(time.time(), agent, action, detail[:400], level)
        self.trace.append(ev)
        for fn in self._listeners:
            try:
                fn(ev)
            except Exception:
                pass

    # ---- sources -----------------------------------------------------
    def add_source(self, src: Source) -> Source:
        self.sources[src.id] = src
        self.log("ledger", "source added", f"{src.kind} {src.id} ({src.licence})")
        return src

    # ---- facts -------------------------------------------------------
    def put(self, fact: Fact) -> Fact:
        prev = self.facts.get(fact.name)
        # never let a weaker status overwrite a stronger one
        rank = {"observed": 3, "derived": 2, "imputed": 1, "unknown": 0}
        if prev and rank[prev.status] > rank[fact.status]:
            return prev
        self.facts[fact.name] = fact
        return fact

    def get(self, name: str, default: Any = None) -> Any:
        f = self.facts.get(name)
        if f is None or f.status == "unknown":
            return default
        return f.value

    def status(self, name: str) -> str:
        f = self.facts.get(name)
        return f.status if f else "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "facts": {k: asdict(v) for k, v in self.facts.items()},
            "sources": {k: v.brief() for k, v in self.sources.items()},
            "trace": [asdict(e) for e in self.trace],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


def unknown(name: str, agent: str, note: str = "") -> Fact:
    return Fact(name=name, value=None, status="unknown", agent=agent, note=note)
