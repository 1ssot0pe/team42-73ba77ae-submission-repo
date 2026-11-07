"""SYNTHETIC world simulator. Stands in for real people, sites and raters so the
platform can be demonstrated end to end. Nothing here is real data.

Agents never read allocation. Only this simulator peeks at the vault (it plays
the role of reality: real patients who got the drug really do feel it).

Planted events the agents should discover on their own:
  * from day DRIFT_DAY, raters at DRIFT_SITE start sitting in on dosing sessions,
    so their guesses become far more accurate (rater unblinding drift)
  * MISSING_SITE misses check-ins more often (data chasing)
  * some applicants disclose an exclusion only in free text (screening must read it)
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

from .core import Vault

FIRST = ["Alex", "Sam", "Jordan", "Priya", "Tom", "Aisha", "Leo", "Maya", "Ben", "Chloe", "Omar", "Grace",
         "Dan", "Zara", "Kofi", "Ella", "Ravi", "Nina", "Joe", "Ines", "Hugo", "Amara", "Finn", "Lena"]
MEDS = ["none", "sertraline (SSRI)", "escitalopram (SSRI)", "lithium", "venlafaxine (SNRI)", "quetiapine",
        "propranolol", "none", "none", "sertraline (SSRI)"]
SITES = ["Site A (London)", "Site B (Manchester)", "Site C (Bristol)"]


@dataclass
class WorldConfig:
    seed: int = 42
    true_effect: float = 4.0          # true drug benefit on MADRS (points) at primary endpoint
    expectancy_effect: float = 3.0    # extra points of 'improvement' when a patient believes they got drug
    rater_bias: float = 2.0           # extra points when the RATER believes the patient got drug
    drift_site: str = SITES[1]
    drift_day: int = 28
    missing_site: str = SITES[2]


class World:
    def __init__(self, vault: Vault, cfg: Optional[WorldConfig] = None):
        self.v = vault
        self.cfg = cfg or WorldConfig()
        self.rng = random.Random(self.cfg.seed)
        self.people: Dict[str, dict] = {}
        self._baseline: Dict[str, float] = {}

    # ------------------------------------------------------------- recruitment
    def applicants(self, n: int, start_id: int = 1) -> List[dict]:
        r = self.rng
        out = []
        for i in range(start_id, start_id + n):
            age = r.randint(16, 79)
            uk = r.random() < 0.88
            prior = r.choices(["never", "once", "several times"], [0.55, 0.25, 0.20])[0]
            meds = r.choice(MEDS)
            fails = r.choices([0, 1, 2, 3, 4], [0.12, 0.18, 0.35, 0.22, 0.13])[0]
            psychosis = r.random() < 0.04
            bipolar = r.random() < 0.05
            cardio = r.random() < 0.06
            pregnant = r.random() < 0.02
            hidden = r.random() < 0.06
            free = r.choice([
                "I've tried lots of antidepressants and nothing has really helped.",
                "My GP suggested I look into trials.",
                "I read about psilocybin research and want to help.",
                "Depression has affected my work for years.",
                "I'd like to try something different.",
            ])
            if hidden:
                free = r.choice([
                    "I was diagnosed with bipolar disorder last year but I'm stable now.",
                    "I had a psychotic episode at university, but that was a long time ago.",
                    "My cardiologist is monitoring my blood pressure, it's quite high at the moment.",
                ])
            p = {
                "id": f"APP-{i:04d}", "name": f"{r.choice(FIRST)} {chr(65 + r.randint(0, 25))}.",
                "age": age, "phone": ("+44 7" if uk else r.choice(["+1 415", "+33 6", "+49 151"])) + f"{r.randint(100000000, 999999999)}"[:9],
                "country": "UK" if uk else r.choice(["US", "France", "Germany"]),
                "nearest_site": r.choice(SITES), "self_reported_diagnosis": r.choices(
                    ["major depressive disorder", "treatment-resistant depression", "anxiety", "none"], [0.45, 0.35, 0.12, 0.08])[0],
                "failed_antidepressants": fails, "current_medication": meds,
                "history_psychosis": psychosis, "history_bipolar": bipolar, "cardiovascular_condition": cardio,
                "pregnant_or_breastfeeding": pregnant, "prior_psychedelic_use": prior,
                "months_since_last_psychedelic": None if prior == "never" else r.randint(1, 120),
                "can_attend_8_visits": r.random() < 0.9, "consents_to_chatbot_checkins": r.random() < 0.93,
                "consents_to_data_sharing": r.random() < 0.8, "free_text": free,
                "_hidden_exclusion": hidden,      # ground truth for evaluating the screener (agents must not read keys starting with _)
                "applied_day": 0,
            }
            out.append(p)
        return out

    # ------------------------------------------------------------- dosing phase
    def enrol(self, participants: List[dict]) -> None:
        for p in participants:
            self.people[p["id"]] = p
            self._baseline[p["id"]] = self.rng.gauss(32, 4)

    def _believes_drug(self, pid: str, who: str, day: int, site: str) -> float:
        """Probability that `who` (participant|rater|monitor) guesses 'drug'."""
        arm = self.v._arm(pid)
        prior = self.people.get(pid, {}).get("prior_psychedelic_use", "never")
        if who == "participant":
            base = 0.88 if arm == "drug" else 0.25
            if prior != "never":
                base = min(0.97, base + 0.07) if arm == "drug" else max(0.05, base - 0.10)
        elif who == "monitor":
            base = 0.92 if arm == "drug" else 0.15
        else:  # blinded rater
            base = 0.60 if arm == "drug" else 0.42
            if site == self.cfg.drift_site and day >= self.cfg.drift_day:
                base = 0.90 if arm == "drug" else 0.12   # raters started sitting in on sessions
        return base

    def respond_checkin(self, pid: str, day: int, who: str = "participant", site: str = "") -> Optional[dict]:
        site = site or self.people.get(pid, {}).get("site", "")
        miss_p = 0.18 if site == self.cfg.missing_site else 0.05
        if self.rng.random() < miss_p:
            return None
        pd = self._believes_drug(pid, who, day, site)
        x = self.rng.random()
        dk = 0.08 if who == "participant" else 0.05
        guess = "dont_know" if x < dk else ("drug" if self.rng.random() < pd else "control")
        conf = int(min(100, max(0, self.rng.gauss(70 if guess != "dont_know" else 30, 15))))
        expect = None
        if who == "participant":
            expect = int(min(10, max(0, self.rng.gauss(7 if guess == "drug" else 4, 1.5))))
        return {"guess": guess, "confidence": conf, "expectancy": expect}

    def monitor_debrief(self, pid: str, day: int) -> str:
        arm = self.v._arm(pid)
        r = self.rng
        bits = []
        if arm == "drug":
            bits.append(r.choice(["Participant reported strong visual effects for about four hours.",
                                  "Participant was tearful and described a 'profound' experience.",
                                  "Marked perceptual changes from 40 minutes after dosing."]))
            if r.random() < 0.25:
                bits.append(r.choice(["Transient headache in the evening.", "Nausea in the first hour, resolved.",
                                      "Blood pressure rose to 150/95 at 2 hours, settled by 4 hours.",
                                      "Brief anxiety at peak, managed with reassurance."]))
        else:
            bits.append(r.choice(["Participant reported mild relaxation, little else.",
                                  "Participant asked whether they had received the active drug.",
                                  "Session uneventful, participant slept for an hour."]))
            if r.random() < 0.08:
                bits.append("Mild headache, resolved.")
        if r.random() < 0.10:
            bits.append("Outcome rater came into the room briefly during the session.")
        return " ".join(bits)

    def madrs(self, pid: str, day: int, rater_believes_drug: Optional[bool] = None,
              patient_believes_drug: Optional[bool] = None) -> float:
        """MADRS total (0-60, higher = worse). True effect ramps in after dosing (day 1)."""
        arm = self.v._arm(pid)
        base = self._baseline.get(pid, 32.0)
        ramp = min(1.0, max(0.0, day / 21))
        score = base - 6.0 * ramp                                   # everyone improves a bit (placebo response)
        if arm == "drug":
            score -= self.cfg.true_effect * ramp
        if patient_believes_drug:
            score -= self.cfg.expectancy_effect * ramp
        if rater_believes_drug:
            score -= self.cfg.rater_bias * ramp
        return round(min(60, max(0, score + self.rng.gauss(0, 4))), 1)

    def answer_research_question(self, pid: str, question: str) -> str:
        r = self.rng
        return r.choice([
            "It's hard to put into words, but I've felt more connected to people since.",
            "Honestly not much has changed day to day.",
            "Sleep is better. Mood is up and down.",
            "I think about the session a lot. It made me reflect on my family.",
            "I found the check-ins helpful, they kept me on track.",
        ])

    # ------------------------------------------------------------- actions take effect in the world
    def apply_action(self, kind: str, site: str = "", day: int = 0) -> str:
        """Called by an agent AFTER a human approved an action, so the simulation reflects it."""
        if kind == "remote_raters" and site and site == self.cfg.drift_site:
            self.cfg.drift_day = 10 ** 9          # raters no longer sit in on sessions
            return f"{site}: raters moved to remote assessment from day {day}"
        if kind == "reduce_missing" and site == self.cfg.missing_site:
            self.cfg.missing_site = ""
            return f"{site}: reminder protocol improved"
        return "no effect in simulation"
