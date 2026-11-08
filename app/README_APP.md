# Parallax demo app

Run from the repo root:

```
streamlit run app/app.py
```

Offline demo with the invented fixture trials (no internet needed):

```
UNBLIND_OFFLINE=1 streamlit run app/app.py
```

Then press **Load fixture demo** in the sidebar and **Run**. NCT99999901 and NCT99999902 are INVENTED test trials.

- Set `GEMINI_API_KEY` to turn on Gemini extraction. Without it the agents use deterministic rules.
- `UNBLIND_CACHE` sets the response cache folder.
- Sign-offs are appended to `data/signoffs.jsonl`. Approved real trials can be added to `data/calibration_real.csv`.
- Reports from `python -m unblind build-corpus` can be reviewed with **Load saved report JSON** in the sidebar.
