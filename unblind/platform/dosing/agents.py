"""Dosing agents that execute the schedule and chase the data.

Every agent decides something and explains it with rec.event(...). None reads
allocation: the world is called only through its public methods, and every
blinding number comes from ctx.vault (see monitor.py).
"""
from __future__ import annotations

import csv
from typing import Optional

from ..core import DATA, Ctx, TrialRecord
from .parsing import missing_fields, parse_checkin, parse_debrief, reask_prompt
from .stats import wilson

MODULE = "dosing"
SESSION, DEBRIEF, CHECKIN, RATER = "dosing_session", "monitor_debrief", "participant_checkin", "rater_assessment"
KINDS = (SESSION, DEBRIEF, CHECKIN, RATER)


def log(rec: TrialRecord, agent: str, text: str, level: str = "info", data=None) -> None:
    rec.event(agent, text, level, MODULE, data)


def due(rec: TrialRecord, day: int, kind: str, status: str = "scheduled") -> list:
    return [s for s in rec["schedule"]
            if s.get("owner") == MODULE and s.get("kind") == kind and s.get("day") == day and s.get("status") == status]


def person(rec: TrialRecord, pid: str) -> dict:
    return next((p for p in rec["enrolled"] if p["id"] == pid), {})


def short_site(site: str) -> str:
    return site.split(" (")[0] if site else site


def next_id(rec: TrialRecord, section: str, prefix: str) -> str:
    return f"{prefix}{len(rec[section]) + 1:04d}"


# ---------------------------------------------------------------- sessions and debriefs
class SessionAgent:
    """Runs each scheduled dosing session and has the monitor debrief structured the same day."""
    name = "session_agent"

    def run(self, rec: TrialRecord, day: int, ctx: Ctx, debrief: "DebriefAgent") -> None:
        ran = []
        for s in due(rec, day, SESSION):
            notes = ctx.world.monitor_debrief(s["participant"], day) if ctx.world is not None else ""
            sess = {"id": f"SES-{s['participant']}", "schedule_id": s["id"], "participant": s["participant"],
                    "site": s.get("site", ""), "day": day, "monitor_notes": notes, "deviations": [], "synthetic": True}
            rec["sessions"].append(sess)
            s["status"] = "done"
            debrief.structure(rec, sess, ctx)
            for d in due(rec, day, DEBRIEF):
                if d["participant"] == s["participant"]:
                    d["status"] = "done"
            ran.append(f"{s['participant']} ({short_site(sess['site'])})")
        if ran:
            log(rec, self.name, f"Ran {len(ran)} dosing session(s): {', '.join(ran)}.")


