"""Labelled test set for the bias gate: 15 researcher questions, 5 per expected decision.

Labels were written by the post-dosing owner BEFORE the gate rules were tuned, and
cover all five checks: (1) unblinding cues, (2) leading or expectancy wording,
(3) identifying or personal data, (4) safety content needing a clinician,
(5) timing and consent. Used by tests/platform/test_postdose.py and
eval/platform/bias_gate_eval.py. These are invented questions, not real ones.
"""

QUESTIONS = [
    # ---- approve: neutral, non-identifying, no safety content
    {"text": "How would you describe your sleep over the past two weeks?", "expected": "approve", "check": "none"},
    {"text": "What, if anything, has changed in your daily routine since the study began?", "expected": "approve", "check": "none"},
    {"text": "How easy or hard was it to attend the study visits?", "expected": "approve", "check": "none"},
    {"text": "Were the reminder messages from the study team useful? Why or why not?", "expected": "approve", "check": "none"},
    {"text": "How would you describe your relationships with the people close to you at the moment?", "expected": "approve", "check": "none"},
    # ---- rewrite: fixable unblinding cues or leading wording
    {"text": "How intense were the visuals during your psilocybin session?", "expected": "rewrite", "check": "unblinding"},
    {"text": "How much better do you feel since you took the drug?", "expected": "rewrite", "check": "unblinding+leading"},
    {"text": "Describe your mystical experience during the trip.", "expected": "rewrite", "check": "unblinding"},
    {"text": "How has your mood improved since the session?", "expected": "rewrite", "check": "leading"},
    {"text": "What benefits have you noticed from the treatment?", "expected": "rewrite", "check": "leading"},
    # ---- reject: cannot be made safe by rewording
    {"text": "Wouldn't you say the treatment was life-changing?", "expected": "reject", "check": "leading"},
    {"text": "Do you think you were in the drug group or the placebo group?", "expected": "reject", "check": "unblinding"},
    {"text": "Please give us your full name and phone number so we can follow up.", "expected": "reject", "check": "personal"},
    {"text": "Have you had any thoughts of suicide since the session?", "expected": "reject", "check": "safety"},
    {"text": "Can we contact your GP to ask how you are doing?", "expected": "reject", "check": "consent"},
]
