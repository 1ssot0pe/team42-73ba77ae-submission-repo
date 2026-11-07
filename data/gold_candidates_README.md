# gold_candidates.csv: candidate gold-standard set (UNVERIFIED)

Every row has `verified = NO - needs human check`. Nothing here is gold until a person opens
`source_url` and confirms `quote`. Values were extracted on 2026-11-07.

## Format

Long format, one row per trial per field:
`trial_name, registry_id, field, value, quote, source_url, notes, verified`

- `value` is blank when the fact was not found on any page that was actually fetched.
- `quote` is the verbatim text returned by the fetch tool. The tool caps quotes at about 125
  characters and runs through a summarising model, so treat each quote as "should be verbatim"
  and check it against the source. Where the source was a table, the quote is the table row as
  returned, not a sentence.
- `notes` containing **DERIVED** means the value was computed from quoted counts
  (for example overall guess accuracy from two per-arm counts). The arithmetic is in the note.
- `|` inside a quote separates two separate snippets from the same page.
- Effect signs are kept as the paper reports them. They are NOT harmonised: MAPP1 (+11.9) and
  Bogenschutz (+13.86) report benefit as positive, while most others report it as negative.

## Fields

registry_id, citation, doi, pmid, pmcid, open_access, drug, indication, comparator_type
(inert_placebo / active_placebo / low_dose_same_drug / other_active / waitlist_or_none),
comparator_detail, rater_placement (central_remote / blinded_unspecified / onsite_unblinded),
prior_exposure (0-1), primary_endpoint, effect_est, effect_lo, effect_hi, effect_d, n_drug,
n_control, guess_acc_participants, guess_acc_raters.

## What was searched

- WebSearch for each named trial, plus blinding-specific queries ("correctly guessed",
  "blinding integrity", "allocation guess").
- Full text or abstracts fetched from:
  - nature.com (MAPP2)
  - pmc.ncbi.nlm.nih.gov (MAPP1 only, before the captcha appeared)
  - Europe PMC REST API on www.ebi.ac.uk, through WebFetch rather than the shell (MAPP2 XML,
    von Rotz XML, Ross XML, and abstracts for Carhart-Harris, Goodwin and Holze)
  - jamanetwork.com (Raison, Bogenschutz, Yngwe, Hendricks, EPISODE, MM120, and the 2026 review)
  - cambridge.org (Palhano-Fontes; Szigeti expectancy paper)
  - repositorio.ufrn.br (Palhano-Fontes author PDF)
  - bibliography.maps.org (Mithoefer 2018, Gasser 2014 PDFs)
  - research.rug.nl (Goodwin abstract)
  - Compass press releases (q4cdn PDF, SEC 8-K, sttinfo.fi Business Wire mirror)
  - HRA UK research summary and ctv.veeva.com registry mirrors (Compass NCT IDs)
  - psychiatrist.com: J Clin Psychiatry article 22r14518, "Table 3. Summary of Blind Integrity
    Assessments". This is a **secondary source** used only where marked.

## Sources that refused or failed

- **pubmed.ncbi.nlm.nih.gov**: blank page or rate limit twice, including the 2026 review
  (PMID 41984443). No PMIDs come from PubMed pages. PMIDs that appear only in search-result URLs
  are listed in `notes` as unverified.
- **pmc.ncbi.nlm.nih.gov**: worked once (MAPP1), then showed a reCAPTCHA interstitial
  (MAPP2, Bogenschutz).
- **Europe PMC**: rate-limited several times. The Palhano-Fontes XML failed twice. One
  multi-DOI query was rejected for URL length, and a second failed with a client error.
- **nejm.org**: client error, so no NEJM full text (Carhart-Harris, Goodwin).
- **research.rug.nl PDF**, **biologicalpsychiatryjournal.com** (Holze full text), and
  **zora.uzh.ch** (Anubis block): failed.
- **The shell** cannot reach external hosts (the proxy returned 403 for an ordinary PDF host), so
  no PDFs were downloaded locally.
- **clinicaltrials.gov** was not used, as instructed. NCT IDs come from papers, press-release
  mirrors, HRA and ctv.veeva.com.

## The 2026 JAMA Psychiatry review (best potential gold source): NOT obtained

Orsini DK, ..., Rosenblat JD. "Blinding Integrity in Psychedelic Randomized Clinical Trials:
A Systematic Review." JAMA Psychiatry 2026;83(7):755-769. doi:10.1001/jamapsychiatry.2026.0255.
https://jamanetwork.com/journals/jamapsychiatry/fullarticle/2847667