class DebriefAgent:
    """Turns monitor notes into adverse events (with severity) and unblinding cues, with quotes."""
    name = "debrief_agent"
    SCHEMA = ('{"adverse_events":[{"term":"","severity":"mild|moderate|severe","serious":false,"quote":""}],'
              '"unblinding_cues":[{"type":"rater_contact|participant_question|other","quote":""}]}')

    def structure(self, rec: TrialRecord, sess: dict, ctx: Ctx) -> dict:
        notes = sess["monitor_notes"]
        out = parse_debrief(notes)
        method = "rules"
        if ctx.llm is not None and ctx.llm.available():
            got = ctx.llm.ask_json(
                "Structure these SYNTHETIC psychedelic-trial session notes into adverse events and blinding cues. "
                "Quotes must be exact sentences from the notes.", notes, self.SCHEMA)
            if isinstance(got, dict):
                method = "rules + Gemini"
                have = {a["term"] for a in out["adverse_events"]}
                for a in got.get("adverse_events") or []:
                    if isinstance(a, dict) and a.get("quote") and a["quote"] in notes and a.get("term") not in have:
                        out["adverse_events"].append({**a, "source": "gemini"})
                quotes = {q["quote"] for q in out["unblinding_cues"]}
                for q in got.get("unblinding_cues") or []:
                    if isinstance(q, dict) and q.get("quote") and q["quote"] in notes and q["quote"] not in quotes:
                        out["unblinding_cues"].append({**q, "source": "gemini"})
        for q in out["unblinding_cues"]:
            if q["type"] == "rater_contact":
                sess["deviations"].append(f"Blinding deviation: \"{q['quote']}\"")
        d = {"id": next_id(rec, "debriefs", "DB"), "session_id": sess["id"], "participant": sess["participant"],
             "site": sess["site"], "day": sess["day"], "notes": notes, "method": method, **out,
             "deviations": sess["deviations"], "synthetic": True}
        rec["debriefs"].append(d)
        terms = ", ".join(f"{a['term']} ({a['severity']})" for a in d["adverse_events"]) or "no adverse events"
        log(rec, self.name, f"Structured the debrief for {d['participant']} at {short_site(d['site'])}: {terms}; "
                            f"{len(d['unblinding_cues'])} unblinding cue(s).")
        for q in d["unblinding_cues"]:
            if q["type"] == "rater_contact":
                log(rec, self.name, f"Blinding deviation at {short_site(d['site'])}: \"{q['quote']}\"", "warn")
        serious = [a for a in d["adverse_events"] if a.get("serious")]
        if serious:
            self._escalate(rec, d, serious, ctx)
        return d

    def _escalate(self, rec: TrialRecord, d: dict, serious: list, ctx: Ctx) -> None:
        terms = " and ".join(a["term"] for a in serious)
        quotes = " ".join(f"\"{q}\"" for q in dict.fromkeys(a["quote"] for a in serious))
        aid = next_id(rec, "alerts", "DOS-AL")
        ap = ctx.approvals.request(
            self.name, MODULE, f"Clinician review: {terms} ({d['participant']}, {short_site(d['site'])})",
            f"Monitor note: {quotes}. The site physician must review and confirm the safety response.",
            {"type": "clinical_review", "participant": d["participant"], "site": d["site"], "alert_id": aid},
            evidence={"debrief": d["id"]})
        rec["alerts"].append({"id": aid, "day": rec["day"], "module": MODULE, "severity": "critical",
                              "kind": "serious_adverse_event", "site": d["site"], "title": f"Serious adverse event: {terms}",
                              "explanation": f"Debrief for {d['participant']} records {quotes}. Sent to the site physician.",
                              "evidence": {"debrief": d["id"]}, "approval_id": ap["id"], "status": "open"})
        ctx.bus.post(self.name, "master", "adverse_event",
                     {"participant": d["participant"], "site": d["site"], "terms": [a["term"] for a in serious],
                      "serious": True, "approval_id": ap["id"]}, f"Serious adverse event: {terms}")
        log(rec, self.name, f"Escalated a serious adverse event ({terms}) at {short_site(d['site'])} to the site physician.", "warn")


