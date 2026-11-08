"""Post-dosing agents. Owner: Izzy.

    FollowUpAgent        weeks 8 and 12: MADRS, end-of-treatment guess and expectancy, durability; chases non-responders
    BiasGateAgent        reviews researcher questions: approve, rewrite (neutral wording) or reject, with reasons
    InterviewAgent       asks ethics-approved questions, after the primary lock, to consenting participants only
    Harmoniser           builds the UNBLIND-BLIND-1 export (salted-hash IDs, consent filter, data dictionary)
    CloseoutReportAgent  the FDA blinding report: reported vs expectancy-adjusted effect, blinding over time,
                         every alert and human decision, the FDA checklist with evidence, limitations

Rules followed (MODULE_CONTRACT.md): vault aggregates only; every trial-changing action
goes through ctx.approvals; every decision is logged with rec.event; every agent has a
deterministic path and uses Gemini only as an optional extra; the World is SYNTHETIC
and is used only through its public methods.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core import TRIALS, Ctx, TrialRecord, digest
from . import effects

MODULE = "postdose"
CLOSE_DAY = 90                      # contract: day 90 close-out
FOLLOWUP_WEEKS = (8, 12)
STANDARD = "UNBLIND-BLIND-1"
EVAL_JSON = Path(__file__).resolve().parents[3] / "eval" / "platform" / "effect_recovery.json"


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def log(rec: TrialRecord, agent: str, text: str, level: str = "info", data=None) -> None:
    rec.event(agent, text, level, MODULE, data=data)


def state(rec: TrialRecord) -> dict:
    """The post-dosing working state lives in our own section rec['report'] until the report is drafted."""
    r = rec["report"]
    r.setdefault("status", "collecting")
    r.setdefault("evidence_log", [])
    r.setdefault("primary_lock_day", None)
    return r


def lock_day(rec: TrialRecord) -> Optional[int]:
    """Day the primary endpoint was locked (set by the master, or recorded when we got the message)."""
    d = rec.get("primary_lock_day")
    return d if d is not None else rec["report"].get("primary_lock_day")


def person(rec: TrialRecord, pid: str) -> dict:
    return next((p for p in rec["enrolled"] if p["id"] == pid), {})


def consents(p: dict) -> Tuple[bool, bool]:
    """(check-ins, data sharing). Missing data-sharing consent is treated as NO."""
    c = p.get("consents") or {}
    return bool(c.get("checkins", True)), bool(c.get("data_sharing", c.get("share_data", False)))


def short_site(site: str) -> str:
    return (site or "").split(" (")[0]


def _salt(trial_id: str) -> str:
    """Pseudonymisation salt. Never stored in the TrialRecord or the export, never hard-coded.
    Uses UNBLIND_EXPORT_SALT if set, otherwise a random salt kept in data/trials/ (git-ignored)."""
    env = os.environ.get("UNBLIND_EXPORT_SALT")
    if env:
        return env
    TRIALS.mkdir(parents=True, exist_ok=True)
    p = TRIALS / f"{trial_id}.salt"
    if not p.exists():
        p.write_text(secrets.token_hex(16))
    return p.read_text().strip()


def pseudonym(pid: str, salt: str) -> str:
    return "UB1-" + hashlib.sha256((salt + pid).encode()).hexdigest()[:12]


# ===========================================================================
# 1. Follow-up agent
# ===========================================================================
class FollowUpAgent:
    name = "followup_agent"
    MAX_CHASE = 2

    def plan(self, rec: TrialRecord, day: int) -> int:
        """Plan week-8 and week-12 visits. Uses schedule entries owned by postdose if the pre-dosing
        agents created them; otherwise derives them from each participant's dosing day."""
        if rec["followups"]:
            return 0
        mine = [s for s in rec["schedule"] if s.get("owner") == MODULE and s.get("kind") == "followup"]
        rows = []
        if mine:
            for s in mine:
                p = person(rec, s["participant"])
                wk = s.get("visit_week") or round((s["day"] - p.get("dosing_day", 0)) / 7)
                rows.append(self._row(rec, p, wk, s["day"], s["id"], s.get("rater_id")))
            source = f"{len(mine)} follow-up entries in the schedule"
        else:
            for p in rec["enrolled"]:
                for wk in FOLLOWUP_WEEKS:
                    rows.append(self._row(rec, p, wk, p.get("dosing_day", 1) + 7 * wk, None, self._rater(rec, p["id"])))
            source = "each participant's dosing day (no follow-up entries in the schedule)"
        rec["followups"] = rows
        late = sum(1 for r in rows if r["due_day"] < day)
        after = sum(1 for r in rows if r["due_day"] > CLOSE_DAY)
        log(rec, self.name, f"Primary endpoint locked: planned {len(rows)} follow-up visits (weeks 8 and 12) from {source}. "
                            f"{late} are already past their due day and will be collected now, flagged late. "
                            f"{after} fall after close-out on day {CLOSE_DAY} and are marked for an addendum.", "decision")
        return len(rows)

    @staticmethod
    def _rater(rec: TrialRecord, pid: str) -> Optional[str]:
        rv = [s for s in rec["schedule"] if s.get("participant") == pid and s.get("rater_id")]
        return rv[-1]["rater_id"] if rv else None

    @staticmethod
    def _row(rec, p, wk, due, sid, rater_id) -> dict:
        return {"id": f"FU-{p.get('id', '?')}-w{wk}", "participant": p.get("id"), "site": p.get("site", ""),
                "visit_week": wk, "due_day": due, "day": None, "status": "planned", "attempts": 0,
                "schedule_id": sid, "rater_id": rater_id, "madrs": None, "rater_guess": None, "patient_guess": None,
                "confidence": None, "expectancy": None, "durability_vs_primary": None, "days_late": 0, "synthetic": True}

    def run(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if lock_day(rec) is None or ctx.world is None:
            return
        if not rec["followups"]:
            self.plan(rec, day)
        done, chased, lost = [], [], []
        for f in rec["followups"]:
            if f["status"] not in ("planned", "missed") or f["due_day"] > day or day > CLOSE_DAY:
                continue
            ci, _ = consents(person(rec, f["participant"]))
            if not ci:
                f["status"] = "no_consent"
                self._sched(rec, f, "missed")
                log(rec, self.name, f"{f['participant']} did not consent to check-ins: week-{f['visit_week']} questions not sent.")
                continue
            ans = ctx.world.respond_checkin(f["participant"], day, "participant", f["site"])
            if ans is None:
                f["attempts"] += 1
                if f["attempts"] > self.MAX_CHASE:
                    f["status"] = "lost"
                    lost.append(f)
                    self._sched(rec, f, "lost")
                else:
                    f["status"] = "missed"
                    chased.append(f)
                continue
            rater = ctx.world.respond_checkin(f["participant"], day, "rater", f["site"])
            rg = rater["guess"] if rater else None
            f.update(day=day, patient_guess=ans["guess"], confidence=ans["confidence"], expectancy=ans["expectancy"],
                     rater_guess=rg, days_late=max(0, day - f["due_day"]),
                     madrs=ctx.world.madrs(f["participant"], day, rater_believes_drug=(rg == "drug") if rg else None,
                                           patient_believes_drug=ans["guess"] == "drug"))
            prim = self._primary_madrs(rec, f["participant"])
            f["durability_vs_primary"] = round(f["madrs"] - prim, 1) if prim is not None else None
            f["status"] = "late_done" if f["days_late"] else "done"
            self._sched(rec, f, f["status"])
            done.append(f)
        for f in chased:
            log(rec, self.name, f"No answer from {f['participant']} for the week-{f['visit_week']} follow-up: reminder sent, "
                                f"attempt {f['attempts']} of {self.MAX_CHASE}, trying again tomorrow.", "decision")
        for f in lost:
            log(rec, self.name, f"{f['participant']} week-{f['visit_week']} follow-up recorded as lost after "
                                f"{self.MAX_CHASE} reminders. It will be listed as missing in the FDA report.", "warn")
        if done:
            late = sum(1 for f in done if f["days_late"])
            log(rec, self.name, f"Collected {len(done)} follow-up visits (MADRS, end-of-treatment guess and expectancy)"
                                + (f", {late} late because they fell before the primary lock" if late else "") + ".")

    @staticmethod
    def _primary_madrs(rec, pid) -> Optional[float]:
        wk = effects.primary_week(rec)
        xs = [o["madrs"] for o in rec["outcomes"] if o.get("participant") == pid and o.get("visit_week") == wk
              and o.get("madrs") is not None]
        return xs[-1] if xs else None

    @staticmethod
    def _sched(rec, f, status) -> None:
        for s in rec["schedule"]:
            if f.get("schedule_id") and s.get("id") == f["schedule_id"] and s.get("owner") == MODULE:
                s["status"] = status

    def close(self, rec: TrialRecord) -> int:
        n = 0
        for f in rec["followups"]:
            if f["status"] == "planned" and f["due_day"] > CLOSE_DAY:
                f["status"] = "after_close"
                n += 1
            elif f["status"] in ("missed", "planned"):
                f["status"] = "lost"
                self._sched(rec, f, "lost")
                log(rec, self.name, f"{f['participant']} week-{f['visit_week']} follow-up still unanswered at close-out: "
                                    "recorded as lost.", "warn")
        if n:
            log(rec, self.name, f"{n} follow-up visits fall after close-out (day {CLOSE_DAY}); recorded as due for an "
                                "addendum, not as missing.")
        return n


# ===========================================================================
# 2. Bias gate agent
# ===========================================================================
_I = re.IGNORECASE
CHECKS: Dict[str, List[str]] = {
    "unblinding": [r"\bthe drug\b", r"\bactive (drug|treatment|dose)\b", r"\bplacebo\b", r"\bpsilocybin\b",
                   r"\bpsychedelics?\b", r"\bmdma\b", r"\blsd\b", r"\bcomp360\b", r"\btrip(s|ping|ped)?\b",
                   r"\bhallucinat\w*", r"\bvisuals?\b", r"\bvisual effects?\b", r"\bvisions?\b", r"\bcolou?rs\b",
                   r"\bintens(e|ity)\b", r"\bmystical\b", r"\bego[- ]dissolution\b", r"\bperceptual\b",
                   r"\baltered state\b", r"\bpeak\b"],
    "leading": [r"\bhow much (better|happier|more improved)\b", r"\bhow (has|have) (your|the) [\w ]{1,30}? improved\b",
                r"\b(don'?t|do not|wouldn'?t|would not|isn'?t|is not) (you|it) (agree|say|think)\b",
                r"\b(life[- ]changing|transformative|profound|miracle|amazing|incredible|breakthrough)\b",
                r"\bwhat benefits?\b", r"\bhow did (the|your) (treatment|session|therapy) help\b", r"\bfeel better\b",
                r"\bsurely\b"],
    "personal": [r"\b(full )?name\b", r"\baddress\b", r"\bpost ?code\b", r"\bphone\b", r"\bmobile number\b",
                 r"\be-?mail\b", r"\bdate of birth\b", r"\bnhs number\b", r"\bnational insurance\b", r"\bemployer\b",
                 r"\bwhere do you (live|work)\b", r"\bsocial media\b", r"\b(instagram|facebook|tiktok)\b",
                 r"\bphoto(graph)?s?\b", r"\bpassport\b", r"\bAPP-\d+\b"],
    "safety": [r"\bsuicid\w*", r"\bself[- ]harm\w*", r"\bkill (yourself|myself)\b", r"\bend (your|my) life\b",
               r"\bhurt(ing)? (yourself|others)\b", r"\boverdos\w*", r"\bpsychos[ie]s\b", r"\bpsychotic\b",
               r"\bhearing voices\b", r"\bchest pain\b", r"\bheart (problems?|attack)\b", r"\bseizures?\b"],
    "consent": [r"\b(contact|call|email|ask|speak to) (your|their) (family|partner|gp|doctor|friends?|employer)\b",
                r"\b(madrs|primary (outcome|endpoint)|depression (score|rating))\b"],
}
# Things no rewording can fix: asking for the allocation guess (that is the standard instrument's job)
# or a question that is itself an assertion to agree with.
UNFIXABLE = {
    "unblinding": [r"\b(drug|placebo|active|control|treatment) (group|arm)\b", r"\bwhich (group|arm)\b"],
    "leading": [r"^\s*(wouldn'?t|would not|don'?t|do not|isn'?t|is not|surely)\b"],
}
REASON_TEXT = {
    "unblinding": "Unblinding cue: mentions the drug, its effects or the arms, which tells people what they probably got.",
    "leading": "Leading or expectancy wording: presumes improvement or invites agreement.",
    "personal": "Asks for identifying or personal data, which the portal never collects.",
    "safety": "Safety content: this must go to the clinical team through the adverse-event pathway, not a research portal.",
    "consent": "Timing or consent: involves people who have not consented, or re-measures the primary endpoint.",
}
REWRITES: List[Tuple[str, str]] = [
    (r"\b(took|received|had|were given)\s+(the|your)\s+(drug|psilocybin|psychedelic|placebo|dose)\b", r"attended \2 study session"),
    (r"\b(?:(the|your)\s+)?(?:active\s+)?(drug|psilocybin|psychedelic|mdma|lsd|comp360|placebo)(?:\s+(dose|session|experience|treatment|trip))?\b",
     lambda m: f"{m.group(1) or 'the'} study session"),
    (r"\b(the|your) trip\b", r"\1 study session"),
    (r"\btrip(s|ping|ped)?\b", "study session"),
    (r"\b(hallucinations?|visuals|visual effects?|visions?|colou?rs|perceptual changes)\b", "experiences"),
    (r"\b(mystical|ego[- ]dissolution|altered[- ]state|intense|profound|transformative|life[- ]changing|amazing|incredible|miracle|breakthrough)\s+", ""),
    (r"\bintensity\b", "nature"),
    (r"\bhow much (better|happier|more improved)\b", "how"),
    (r"\bhow (has|have) (your|the) ([\w ]{1,30}?) improved\b", r"how would you describe \2 \3"),
    (r"\bwhat benefits? (have|did) you\b", r"what changes, positive or negative, \1 you"),
    (r"\bhow did (the|your) (treatment|session|therapy|study session) help( you)?", "what, if anything, has changed for you"),
    (r"\bfeel better\b", "feel"),
    (r",?\s*(don'?t|do not|wouldn'?t|would not|isn'?t|is not) (you|it) (agree|say|think)\s*", ""),
]


def _hits(text: str, patterns: Dict[str, List[str]]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for check, pats in patterns.items():
        for p in pats:
            m = re.search(p, text, _I)
            if m:
                out.setdefault(check, []).append(m.group(0))
    return out


def _tidy(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"\s+([?.,!])", r"\1", t)
    t = re.sub(r"\b(the|your) (the|your)\b", r"\1", t, flags=_I)
    t = re.sub(r"\bthe study session study session\b", "the study session", t, flags=_I)
    return t[:1].upper() + t[1:] if t else t


def neutral_rewrite(text: str) -> str:
    t = text
    for pat, rep in REWRITES:
        t = re.sub(pat, rep, t, flags=_I)
    return _tidy(t)


class BiasGateAgent:
    name = "bias_gate_agent"

    def review(self, text: str, llm=None) -> dict:
        """Deterministic review (plus an optional Gemini rewrite that must pass the same rules)."""
        text = (text or "").strip()
        reasons = []
        if len(text) < 10:
            return {"decision": "reject", "reasons": [{"check": "format", "detail": "Too short to be a question.", "quote": text}],
                    "rewrite": None, "method": "rules"}
        hits = _hits(text, CHECKS)
        hard = _hits(text, UNFIXABLE)
        for check, quotes in {**hits, **{k: v for k, v in hard.items() if k not in hits}}.items():
            reasons.append({"check": check, "detail": REASON_TEXT[check], "quote": "; ".join(sorted(set(quotes)))})
        blocking = {"personal", "safety", "consent"} & set(hits)
        if blocking or hard:
            why = sorted(blocking) or sorted(hard)
            return {"decision": "reject", "reasons": reasons, "rewrite": None, "method": "rules",
                    "summary": f"Rejected: {', '.join(why)} cannot be fixed by rewording."}
        if not hits:
            return {"decision": "approve", "reasons": [], "rewrite": None, "method": "rules",
                    "summary": "No unblinding cues, leading wording, personal data, safety or consent issues found."}
        method = "rules"
        candidate = None
        if llm is not None and llm.available():
            got = llm.ask_json(
                "You review questions that outside researchers want to ask participants of a blinded psychedelic "
                "trial. Rewrite the question in the DOCUMENT so it is neutral: no mention of the drug, placebo, "
                "trips, visual or intense effects, or which group someone was in; no wording that presumes "
                "improvement. Keep the researcher's topic. Return the rewritten question in 'rewrite' and put the "
                "original question in 'quote'.", text, '{"rewrite": "", "quote": ""}')
            cand = (got or {}).get("rewrite")
            if isinstance(cand, str) and 10 <= len(cand) <= 300 and not _hits(cand, CHECKS) and not _hits(cand, UNFIXABLE):
                candidate, method = cand.strip(), "rules + Gemini rewrite (re-checked by rules)"
        if candidate is None:
            candidate = neutral_rewrite(text)
        if _hits(candidate, CHECKS) or _hits(candidate, UNFIXABLE) or len(candidate) < 10:
            return {"decision": "reject", "reasons": reasons, "rewrite": None, "method": method,
                    "summary": "Rejected: no neutral rewording passed the checks."}
        return {"decision": "rewrite", "reasons": reasons, "rewrite": candidate, "method": method,
                "summary": f"Rewrite proposed: {candidate}"}

    def submit(self, rec: TrialRecord, text: str, researcher: str, ctx: Ctx) -> dict:
        res = self.review(text, ctx.llm)
        qid = f"RQ-{len(rec['research_questions']) + 1:03d}"
        q = {"id": qid, "day": rec["day"], "researcher": (researcher or "anonymous researcher").strip()[:80],
             "text": text.strip(), "decision": res["decision"], "reasons": res["reasons"], "rewrite": res["rewrite"],
             "summary": res.get("summary", ""),
             "final_text": None, "method": res["method"], "status": "", "approval_id": None, "released_day": None,
             "asked": 0, "skipped_no_consent": 0, "answers": [], "themes": [], "synthetic": True}
        rec["research_questions"].append(q)
        if res["decision"] == "reject":
            q["status"] = "rejected_by_gate"
            log(rec, self.name, f"{qid} rejected. {res['summary']} Reasons: "
                                + " | ".join(f"{r['check']}: \"{r['quote']}\"" for r in res["reasons"]), "decision")
            ctx.bus.post(self.name, "master", "question_rejected",
                         {"question_id": qid, "checks": [r["check"] for r in res["reasons"]]},
                         f"Bias gate rejected researcher question {qid}")
            return {"ok": True, "question_id": qid, "decision": "reject", "message": res["summary"], "reasons": res["reasons"]}
        q["final_text"] = res["rewrite"] or q["text"]
        locked = lock_day(rec) is not None
        a = ctx.approvals.request(
            self.name, MODULE, f"Ethics: release researcher question {qid}",
            f"The bias gate {'approved' if res['decision'] == 'approve' else 'rewrote'} this question. "
            f"It will be asked only of participants who consented to data sharing, and only after the primary "
            f"endpoint is locked{' (already locked)' if locked else ' (not yet locked, so it will be held)'}.",
            {"type": "release_research_question", "question_id": qid, "text": q["final_text"]},
            evidence={"original": q["text"], "reasons": res["reasons"], "method": res["method"]})
        q["approval_id"], q["status"] = a["id"], "awaiting_ethics"
        log(rec, self.name, f"{qid} {'passed' if res['decision'] == 'approve' else 'rewritten'}: "
                            f"\"{q['final_text']}\". Sent to an ethics reviewer before release.", "decision")
        return {"ok": True, "question_id": qid, "decision": res["decision"], "rewrite": res["rewrite"],
                "message": res["summary"] + " Waiting for an ethics reviewer.", "reasons": res["reasons"]}

    def decided(self, rec: TrialRecord, a: dict) -> None:
        qid = (a.get("action") or {}).get("question_id")
        q = next((x for x in rec["research_questions"] if x["id"] == qid), None)
        if not q:
            return
        if a["status"] == "approved":
            q["status"] = "approved_held"
            log(rec, self.name, f"{a.get('reviewer')} approved {qid}. "
                                + ("Releasing now: the primary endpoint is locked." if lock_day(rec) is not None
                                   else "Held until the primary endpoint is locked."), "decision")
            self.release(rec)
        else:
            q["status"] = "rejected_by_ethics"
            log(rec, self.name, f"{a.get('reviewer')} rejected {qid}; it will not be asked.", "decision")

    def release(self, rec: TrialRecord) -> int:
        """No question is released before the primary lock."""
        ld = lock_day(rec)
        if ld is None:
            return 0
        n = 0
        for q in rec["research_questions"]:
            if q["status"] == "approved_held":
                q["status"], q["released_day"] = "released", rec["day"]
                n += 1
        if n:
            log(rec, self.name, f"Released {n} ethics-approved question(s) to the participant interview agent "
                                f"(primary endpoint locked on day {ld}).", "decision")
        return n


# ===========================================================================
# 3. Participant interview agent
# ===========================================================================
THEMES = {
    "connection with others": ["connected", "people", "family", "relationship"],
    "reflection on the session": ["reflect", "think about the session", "put into words"],
    "sleep": ["sleep"],
    "mood up and down": ["mood", "up and down"],
    "little or no change": ["not much", "nothing", "no change", "hasn't changed", "not changed"],
    "study process": ["check-in", "helpful", "on track"],
}


class InterviewAgent:
    name = "interview_agent"

    def run(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if lock_day(rec) is None or ctx.world is None:
            return
        salt = None
        for q in rec["research_questions"]:
            if q["status"] != "released":
                continue
            salt = salt or _salt(rec["trial_id"])
            for p in rec["enrolled"]:
                _, share = consents(p)
                if not share:
                    q["skipped_no_consent"] += 1
                    continue
                text = ctx.world.answer_research_question(p["id"], q["final_text"])
                q["answers"].append({"pid": pseudonym(p["id"], salt), "day": day, "answer": text})
                q["asked"] += 1
            q["themes"] = self.themes(q["answers"], ctx)
            q["status"] = "answered"
            for s in rec["schedule"]:
                if s.get("owner") == MODULE and s.get("kind") == "research_question" and s.get("status") == "scheduled" \
                        and s.get("day", 10 ** 9) <= day:
                    s["status"] = "done"
            top = ", ".join(f"{t['theme']} ({t['n']})" for t in q["themes"][:3]) or "none"
            log(rec, self.name, f"{q['id']} asked of {q['asked']} consenting participants "
                                f"({q['skipped_no_consent']} without data-sharing consent were not asked). "
                                f"Top themes: {top}. Answers stored under pseudonyms only.", "decision")

    @staticmethod
    def themes(answers: List[dict], ctx: Optional[Ctx] = None) -> List[dict]:
        counts: Dict[str, int] = {}
        for a in answers:
            low = a["answer"].lower()
            for theme, words in THEMES.items():
                if any(w in low for w in words):
                    counts[theme] = counts.get(theme, 0) + 1
        out = [{"theme": t, "n": n, "method": "keywords"} for t, n in sorted(counts.items(), key=lambda x: -x[1])]
        if ctx is not None and ctx.llm.available() and answers:
            doc = "\n".join(a["answer"] for a in answers)[:20000]
            got = ctx.llm.ask_json("Group these participant answers into at most 4 themes. For each theme give a short "
                                   "name and one supporting quote copied verbatim from the answers.", doc,
                                   '{"themes": [{"theme": "", "quote": ""}]}')
            for t in (got or {}).get("themes", [])[:4]:
                if isinstance(t, dict) and t.get("quote") and t["quote"] in doc:     # quote audit: verbatim or dropped
                    out.append({"theme": str(t.get("theme", ""))[:60], "n": None, "quote": t["quote"][:200],
                                "method": "Gemini (quote verified)"})
        return out


# ===========================================================================
# 4. Harmoniser: UNBLIND-BLIND-1 export
# ===========================================================================
DICTIONARY = [
    {"field": "pid", "type": "string", "meaning": "Pseudonymised participant ID (salted SHA-256; the salt is never exported)", "cdisc": "USUBJID (pseudonymised)"},
    {"field": "site", "type": "string", "meaning": "Trial site", "cdisc": "SITEID"},
    {"field": "stratum", "type": "string", "meaning": "Randomisation stratum (site and naive or experienced)", "cdisc": "SUPPDM.QVAL (STRATUM)"},
    {"field": "timepoint_day", "type": "integer", "meaning": "Day of the measure relative to the participant's dosing day", "cdisc": "--DY"},
    {"field": "visit_week", "type": "integer or empty", "meaning": "Scheduled visit week, where the measure belongs to one", "cdisc": "VISITNUM"},
    {"field": "respondent", "type": "participant | rater | monitor", "meaning": "Who answered", "cdisc": "QSEVAL"},
    {"field": "guess", "type": "drug | control | dont_know", "meaning": "Which group the respondent thinks the participant was in", "cdisc": "QS, QSCAT = BLINDING"},
    {"field": "confidence", "type": "integer 0 to 100", "meaning": "Confidence in the guess", "cdisc": "QS, QSCAT = BLINDING"},
    {"field": "expectancy", "type": "integer 0 to 10", "meaning": "Expected improvement (participants only)", "cdisc": "QS, QSCAT = EXPECTANCY"},
    {"field": "madrs", "type": "number 0 to 60", "meaning": "MADRS total where measured (higher is worse)", "cdisc": "QS, QSTESTCD = MADRS"},
    {"field": "consent_share", "type": "boolean", "meaning": "Participant consented to data sharing (only true rows are exported)", "cdisc": "not mapped"},
    {"field": "source_event_id", "type": "string", "meaning": "Link back to the audit trail: record section and row number", "cdisc": "not mapped"},
]
FIELDS = [d["field"] for d in DICTIONARY]


class Harmoniser:
    name = "harmoniser"

    def build(self, rec: TrialRecord, salt: str) -> dict:
        people = {p["id"]: p for p in rec["enrolled"]}
        rated = {(o.get("participant"), o.get("day")) for o in rec["outcomes"]}
        raw: List[dict] = []

        def add(pid, day, week, who, guess, conf, exp, madrs, src):
            p = people.get(pid)
            if not p:
                return
            dd = p.get("dosing_day")
            raw.append({"_pid": pid, "site": p.get("site", ""), "stratum": p.get("stratum", ""),
                        "timepoint_day": (day - dd) if (day is not None and dd is not None) else None,
                        "visit_week": week, "respondent": who, "guess": guess, "confidence": conf,
                        "expectancy": exp, "madrs": madrs, "consent_share": consents(p)[1], "source_event_id": src})

        for i, c in enumerate(rec["checkins"]):
            if c.get("who") == "rater" and (c.get("participant"), c.get("day")) in rated:
                continue                                  # the outcome row carries this rater guess
            add(c.get("participant"), c.get("day"), c.get("visit_week"), c.get("who"), c.get("guess"),
                c.get("confidence"), c.get("expectancy"), None, f"checkins#{i}")
        for i, o in enumerate(rec["outcomes"]):
            add(o.get("participant"), o.get("day"), o.get("visit_week"), "rater", o.get("rater_guess"), None, None,
                o.get("madrs"), f"outcomes#{i}")
        for i, f in enumerate(rec["followups"]):
            if f["status"] not in ("done", "late_done"):
                continue
            add(f["participant"], f["day"], f["visit_week"], "participant", f["patient_guess"], f["confidence"],
                f["expectancy"], None, f"followups#{i}")
            add(f["participant"], f["day"], f["visit_week"], "rater", f["rater_guess"], None, None, f["madrs"],
                f"followups#{i}")
        kept = [r for r in raw if r["consent_share"]]
        rows = [{"pid": pseudonym(r["_pid"], salt), **{k: r[k] for k in FIELDS if k != "pid"}} for r in kept]
        required = ("pid", "site", "timepoint_day", "respondent", "guess")
        complete = sum(1 for r in rows if all(r.get(k) not in (None, "") for k in required))
        return {"rows": rows, "n_rows": len(rows), "n_excluded_no_consent": len(raw) - len(kept),
                "n_participants": len({r["pid"] for r in rows}),
                "completeness": round(100 * complete / len(rows), 1) if rows else None}

    def request(self, rec: TrialRecord, ctx: Ctx, who: str = "harmoniser") -> dict:
        ex = rec["exports"]
        if ex.get("status") in ("awaiting_approval", "exported"):
            return {"ok": False, "error": f"export already {ex['status'].replace('_', ' ')}"}
        preview = self.build(rec, "preview-only")
        a = ctx.approvals.request(
            self.name, MODULE, f"Release the {STANDARD} harmonised export",
            f"{preview['n_rows']} rows from {preview['n_participants']} consenting participants; "
            f"{preview['n_excluded_no_consent']} rows withheld for lack of data-sharing consent. "
            "IDs are salted hashes; no names, phone numbers or free text are included.",
            {"type": "harmonised_export", "standard": STANDARD},
            evidence={"fields": FIELDS, "completeness": preview["completeness"]})
        rec["exports"].update(standard=STANDARD, status="awaiting_approval", approval_id=a["id"],
                              requested_day=rec["day"], requested_by=who)
        log(rec, self.name, f"Prepared the {STANDARD} export ({preview['n_rows']} rows) and asked a human to approve its release.",
            "decision")
        return {"ok": True, "message": "Export prepared; waiting for a human to approve it.", "approval_id": a["id"]}

    def decided(self, rec: TrialRecord, a: dict) -> None:
        if a["status"] != "approved":
            rec["exports"]["status"] = "rejected"
            log(rec, self.name, f"{a.get('reviewer')} rejected the export; nothing was written.", "decision")
            return
        out = self.build(rec, _salt(rec["trial_id"]))
        TRIALS.mkdir(parents=True, exist_ok=True)
        csv_path = TRIALS / f"{rec['trial_id']}_{STANDARD}.csv"
        dict_path = TRIALS / f"{rec['trial_id']}_{STANDARD}_dictionary.json"
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(out["rows"])
        dict_path.write_text(json.dumps({"standard": STANDARD, "synthetic": rec.get("synthetic", True),
                                         "fields": DICTIONARY,
                                         "cdisc_note": "Future mapping to CDISC SDTM shown per field; not yet validated."},
                                        indent=1), encoding="utf-8")
        rec["exports"].update(status="exported", approved_by=a.get("reviewer"), exported_day=rec["day"],
                              n_rows=out["n_rows"], n_participants=out["n_participants"],
                              n_excluded_no_consent=out["n_excluded_no_consent"], completeness=out["completeness"],
                              files=[str(csv_path.name), str(dict_path.name)], fields=FIELDS,
                              preview=out["rows"][:8], synthetic=True,
                              cdisc_note="Future mapping to CDISC SDTM listed in the data dictionary; not yet validated.")
        log(rec, self.name, f"{STANDARD} export written after approval by {a.get('reviewer')}: {out['n_rows']} rows, "
                            f"{out['completeness']}% complete, {out['n_excluded_no_consent']} rows withheld (no consent).",
            "decision")


# ===========================================================================
# 5. Close-out report agent
# ===========================================================================
class CloseoutReportAgent:
    name = "closeout_report_agent"

    def draft(self, rec: TrialRecord, ctx: Ctx, final: bool = True) -> dict:
        st = state(rec)
        if st["status"] in ("draft", "final"):        # never overwrite a report awaiting or holding a sign-off
            return rec["report"]
        locked = lock_day(rec)
        eff = effects.estimate_all(rec, ctx.vault, self.name) if locked is not None else \
            {"reported": None, "why_missing": "the primary endpoint was never locked, so the vault was not asked"}
        blind = self._blinding(rec, ctx)
        alerts = [{k: a.get(k) for k in ("id", "day", "module", "severity", "title", "explanation", "approval_id", "status")}
                  for a in rec["alerts"]]
        decisions = [{k: a.get(k) for k in ("id", "day", "module", "title", "status", "reviewer", "decided_day", "comment")}
                     for a in rec["approvals"] if a.get("status") != "pending"]
        report = {
            "standard": STANDARD, "trial_id": rec["trial_id"], "synthetic": rec.get("synthetic", True),
            "drafted_day": rec["day"], "primary_lock_day": locked, "effect": eff, "blinding": blind,
            "alerts": alerts, "decisions": decisions, "actions": list(rec["actions"]),
            "evidence_log": list(st["evidence_log"]), "followups": self._followups(rec),
            "research_questions": self._questions(rec), "missing_data": self._missing(rec),
            "checklist": self._checklist(rec, eff, blind), "limitations": self._limits(rec, eff),
        }
        report["digest"] = digest({k: report[k] for k in ("effect", "blinding", "alerts", "decisions", "checklist")})
        report["markdown"] = render_markdown(report)
        report["status"] = "draft" if final else "preview"
        if final:
            a = ctx.approvals.request(self.name, MODULE, "Sign off the FDA blinding report",
                                      "The close-out report is drafted. A named person must check and sign it before it is final.",
                                      {"type": "report_signoff", "digest": report["digest"]},
                                      evidence={"reported": (eff.get("reported") or {}).get("md"),
                                                "adjusted_range": eff.get("adjusted_range")})
            report["approval_id"] = a["id"]
        rec["report"] = {**st, **report}
        rep = eff.get("reported")
        rng = eff.get("adjusted_range")
        log(rec, self.name, ("Drafted" if final else "Previewed") + " the FDA blinding report. "
            + (f"Reported effect {rep['md']} MADRS points (95% CI {rep['lo']} to {rep['hi']}); "
               + (f"expectancy-adjusted range {rng['lo']} to {rng['hi']}." if rng else "no adjusted estimate was possible.")
               if rep else f"No effect estimate: {eff.get('why_missing')}.")
            + (" Waiting for a named sign-off." if final else ""), "decision")
        return rec["report"]

    def decided(self, rec: TrialRecord, a: dict) -> None:
        r = rec["report"]
        if a.get("id") != r.get("approval_id"):
            return
        if a["status"] == "approved" and (a.get("reviewer") or "").strip():
            r.update(status="final", signed_by=a["reviewer"], signed_day=a.get("decided_day"), sign_comment=a.get("comment", ""))
            r["markdown"] = render_markdown(r)
            log(rec, self.name, f"FDA blinding report signed off by {a['reviewer']}; it is now final (digest {r['digest']}).", "decision")
        else:
            r["status"] = "changes_requested"
            log(rec, self.name, f"{a.get('reviewer')} did not sign the report ({a.get('comment') or 'no comment'}). "
                                "It stays a draft until it is redrafted and signed.", "warn")

    # ---------------------------------------------------------------- sections
    def _blinding(self, rec: TrialRecord, ctx: Ctx) -> dict:
        last_pg: Dict[str, dict] = {}
        for c in rec["checkins"]:
            if c.get("who") == "participant" and c.get("guess"):
                last_pg[c["participant"]] = c
        for f in rec["followups"]:
            if f.get("patient_guess"):
                last_pg[f["participant"]] = {"participant": f["participant"], "guess": f["patient_guess"], "site": f["site"]}
        rater = [{"participant": c["participant"], "guess": c["guess"], "site": c.get("site", ""),
                  "rater": c.get("rater_id") or "unknown"} for c in rec["checkins"] if c.get("who") == "rater" and c.get("guess")]
        pg = [{"participant": c["participant"], "guess": c["guess"], "site": c.get("site", ""), "all": "all"}
              for c in last_pg.values()]
        last_eot: Dict[str, str] = {}                      # one end-of-treatment guess per person (the latest)
        for f in sorted(rec["followups"], key=lambda x: (x.get("day") or 0)):
            if f.get("patient_guess"):
                last_eot[f["participant"]] = f["patient_guess"]
        eot = [{"participant": p, "guess": g, "all": "all"} for p, g in last_eot.items()]
        v = ctx.vault
        out = {"participant_overall": v.blinding_stats(pg, "all", self.name) if pg else [],
               "participant_by_site": v.blinding_stats(pg, "site", self.name) if pg else [],
               "participant_end_of_treatment": v.blinding_stats(eot, "all", self.name) if eot else [],
               "rater_by_site": v.blinding_stats(rater, "site", self.name) if rater else [],
               "rater_by_rater": v.blinding_stats(rater, "rater", self.name) if rater else []}
        tl: Dict[tuple, dict] = {}
        for m in rec["blinding_metrics"]:
            if m.get("by") in ("site", "rater") and m.get("accuracy") is not None and not m.get("suppressed"):
                tl[(m["day"] // 7, m.get("who"), m["by"], m.get("group"))] = m
        out["timeline"] = [{"week": k[0], "who": k[1], "by": k[2], "group": k[3], "accuracy": m["accuracy"],
                            "u": m.get("u"), "n": m.get("n")} for k, m in sorted(tl.items(), key=lambda x: (x[0][0], str(x[0][1:])))]
        return out

    @staticmethod
    def _followups(rec) -> dict:
        by: Dict[str, int] = {}
        for f in rec["followups"]:
            k = f"week {f['visit_week']}: {f['status']}"
            by[k] = by.get(k, 0) + 1
        dur = [f["durability_vs_primary"] for f in rec["followups"] if f.get("durability_vs_primary") is not None]
        return {"counts": by, "n": len(rec["followups"]),
                "mean_change_since_primary_all_participants": round(sum(dur) / len(dur), 2) if dur else None}

    @staticmethod
    def _questions(rec) -> List[dict]:
        return [{k: q.get(k) for k in ("id", "day", "text", "decision", "final_text", "status", "asked",
                                       "skipped_no_consent", "themes")} | {"reasons": [r["check"] for r in q["reasons"]]}
                for q in rec["research_questions"]]

    @staticmethod
    def _missing(rec) -> dict:
        md = rec["missing_data"]
        lost_fu = sum(1 for f in rec["followups"] if f["status"] == "lost")
        return {"dosing_rows": len(md), "lost": sum(1 for m in md if m.get("status") == "lost"),
                "recovered": sum(1 for m in md if m.get("status") == "recovered"), "followups_lost": lost_fu}

    @staticmethod
    def _checklist(rec, eff, blind) -> List[dict]:
        pc = [c for c in rec["checkins"] if c.get("who") == "participant" and c.get("guess")]
        rc = [c for c in rec["checkins"] if c.get("who") == "rater" and c.get("guess")]
        plan = (rec.get("measurement_plan") or {}).get("instruments", [])
        dosing_day = {p["id"]: p.get("dosing_day", 0) for p in rec["enrolled"]}
        pre_plan = [i for i in plan if "expect" in json.dumps(i).lower() and min(i.get("timepoints_days") or [1]) <= 0]
        pre_obs = [c for c in rec["checkins"] if c.get("expectancy") is not None
                   and c.get("day", 0) < dosing_day.get(c.get("participant"), 0)]
        eot = [f for f in rec["followups"] if f.get("expectancy") is not None]
        prot = rec.get("protocol") or {}
        comp = str(prot.get("comparator", "")).lower()
        remote = [a for a in rec["actions"] if a.get("type") == "remote_raters"]
        drift_alerts = [a for a in rec["alerts"] if "drift" in str(a.get("kind", a.get("title", ""))).lower()]
        decided = [a for a in rec["approvals"] if a.get("status") in ("approved", "rejected")]

        def item(name, status, evidence):
            return {"item": name, "status": status, "evidence": evidence}
        out = [
            item("Blinding questionnaire given to participants", "met" if pc else "not_met",
                 f"{len(pc)} participant guesses from {len({c['participant'] for c in pc})} people" if pc else "no participant guesses recorded"),
            item("Blinding questionnaire given to outcome raters", "met" if rc else "not_met",
                 f"{len(rc)} rater guesses from {len({c.get('rater_id') for c in rc})} raters" if rc else "no rater guesses recorded"),
            item("Expectancy measured before randomisation", "met" if (pre_plan and pre_obs) else ("partial" if pre_plan or pre_obs else "not_met"),
                 f"{len(pre_plan)} planned pre-randomisation expectancy instruments, {len(pre_obs)} answers before dosing"),
            item("Expectancy measured at end of treatment", "met" if eot else "not_met",
                 f"{len(eot)} end-of-treatment expectancy answers at weeks 8 and 12" if eot else "no end-of-treatment expectancy answers"),
            item("Central blinded raters", "met" if effects.central_raters(rec) else ("partial" if remote else "not_met"),
                 f"protocol rater model: {prot.get('rater_model', 'not stated')}"
                 + (f"; remote raters approved at {', '.join(short_site(a.get('site', '')) for a in remote)}" if remote else "")),
            item("Alternative or active control considered", "met" if any(k in comp for k in ("active", "low dose", "low-dose", "niacin", "mg")) else ("not_met" if comp else "not_assessable"),
                 f"comparator: {prot.get('comparator', 'not stated')}"),
            item("Blinding monitored during the trial, with decisions logged", "met" if (blind["rater_by_site"] or rec["blinding_metrics"]) else "not_met",
                 f"{len(rec['blinding_metrics'])} blinding metric releases, {len(drift_alerts)} drift alerts, {len(decided)} human decisions"),
            item("Effect reported with an expectancy-adjusted estimate", "met" if eff.get("adjusted_range") else "not_met",
                 "within-trial and cross-trial estimates side by side" if eff.get("adjusted_range") else str(eff.get("why_missing", "no adjusted estimate"))),
        ]
        return out

    @staticmethod
    def _limits(rec, eff) -> List[str]:
        lim = ["SYNTHETIC trial: every participant, guess and score was simulated. Nothing here is real-world performance.",
               "Reverse causation: people who improve may guess 'drug' because they improved. Adjusting for the guess then "
               "removes real benefit, so the adjusted values are a conservative bound, not the true effect."]
        try:
            ev = json.loads(EVAL_JSON.read_text())
            rc = ev["scenarios"]["reverse_causation"]["within_trial"]
            lim.append(f"In our planted-truth simulation where guesses follow improvement, the within-trial estimate was off by "
                       f"{rc['bias']:+.2f} MADRS points on average ({ev['n_seeds']} seeds, truth -4).")
            nb = ev["scenarios"]["no_bias"]["cross_trial"]
            lim.append(f"The cross-trial calibration over-corrected by {nb['bias']:+.2f} points in simulated trials with no "
                       "expectancy bias at all, because it treats all unblinding as bias. Prefer the within-trial value.")
        except Exception:
            pass
        lim += ["Confounding: guess groups are not randomised. Comparing drug and control within a guess group assumes the "
                "guess is not linked to prognosis.",
                "Patient-guess strata do not remove rater bias; the patient-and-rater sensitivity estimate addresses it when "
                "cells are large enough.",
                "Any stratum with fewer than 5 people in an arm is suppressed by the vault, so the within-trial estimate covers "
                + (f"{eff['within_trial']['n_used']} of {eff['within_trial']['n_total']} participants."
                   if eff.get("within_trial") and eff["within_trial"].get("n_total") else "only the strata that passed.")]
        ct = eff.get("cross_trial")
        if ct and ct.get("synthetic_calibration"):
            lim.append("The cross-trial calibration is SYNTHETIC (data/calibration_synthetic.csv) until real trials are verified.")
        if ct and ct.get("extrapolated"):
            lim.append("This trial's unblinding lies outside the calibration's observed range, so the cross-trial value is extrapolated.")
        after = sum(1 for f in rec["followups"] if f["status"] == "after_close")
        if after:
            lim.append(f"{after} week-12 follow-up visits fall after close-out and will be reported in an addendum.")
        return lim


# ---------------------------------------------------------------------------
def _fmt(e: Optional[dict]) -> str:
    if not e or e.get("md") is None:
        return "not estimable" + (f" ({e.get('why_missing')})" if e and e.get("why_missing") else "")
    return f"{e['md']:+.2f} (95% CI {e['lo']:+.2f} to {e['hi']:+.2f})"


def render_markdown(r: dict) -> str:
    eff = r["effect"]
    L = [f"# FDA blinding report: {r['trial_id']}",
         "",
         f"**SYNTHETIC DATA.** Standard: {r['standard']}. Drafted on day {r['drafted_day']}. "
         f"Primary endpoint locked on day {r['primary_lock_day']}. Status: **{r.get('status', 'draft')}**"
         + (f", signed by {r['signed_by']} on day {r['signed_day']}." if r.get("signed_by") else "."),
         "",
         "## 1. Effect on the primary endpoint",
         f"MADRS points, {eff.get('sign', 'drug minus control; negative favours the drug')}. Basis: {eff.get('basis', 'n/a')}.",
         "",
         "| Estimate | Value |", "|---|---|",
         f"| Reported (naive) | {_fmt(eff.get('reported') or {'md': None, 'why_missing': eff.get('why_missing')})} |",
         f"| Within-trial, same patient guess | {_fmt(eff.get('within_trial'))} |",
         f"| Within-trial, same patient and rater guess (sensitivity) | {_fmt(eff.get('within_trial_rater'))} |",
         f"| Cross-trial calibration | {_fmt(eff.get('cross_trial'))} |"]
    rng = eff.get("adjusted_range")
    if rng:
        txt = (f"Expectancy-adjusted range: {rng['lo']:+.2f} to {rng['hi']:+.2f}" if rng["lo"] != rng["hi"] else
               f"Expectancy-adjusted estimate: {rng['lo']:+.2f} (only one adjustment method was estimable)")
        L += ["", f"**{txt}.** This is a bound under the assumptions below, not the true effect."]
    b = r["blinding"]
    L += ["", "## 2. Blinding", "", "| Who | Group | n | Accuracy (95% CI) | u | Bang (drug arm) |", "|---|---|---|---|---|---|"]
    for key, who in (("participant_overall", "Participants"), ("participant_end_of_treatment", "Participants, end of treatment"),
                     ("participant_by_site", "Participants"), ("rater_by_site", "Raters"), ("rater_by_rater", "Raters")):
        for s in b.get(key, []):
            if s.get("suppressed"):
                L.append(f"| {who} | {s['group']} | {s['n']} | suppressed (under 5) | | |")
            else:
                L.append(f"| {who} | {s['group']} | {s['n']} | {s['accuracy']:.2f} ({s['accuracy_lo']:.2f} to {s['accuracy_hi']:.2f}) "
                         f"| {s['u']:.2f} | {'' if s.get('bang_drug') is None else s['bang_drug']} |")
    L += ["", "## 3. Alerts and human decisions"]
    L += [f"- Day {a['day']}, {a['module']}, {a['severity']}: {a['title']}" for a in r["alerts"]] or ["- No alerts."]
    L += [f"- Day {d['decided_day']}: {d['title']} was **{d['status']}** by {d['reviewer']}" for d in r["decisions"]] or ["- No decisions."]
    if r.get("evidence_log"):
        L += ["", "Messages recorded for this report:"]
        kinds: Dict[str, int] = {}
        for e in r["evidence_log"]:
            kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
        L += [f"- {k}: {n}" for k, n in sorted(kinds.items())]
    L += ["", "## 4. FDA guidance checklist (July 2026)", "", "| Item | Status | Evidence |", "|---|---|---|"]
    L += [f"| {c['item']} | {c['status'].replace('_', ' ')} | {c['evidence']} |" for c in r["checklist"]]
    fu = r["followups"]
    L += ["", "## 5. Follow-up and researcher questions",
          "Follow-up visits: " + (", ".join(f"{k} = {n}" for k, n in sorted(fu["counts"].items())) or "none") + "."]
    L += [f"- {q['id']}: {q['decision']} -> {q['status']}" + (f" (asked {q['asked']})" if q.get("asked") else "")
          for q in r["research_questions"]] or ["- No researcher questions."]
    L += ["", "## 6. Limitations"] + [f"- {x}" for x in r["limitations"]]
    return "\n".join(L)
