# UNBLIND: one-page write-up

**The problem.** Psychedelic trials cannot stay blinded, because patients and clinicians can tell who tripped. A 2026 review of 112 randomised psychedelic trials found only 29.5% assessed blinding at all. Those that did often reported failure above 90%. Every reported effect is therefore drug plus expectation, measured on the same people at the same moment, so no single trial can separate the two. The FDA's July 2026 final guidance names this functional unblinding as the central threat to validity. It was central to the 2024 rejection of the MDMA application. And it hangs over the current psilocybin filings: Compass reported a 3.6-point MADRS difference against placebo (COMP005) and 3.8 points against 1 mg psilocybin (COMP006).

**What we built.** A multi-agent pipeline that turns any trial handle into a checked evidence ledger and an expectancy-corrected effect with an interval. Eight agents:

- **Resolver:** finds the trial behind any input
- **Hunter:** finds the paper, reformulating its search on a miss
- **Outcome extractor:** picks the number matching the registered primary endpoint
- **Design extractor:** reads the design with results redacted, so outcomes cannot sway it
- **Blinding hunter:** searches paper, then supplement, then protocol PDF, and flags blinding checks that were planned but never reported
- **Auditor:** deterministic code, not an LLM. Every quote must appear word for word in its source
- **Statistician:** plain code
- **Design advisor:** ranks the comparator, rater and sample changes that would most reduce bias

A named human signs off every output and every row added to the calibration corpus.

**Who it helps.** A clinical development lead writing a Phase 2b or 3 psychedelic protocol this quarter. Before locking the design, they see how much bias it will likely carry and which change buys the most. They arrive at an FDA meeting with a number rather than an argument.

**Data.** All public: ClinicalTrials.gov API v2 (public domain), Europe PMC open-access full text and supplements (licence recorded per article), protocol PDFs posted on the registry, and optionally the CC0 Hugging Face protocol corpus. No patient-level data. The demo calibration is synthetic and labelled as such everywhere. Real trials join only after human approval. The candidate gold set has 18 real trials with quotes and URLs, flagged as unverified.

**Evaluation.**

1. **Planted-truth simulation** (synthetic; 60 trials, 300 runs per scenario).
   - **When expectancy is the only bias:** a standard meta-analysis overstates the effect by 0.43 g and almost never contains the truth. UNBLIND is within 0.01 g, with 98% coverage, but with intervals several times wider.
   - **When improvement causes correct guessing (reverse causation):** UNBLIND over-subtracts by 0.15 g.
   - **Under cross-trial confounding:** it does worse than doing nothing.
2. **Extraction accuracy against a hand-verified gold set,** with honest abstention scored separately from misses.
3. **Baseline:** single-shot Gemini versus the pipeline, run on masked and unmasked text to measure how much the model "remembers" from the news rather than reads.

**Limits.** Reverse causation and confounding are stated on every report, and the corrected value is presented as a conservative bound. A low-dose comparator mixes better blinding with real pharmacology. Data are sparsest near zero unblinding, exactly where the intercept lives and where non-hallucinogenic compounds sit. The tool estimates contamination, not efficacy.

**Safeguards.**

| Risk | Safeguard |
|---|---|
| Wrong extraction | Verbatim quote audit; unproven facts become unknown |
| Outcome leaking into design reading | Results firewall on the design extractor |
| Prompt injection in fetched documents | Treated as data only, schema-checked and flagged in the report |
| Agent sent to arbitrary sites | Host allowlist |
| Poisoned calibration | Human-approved corpus only |
| Output treated as a verdict | Mandatory sign-off, with a fingerprint of the report logged |