- The accessible page showed the abstract only: 112 RCTs, 33 (29.5%) assessed blinding,
  "No control strategy consistently achieved ideal blinding".
- No per-trial table or eTable was visible.
- The copyright line is "© 2026 American Medical Association. All rights reserved", so the
  article is not open access.
- **Action for a human:** get the full text and supplement through institutional access. It
  should list per-trial blinding values for all 33 trials. Cross-check every guess value below
  against it.

## Per-trial confidence

**Tier A: guess data in the primary paper, fetched**

| Trial | Confidence | Caveats |
|---|---|---|
| MAPP2 (Mitchell 2023, NCT04077437) | High | Participant guesses per arm (placebo 33/44, MDMA 49/52) from an end-of-study survey. Overall 0.854 is derived. No rater guesses. |
| Bogenschutz 2022 (NCT02061293) | High | Accuracy is pooled across arms and counted per session (93.6% and 94.7%). "Rater" values are therapists (92.4% and 97.4%), not TLFB assessors. PMID/PMCID not verified. |
| Yngwe 2026 (NCT04630964) | High | Rater guesses at day 8 per arm (12/17, 15/17) are good rater data. Participant guesses were collected at **day 365**, not at the endpoint. The comparator quote (niacin "active placebo") still needs a verbatim capture. |
| Hendricks 2026 (NCT02037126) | Medium-high | Participant guesses per arm (18/20, 9/19). The therapist value 39/40 is not an outcome-rater value. The effect is a model β, not a raw mean difference. |
| Gasser 2014 (NCT00920387) | Medium | Very small (n=12). Guesses are session-level dose guesses (200 vs 20 µg). No between-group mean difference reported. |
| Mithoefer 2018 (NCT01211405) | Medium | Three-arm dose guess, so not a binary drug-vs-placebo accuracy. Participant accuracy of 0.463 is derived from "incorrectly for 53.7%". |
| MAPP1 (Mitchell 2021, NCT03537014) | Effect high; guess low | No formal blinding assessment. The authors call the incorrect-belief counts "anecdotal" (at least 7/44 and 2/46). **Do not use as gold guess accuracy.** |
| Palhano-Fontes 2019 (NCT02914769) | Medium-low | Primary paper says 5 placebo patients misclassified placebo as ayahuasca. Only the secondary JCP table says no ayahuasca patient guessed placebo. Overall 24/29 is NOT stored as a value. No mean difference, only Cohen's d. |

**Tier B: blinding assessed, but values only in inaccessible supplements or secondary sources**

| Trial | Status |
|---|---|
| EPISODE (Mertens 2026, NCT04670081) | Patient and therapist guesses are in eTables 21 and 23 (Supplement 1). Primary endpoint is binary response; the -4.60 HAMD17 value is a secondary outcome. |
| MM120 (Robison 2025, NCT05407064) | Methods say participant and rater blinding was assessed on a 5-point questionnaire; results were not reachable. The primary analysis is MCP-Mod dose-response, and -5.0 is the 100 µg vs placebo week-4 contrast. |
| Holze 2023 LSD anxiety | Effect from the Europe PMC abstract. Guess data only from the secondary JCP table ("Only one patient in the LSD-first group mistook LSD as placebo", no denominator). NCT03153579 not confirmed on a fetched page. |
| Ross 2016 (NCT00957359) | Staff guess of 28/29 (97%) comes only from the secondary JCP table; not found in the primary full text. Effect sizes are in a figure only. |

**Tier C: effect and registry data only, no guess data**

| Trial | Status |
|---|---|
| Carhart-Harris 2021 (NCT03429075) | Szigeti et al. confirm "No 'treatment allocation guess' data was collected". The abstract prints the effect as "2.0 points (95% CI -5.0 to 0.9)". This is a sign inconsistency in the source; check the NEJM full text. |
| COMP001 (Goodwin 2022, NCT03775200; EudraCT 2017-003288-36) | No guess data found. NEJM full text inaccessible. |
| COMP005 (NCT05624268) | Press releases only: -3.6 [-5.7, -1.5] at week 6, 258 dosed. No per-arm n and no blinding data. |
| COMP006 (NCT05711940; EudraCT 2022-002339-73) | Press release only: -3.8 [-5.8, -1.8] at week 6 for 25 mg vs 1 mg, 581 dosed. |
| Raison 2023 (NCT03866174) | Strong design facts (remote central MADRS raters, niacin, prior-use 23/104). Guess data not found; the Discussion and supplement were truncated by the paywall. |
| von Rotz 2023 (NCT03715127) | No guess data. MADRS mean difference reported inconsistently (-13.0 in the Discussion; CI -15.0 to -1.3). Placebo substance not quoted. |

