"""STUB modules. Used by the master ONLY when the real dosing / postdose module
cannot be imported (before Callum and Izzy merge). They do the minimum so the
platform runs end to end; every view they return is labelled STUB.

Do not extend these. The real modules replace them automatically.
"""
from __future__ import annotations

from ..core import BaseModule, Ctx, TrialRecord


class StubDosing(BaseModule):
    name = "dosing"
    title = "Dosing (STUB until Izzy's module is merged)"

    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if not rec["enrolled"]:
            return
        for s in rec["schedule"]:
            if s.get("owner") != "dosing" or s.get("day") != day or s.get("status") != "scheduled":
                continue
            if s["kind"] in ("participant_checkin", "rater_assessment") and ctx.world is not None:
                who = "participant" if s["kind"] == "participant_checkin" else "rater"
                r = ctx.world.respond_checkin(s["participant"], day, who, s.get("site", ""))
                if r is None:
                    s["status"] = "missed"
                    continue
                rec["checkins"].append({"participant": s["participant"], "site": s.get("site", ""), "day": day,
                                        "who": who, "rater_id": s.get("rater_id"), "guess": r["guess"],
                                        "confidence": r["confidence"], "expectancy": r["expectancy"], "channel": "text"})
            s["status"] = "done"
        guesses = [{"participant": c["participant"], "guess": c["guess"], "all": "all"}
                   for c in rec["checkins"] if c["who"] == "participant"]
        if guesses:
            for m in ctx.vault.blinding_stats(guesses, "all", "stub_dosing"):
                rec["blinding_metrics"].append(dict(m, day=day, who="participant", by="overall"))
        last_primary = max((s["day"] for s in rec["schedule"] if s.get("kind") == "rater_assessment"), default=64)
        if day == last_primary + 1 and not rec.get("primary_lock_day"):
            ctx.bus.post("dosing", "master", "primary_locked", {"day": day}, "All week-6 assessments done (stub).")

    def view(self, rec: TrialRecord) -> dict:
        v = super().view(rec)
        v["cards"] = [{"title": "STUB", "body": "Placeholder dosing module. Izzy's real module replaces this.", "tone": "warn"}]
        return v


class StubPostdose(BaseModule):
    name = "postdose"
    title = "Post-dosing (STUB until Callum's module is merged)"

    def on_day(self, rec: TrialRecord, day: int, ctx: Ctx) -> None:
        if day == 90 and not rec["report"]:
            rec["report"] = {"status": "draft", "stub": True,
                             "markdown": "# FDA blinding report (STUB)\nCallum's module produces the real report."}
            rec.event("postdose(stub)", "drafted placeholder report", "info", "postdose")

    def view(self, rec: TrialRecord) -> dict:
        v = super().view(rec)
        v["cards"] = [{"title": "STUB", "body": "Placeholder post-dosing module. Callum's real module replaces this.", "tone": "warn"}]
        return v


class StubPredose(BaseModule):
    """Only for tests of the master before Danny's predose exists: enrols 24 synthetic people."""
    name = "predose"
    title = "Pre-dosing (STUB)"

    def setup(self, rec: TrialRecord, ctx: Ctx) -> None:
        apps = ctx.world.applicants(24)
        sites = ["Site A (London)", "Site B (Manchester)", "Site C (Bristol)"]
        enrolled = []
        for i, a in enumerate(apps):
            site = sites[i % 3]
            enrolled.append({"id": a["id"], "name": a["name"], "site": site,
                             "stratum": f"{site}|{'naive' if a['prior_psychedelic_use'] == 'never' else 'experienced'}",
                             "prior_psychedelic_use": a["prior_psychedelic_use"], "dosing_day": 1 + i % 20,
                             "consents": {"checkins": True, "data_sharing": True}})
        ctx.vault.randomise(enrolled, "stratum")
        rec["enrolled"] = enrolled
        for p in enrolled:
            d = p["dosing_day"]
            rid = "R-" + p["site"][5] + "1"
            rec["schedule"] += [
                {"id": f"{p['id']}-dose", "participant": p["id"], "site": p["site"], "day": d, "kind": "dosing_session", "owner": "dosing", "instrument": "session", "status": "scheduled"},
                {"id": f"{p['id']}-ci1", "participant": p["id"], "site": p["site"], "day": d + 1, "kind": "participant_checkin", "owner": "dosing", "instrument": "UB1-PG", "status": "scheduled"},
            ] + [{"id": f"{p['id']}-rv{w}", "participant": p["id"], "site": p["site"], "day": d + 7 * w, "kind": "rater_assessment",
                  "owner": "dosing", "instrument": "MADRS+UB1-RG", "status": "scheduled", "rater_id": rid} for w in (1, 3, 6)]
        ctx.bus.post("predose", "master", "enrolment_complete", {"n": len(enrolled)})
