# Patches for teammates' modules (not applied)

These bugs are in `unblind/platform/dosing/` (Izzy) or `unblind/platform/postdose/` (Callum), which this pass does not edit. Each entry has the exact change. Danny decides whether to apply it or send it to the owner.

## TP-1 (BL-3, major): primary lock counts week 6 even when the protocol's primary week is 8 (dosing, Izzy)

`unblind/platform/dosing/agents.py:362-367`. The MDMA example's primary endpoint is week 8. Predose schedules week-8 visits (`predose/agents.py:856,870`), but the lock counts week 6, so it reports "0 of 73 participants have a week-6 MADRS".

```diff
-        have = {o["participant"] for o in rec["outcomes"] if o.get("visit_week") == 6}
+        wk = int((rec.get("measurement_plan") or {}).get("primary_week", 6))
+        scale = ((rec.get("protocol") or {}).get("primary_endpoint") or {}).get("scale") or "MADRS"
+        have = {o["participant"] for o in rec["outcomes"] if o.get("visit_week") == wk}
         n = len(rec["enrolled"])
-        ctx.bus.post(self.name, "master", "primary_locked", {"day": day, "with_week6": len(have), "n": n},
-                     f"Primary endpoint locked: {len(have)} of {n} have a week-6 MADRS.")
-        log(rec, self.name, f"Primary endpoint locked: {len(have)} of {n} participants have a week-6 MADRS. "
+        ctx.bus.post(self.name, "master", "primary_locked",
+                     {"day": day, "with_week6": len(have), "with_primary": len(have), "primary_week": wk, "n": n},
+                     f"Primary endpoint locked: {len(have)} of {n} have a week-{wk} {scale}.")
+        log(rec, self.name, f"Primary endpoint locked: {len(have)} of {n} participants have a week-{wk} {scale}. "
```

`unblind/platform/dosing/module.py:190`:

```diff
-                          "body": f"{lock['with_week6']} of {lock['n']} participants have a week-6 MADRS."})
+                          "body": f"{lock.get('with_primary', lock['with_week6'])} of {lock['n']} participants have a "
+                                  f"week-{lock.get('primary_week', 6)} primary outcome."})
```

`with_week6` is kept so existing readers don't break.

Test to add (`tests/platform/test_dosing.py`): run the MDMA example to close and assert that the lock payload has `primary_week == 8` and `with_primary > 0`.

## TP-2 (BL-4, major): MADRS labels on an MDMA/PTSD (CAPS-5) trial (dosing and postdose)

The scale name is hard-coded as "MADRS" in user-facing strings. Every occurrence should read the protocol's scale, with MADRS as the fallback:

```python
scale = ((rec.get("protocol") or {}).get("primary_endpoint") or {}).get("scale") or "MADRS"
```

Sites to change:
- `dosing/agents.py:208` (docstring only)
- `dosing/agents.py:214` ("Recorded {n} rater assessment(s): {scale} plus the rater's guess.")
- `dosing/monitor.py:216` and `:228` (drift explanation and proposed action: "{s} {scale} interviews")
- `dosing/module.py:9` (comment only)
- the postdose views and report text: `grep -n MADRS unblind/platform/postdose/*.py`

Test: run the MDMA example to close and assert that no event text, module view or report contains "MADRS".

## TP-3 (BL-2, major): a rejected researcher question is shown as "ACCEPTED" (postdose, Callum)

`unblind/platform/postdose/agents.py:351` returns `"ok": True` for a rejection. The UI (`frontend/src/components/module/ViewForm.tsx:51`) treats `ok` as "accepted".

```diff
-            return {"ok": True, "question_id": qid, "decision": "reject", "message": res["summary"], "reasons": res["reasons"]}
+            return {"ok": False, "question_id": qid, "decision": "reject", "error": res["summary"],
+                    "message": res["summary"], "reasons": res["reasons"]}
```

Alternatively, the redesign branch can make `ViewForm` treat `decision === "reject"` as not accepted.

Test: submit a leading question and assert `result.ok is False` and `result.decision == "reject"`.

## TP-4 (BL-10, minor): the bias-gate rewrite produces "the study session or the study session capsule" (postdose, Callum)

The rule-based rewrite in `postdose/agents.py` (the rewriting branch after line 315) replaces drug words one at a time, so a phrase like "the dose or the drug capsule" turns into duplicated text. Fix it by replacing the whole matched phrase once, then collapsing repeated "the study session" phrases. Reproduce with the question used in J10 (see `docs/testing/bugs/browser-local.md`, BL-10).