# ---------------------------------------------------------------- check-ins
class CheckinAgent:
    """Runs participant check-ins (guess, confidence 0-100, expectancy 0-10); re-asks when an answer is incomplete."""
    name = "checkin_agent"

    def run(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        done = missed = reasked = 0
        for s in due(rec, day, CHECKIN):
            r = self.collect(rec, s, day, ctx)
            if r is None:
                missed += 1
            else:
                done += 1
                reasked += r["reasked"]
        if done or missed:
            log(rec, self.name, f"Collected {done} check-in(s); re-asked {reasked} incomplete answer(s); "
                                f"{missed} unanswered, passed to the missing-data chaser.")

    def collect(self, rec: TrialRecord, s: dict, day: int, ctx: Ctx, late: bool = False) -> Optional[dict]:
        ans = ctx.world.respond_checkin(s["participant"], day, "participant", s.get("site", ""))
        if ans is None:
            if not late:
                s["status"], s["initially_missed"] = "missed", True
            return None
        reasked = False
        if missing_fields(ans):
            reasked = True
            again = ctx.world.respond_checkin(s["participant"], day, "participant", s.get("site", ""))
            if again:
                ans = {k: (ans.get(k) if ans.get(k) is not None else again.get(k)) for k in ("guess", "confidence", "expectancy")}
        row = self.record(rec, s["participant"], s.get("site", ""), day, ans, channel="text", reasked=reasked,
                          late=late, schedule_id=s["id"])
        s["status"] = "late_done" if late else "done"
        return row

    def record(self, rec: TrialRecord, pid: str, site: str, day: int, ans: dict, channel: str = "text",
               reasked: bool = False, late: bool = False, schedule_id: Optional[str] = None, judge: bool = False,
               raw_text: Optional[str] = None) -> dict:
        row = {"id": next_id(rec, "checkins", "CI"), "participant": pid, "site": site, "day": day, "who": "participant",
               "rater_id": None, "guess": ans.get("guess"), "confidence": ans.get("confidence"),
               "expectancy": ans.get("expectancy"), "channel": channel, "reasked": reasked, "late": late,
               "complete": not missing_fields(ans), "schedule_id": schedule_id, "judge_input": judge,
               "raw_text": raw_text, "synthetic": True}
        rec["checkins"].append(row)
        return row

    def judge(self, rec: TrialRecord, payload: dict, ctx: Ctx) -> dict:
        """'Play a patient': a judge answers a check-in for a SYNTHETIC participant, in words or by form."""
        pid = str(payload.get("participant", "")).strip()
        p = person(rec, pid)
        if not p:
            return {"ok": False, "message": f"No enrolled participant '{pid}'. Try {rec['enrolled'][0]['id'] if rec['enrolled'] else 'one from the enrolled list'}."}
        text = str(payload.get("answer") or "").strip()
        ans = parse_checkin(text) if text else {"guess": None, "confidence": None, "expectancy": None}
        if text and missing_fields(ans) and ctx.llm is not None and ctx.llm.available():
            got = ctx.llm.ask_json("Extract a blinding check-in answer. Use null for anything not said.", text,
                                   '{"guess":"drug|control|dont_know|null","confidence":0,"expectancy":0}')
            if isinstance(got, dict):
                for k in ("guess", "confidence", "expectancy"):
                    if ans.get(k) is None and got.get(k) not in (None, "null", ""):
                        ans[k] = got[k]
        for k in ("guess", "confidence", "expectancy"):  # form fields fill any gaps
            v = payload.get(k)
            if ans.get(k) is None and v not in (None, ""):
                try:
                    ans[k] = v if k == "guess" else int(float(v))
                except (TypeError, ValueError):
                    pass
        miss = missing_fields(ans)
        if miss:
            prompt = reask_prompt(miss)
            log(rec, self.name, f"Live check-in for {pid} was incomplete; asked: {prompt}", "decision")
            return {"ok": False, "needs_reask": True, "missing": miss, "message": prompt}
        row = self.record(rec, pid, p.get("site", ""), max(rec["day"], 0), ans, channel=payload.get("channel") or "text",
                          judge=True, raw_text=text or None)
        log(rec, self.name, f"Live check-in from {pid} (played by a judge): guess {ans['guess']}, confidence "
                            f"{ans['confidence']}, expectancy {ans['expectancy']}. It now counts in the blinding monitor.", "decision")
        return {"ok": True, "message": f"Recorded for {pid}: {ans['guess']}, confidence {ans['confidence']}, "
                                       f"expectancy {ans['expectancy']}.", "checkin": row}


# ---------------------------------------------------------------- rater assessments
class RaterVisitAgent:
    """Weeks 1, 3 and 6: MADRS plus the rater's guess, by rater ID."""
    name = "rater_visit_agent"

    def run(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        n = sum(self.attempt(rec, s, day, ctx) for s in due(rec, day, RATER))
        if n:
            log(rec, self.name, f"Recorded {n} rater assessment(s): MADRS plus the rater's guess.")

    def attempt(self, rec: TrialRecord, s: dict, day: int, ctx: Ctx, retry: bool = False) -> bool:
        pid, site = s["participant"], s.get("site", "")
        r = ctx.world.respond_checkin(pid, day, "rater", site)
        if r is None:
            if not retry:
                s["status"], s["initially_missed"] = "missed", True
            return False
        pg = next((c["guess"] for c in reversed(rec["checkins"]) if c["participant"] == pid and c["who"] == "participant"), None)
        madrs = ctx.world.madrs(pid, day, rater_believes_drug=r["guess"] == "drug", patient_believes_drug=pg == "drug")
        week = round((day - person(rec, pid).get("dosing_day", day)) / 7)
        rec["checkins"].append({"id": next_id(rec, "checkins", "CI"), "participant": pid, "site": site, "day": day,
                                "who": "rater", "rater_id": s.get("rater_id"), "guess": r["guess"],
                                "confidence": r["confidence"], "expectancy": None, "channel": "form",
                                "late": retry, "complete": True, "schedule_id": s["id"], "synthetic": True})
        rec["outcomes"].append({"participant": pid, "site": site, "day": day, "visit_week": week, "madrs": madrs,
                                "rater_id": s.get("rater_id"), "rater_guess": r["guess"], "patient_guess": pg,
                                "synthetic": True})
        s["status"] = "late_done" if retry else "done"
        return True


# ---------------------------------------------------------------- missing data
class MissingDataChaser:
    """Reminds the next day, escalates to the site after two misses, proposes a site fix if a pattern appears."""
    name = "missing_data_chaser"
    WINDOW, MIN_DUE, RATE = 14, 20, 0.15

    def _note(self, rec, s, status, detail):
        rec["missing_data"].append({"day": rec["day"], "schedule_id": s["id"], "participant": s["participant"],
                                    "site": s.get("site", ""), "kind": s["kind"], "status": status, "detail": detail})

    def run(self, rec: TrialRecord, day: int, ctx: Ctx, checkin: CheckinAgent, rater: RaterVisitAgent) -> None:
        chased = recovered = 0
        for s in [x for x in rec["schedule"] if x.get("owner") == MODULE and x.get("status") == "missed" and x.get("day") == day - 1]:
            chased += 1
            ok = (checkin.collect(rec, s, day, ctx, late=True) is not None) if s["kind"] == CHECKIN \
                else rater.attempt(rec, s, day, ctx, retry=True)
            if ok:
                recovered += 1
                self._note(rec, s, "recovered", "Answered after a reminder" if s["kind"] == CHECKIN else "Rescheduled by the site")
                continue
            s["status"] = "lost"
            self._note(rec, s, "lost", "No answer after a reminder")
            misses = sum(1 for m in rec["missing_data"] if m["participant"] == s["participant"] and m["status"] == "lost")
            escalated = any(m["participant"] == s["participant"] and m["status"] == "escalated" for m in rec["missing_data"])
            if misses >= 2 and not escalated:
                self._note(rec, s, "escalated", f"{misses} missed assessments; escalated to the site coordinator")
                ctx.bus.post(self.name, "master", "missing_data", {"participant": s["participant"], "site": s.get("site", ""),
                                                                  "misses": misses}, f"{s['participant']} missed {misses} assessments")
                log(rec, self.name, f"{s['participant']} has missed {misses} assessments; escalated to "
                                    f"{short_site(s.get('site', ''))} coordinator.", "warn")
        if chased:
            log(rec, self.name, f"Chased {chased} missed assessment(s) from yesterday; {recovered} recovered.")
        self._pattern(rec, day, ctx)

    def _pattern(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        asked = {a["site"] for a in rec["alerts"] if a.get("kind") == "missing_data_pattern"}
        by: dict = {}
        for s in rec["schedule"]:
            if s.get("owner") == MODULE and s.get("kind") == CHECKIN and day - self.WINDOW <= s.get("day", -1) < day:
                v = by.setdefault(s.get("site", ""), [0, 0])
                v[0] += 1
                v[1] += bool(s.get("initially_missed"))
        for site, (n_due, n_miss) in sorted(by.items()):
            if site in asked or n_due < self.MIN_DUE or n_miss / n_due <= self.RATE:
                continue
            others = [m / d for s2, (d, m) in by.items() if s2 != site and d]
            other = sum(others) / len(others) if others else 0.0
            if wilson(n_miss, n_due)[0] <= other:  # not clearly worse than the other sites yet
                continue
            aid = next_id(rec, "alerts", "DOS-AL")
            why = (f"{short_site(site)} missed {n_miss} of {n_due} check-ins in the last {self.WINDOW} days "
                   f"({n_miss / n_due:.0%}; other sites {other:.0%}).")
            ap = ctx.approvals.request(
                self.name, MODULE, f"{short_site(site)}: add SMS reminders and a coordinator call",
                why + " Proposed fix: an SMS reminder the evening before and a coordinator call on the morning of each check-in.",
                {"type": "reduce_missing", "site": site, "alert_id": aid}, evidence={"due": n_due, "missed": n_miss})
            rec["alerts"].append({"id": aid, "day": day, "module": MODULE, "severity": "warn", "kind": "missing_data_pattern",
                                  "site": site, "title": f"Missing data pattern at {short_site(site)}", "explanation": why,
                                  "evidence": {"due": n_due, "missed": n_miss, "other_sites_rate": round(other, 3)},
                                  "approval_id": ap["id"], "status": "open"})
            ctx.bus.post(self.name, "master", "missing_data", {"site": site, "pattern": True, "due": n_due, "missed": n_miss},
                         why)
            log(rec, self.name, why + " Proposed a site fix for approval.", "decision")


# ---------------------------------------------------------------- literature
class LiteratureAgent:
    """Weekly: proposes one candidate trial from the research pipeline's cached extractions for the reference data."""
    name = "literature_agent"

    def candidates(self) -> list:
        path = DATA / "gold_candidates.csv"
        if not path.exists():
            return []
        trials: dict = {}
        with open(path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                t = trials.setdefault(r["trial_name"], {"trial": r["trial_name"], "registry_id": r.get("registry_id", ""),
                                                        "fields": 0, "verified": 0, "url": r.get("source_url", "")})
                t["fields"] += 1
                t["verified"] += str(r.get("verified", "")).upper().startswith("YES")
        return list(trials.values())

    def run(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if day <= 0 or day % 7:
            return
        # One proposal at a time, so weekly reference data never buries trial decisions in the approval inbox.
        if any(x["status"] == "proposed" for x in rec["literature"]):
            return
        cands = self.candidates()
        i = len(rec["literature"])
        if i >= len(cands):
            return
        c = cands[i]
        status = "all fields verified" if c["verified"] == c["fields"] else f"{c['fields'] - c['verified']} of {c['fields']} fields still need a human check"
        ap = ctx.approvals.request(
            self.name, MODULE, f"Add to reference data: {c['trial']}",
            f"Weekly literature scan (cached research pipeline output, offline). {c['trial']} ({c['registry_id']}): "
            f"{c['fields']} extracted fields with quotes; {status}. Approve only after checking the quotes.",
            {"type": "literature_addition", "trial": c["trial"]}, evidence=c)
        rec["literature"].append({"id": next_id(rec, "literature", "LIT"), "day": day, **c, "status": "proposed",
                                  "approval_id": ap["id"], "source": "data/gold_candidates.csv"})
        log(rec, self.name, f"Weekly scan: proposed {c['trial']} for the reference data ({status}).", "decision")


# ---------------------------------------------------------------- primary lock
class PrimaryLock:
    """Locks the primary endpoint the day after the last week-6 assessment (or once the retry window has passed)."""
    name = "primary_lock"
    GRACE = 7

    @staticmethod
    def locked(rec: TrialRecord) -> Optional[dict]:
        return next((m["payload"] for m in rec["messages"] if m["kind"] == "primary_locked" and m["from"] == PrimaryLock.name), None)

    def run(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if self.locked(rec):
            return
        rv = [s for s in rec["schedule"] if s.get("owner") == MODULE and s.get("kind") == RATER]
        if not rv:
            return
        last = max(s["day"] for s in rv)
        open_ = [s for s in rv if s["status"] in ("scheduled", "missed")]
        if day < last + 1 or (open_ and day < last + 1 + self.GRACE):
            return
        have = {o["participant"] for o in rec["outcomes"] if o.get("visit_week") == 6}
        n = len(rec["enrolled"])
        ctx.bus.post(self.name, "master", "primary_locked", {"day": day, "with_week6": len(have), "n": n},
                     f"Primary endpoint locked: {len(have)} of {n} have a week-6 MADRS.")
        log(rec, self.name, f"Primary endpoint locked: {len(have)} of {n} participants have a week-6 MADRS. "
                            "No more changes to the primary analysis data.", "decision")