Fetched but left out of the CSV:

- **Griffiths 2016** (NCT00465595, CC BY 3.0): no guess data found in the full text. Pre-crossover
  d = 1.30 (GRID-HAMD) and 1.23 (HAM-A). 45% had prior hallucinogen use.
- **Ot'alora 2018** (NCT01793610, CC BY-NC 4.0): no guess data found. Cohen's d 0.42 (125 mg)
  and 0.37 (100 mg) vs 40 mg.

## Ambiguities to resolve

1. **Guess accuracy is reported in different ways.**
   - Per arm: MAPP2, Hendricks, Yngwe.
   - Pooled per session: Bogenschutz, Gasser, Mithoefer.
   - Incorrect-only lower bounds: MAPP1.
   - Count of misclassified placebo only: Palhano-Fontes.

   The tool will probably need per-arm values. The pooled value is stored in `value`, and the
   per-arm values are in `notes`.
2. **"Raters" usually means therapists.** Bogenschutz, Hendricks, Mithoefer, Gasser and Ross
   report therapist or staff guesses. Only Yngwe reports a guess by the blinded outcome rater.
3. **Timing of the guess differs.**
   - End of study: MAPP2 (visit 20), Yngwe participants (day 365).
   - Per session: Bogenschutz, Gasser.
   - Day 8: Yngwe rater.
4. **Crossover designs** (Holze, Ross, Griffiths): the first-period between-subjects contrast
   is primary.
5. **Prior exposure is measured differently.**
   - MDMA only: MAPP1, MAPP2, Mithoefer.
   - LSD only: Gasser.
   - Any psychedelic: Raison, von Rotz, EPISODE.
   - Hallucinogen: Hendricks, Ross.
   - Zero by exclusion: Yngwe, Palhano-Fontes.
6. **Endpoint scales differ** (CAPS, MADRS, HAMD, QIDS-SR, STAI, PHDD, percentage abstinent
   days), so effect_est cannot be compared across trials without standardising.

## Licence and terms by source

| Source | Licence |
|---|---|
| MAPP1 and MAPP2 (Nature Medicine) | CC BY 4.0; quoting and reuse with attribution is fine |
| von Rotz (eClinicalMedicine) | CC BY |
| Palhano-Fontes (Psychological Medicine) | CC BY |
| Ross 2016 and Griffiths 2016 (J Psychopharmacol) | CC BY 3.0 |
| Gasser 2014 | CC BY-NC-ND 3.0; non-commercial, no derivatives. Short factual extraction is fine; do not redistribute the PDF |
| Ot'alora 2018 | CC BY-NC 4.0 |
| Szigeti 2024 | CC BY-NC-SA 4.0 |
| JAMA Network Open (Yngwe, Hendricks) | Open access. Permission links point to CC BY (Yngwe) and CC BY-NC-ND (Hendricks); the licence line was not captured, so check it |
| JAMA, JAMA Psychiatry (Raison, Bogenschutz, EPISODE, MM120, the 2026 review) | Treat as copyrighted (© AMA) unless the article shows an OA licence. Bogenschutz is in PMC and may be CC BY; check |
| NEJM (Carhart-Harris, Goodwin) | Copyrighted; abstract-level facts only |
| Biological Psychiatry (Holze) | Europe PMC lists CC BY but flags it as not OA; check |
| Europe PMC and PubMed abstracts | Abstracts remain under the publisher's copyright. Short factual quotes for research use are standard, but do not bulk-redistribute abstract text |
| Press releases and SEC filings (Compass) | Public company disclosures; facts are free to use. These are not peer-reviewed and are described as preliminary |
| J Clin Psychiatry Table 3 (psychiatrist.com) | Copyrighted. Used only as a pointer to secondary data; replace with primary sources |
| Registry mirrors (ctv.veeva.com, HRA) | Facts only; confirm on clinicaltrials.gov by hand |

Facts themselves (numbers, IDs) are not copyrightable. The verbatim quotes are short excerpts
kept for verification, which fits normal fair-dealing / fair-use practice. Do not ship long
quotes in a public product without checking the licence.