## TP-5 (BL-8 / BP-6, minor): "UNBLIND-BLIND-1" shown in the UI after the rename to Parallax (shared contract)

This is a data-standard identifier shared by predose (`predose/agents.py:257,400,890`), postdose (`postdose/agents.py:32`, `STANDARD`) and `MODULE_CONTRACT.md:44`. Renaming it (for example to `PARALLAX-BLIND-1`) changes the module contract and the export format, so it should be one coordinated change by all three owners, not a patch to one module.

## TP-6 (UI review, minor): "1 adverse events" in the dosing readout (dosing, Izzy)

The note on the "Debriefs structured automatically" KPI is built in the backend, so the frontend shows it as is. With one event it reads "1 adverse events" (and "1 unblinding cues"). Found in the UI review of PR #7 on the Dosing stage.

`unblind/platform/dosing/module.py:162-166`:

```diff
         aes = [a for d in rec["debriefs"] for a in d["adverse_events"]]
+        n_ae = len(aes)
+        n_cues = sum(len(d["unblinding_cues"]) for d in rec["debriefs"])
         out.append({"label": "Debriefs structured automatically", "value": len(rec["debriefs"]), "baseline": 0,
                     "unit": "debriefs", "bottleneck_id": "monitoring_burden",
-                    "note": f"{len(aes)} adverse events and {sum(len(d['unblinding_cues']) for d in rec['debriefs'])} "
-                            "unblinding cues extracted, each with its quote."})
+                    "note": f"{n_ae} adverse {'event' if n_ae == 1 else 'events'} and {n_cues} unblinding "
+                            f"{'cue' if n_cues == 1 else 'cues'} extracted, each with its quote."})
```

Test to add (`tests/platform/test_dosing.py`): with one debrief holding one adverse event and one cue, assert the note reads "1 adverse event and 1 unblinding cue extracted, each with its quote."

## Visuals pass (feat/visuals): data requests, not applied

The charts work today without these. Where a field is missing, the frontend recomputes it from data that already exists in the record, and checks it against the module's own value before using it. These requests would let the charts read the values directly. Details are in `docs/visuals-requests.md`.

### For Izzy (`unblind/platform/dosing/`)
- **TP-6 (R3): drift never resolves.** At D90 the Site B alert still has `resolved_day: None`, although Site B's rolling accuracy is back to about 50%, so no "Drift stopped" marker can be drawn. Set `resolved_day` when the rule that raised the alert clears.
- **TP-7 (possible off-by-one in `monitor.py`).** After a reset, the first batch after the action (`window_from` equal to the action day) is left out of later rolling windows (`window_from > reset_day`). So Site B's rolling value at D56 is 2 of 4, not 5 of 9. Check whether this should be `>=`. The chart shows the value as recorded.
- **Optional (R1):** send `window_correct` and `window_decisive` on each rolling-accuracy chart point. The frontend currently rebuilds them from `record.blinding_metrics`.

### For Callum (`unblind/platform/postdose/module.py`, `_charts`)
- **TP-8: planted truth as an explicit simulated field.** "Planted truth" is hard-coded as −4.0 on every effect-estimate row. Send it from the simulator config as a labelled reference, e.g. `refs: [{y, label: "Planted truth (simulated)"}]`.
- **TP-9: n and SD per MADRS visit week.** The view sends only the mean. The frontend recounts n and SD from `record.outcomes` and `record.followups` with the view's own filter, and shows them only when its mean matches the view's mean.
- **TP-10: counts, bounds and drift markers on the report's rater-accuracy chart.** Per point: `n_correct`, `n_decisive`, `accuracy_lo` and `accuracy_hi`, plus the drift alert days. These are read from `record.blinding_metrics` and `record.alerts` today.

### For the pipeline owner (Studio)
- **TP-11: NCT03866174 arm sizes.** The registry enrolment of 347 is used to impute arms of 173/174. If the published analysis had about 104 participants (unverified; recalled from the JAMA 2023 paper), the reported g would be about 0.91 instead of 0.50, and the adjusted estimate would move by about the same amount. This is a statistics question, outside this presentation pass.
- **TP-12: two sets of blinding cut-offs.** The Studio's blinding words use 0.25 and 0.55; the pre-dosing risk bands use 0.35 and 0.6. Both are drawn as they are in the code. Whether they should match is a decision for the owners.
