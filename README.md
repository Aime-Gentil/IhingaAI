# IhingaAI — Smarter Farming Together

A Streamlit agricultural decision-support application with farmer, agronomist and planner roles.

## Run locally

Use Python 3.11 or 3.12, install `requirements.txt`, then run:

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

To activate AI features, configure `.streamlit/secrets.toml` locally or the equivalent Streamlit Cloud secret setting. Do not commit secrets or private farmer records.

## Cloud deployment

Deploy `app.py` as the Streamlit entrypoint. Both trained prediction model files must be included in `data/`. Ensure host resource limits are sufficient. SQLite and locally uploaded photo storage are **ephemeral** on Streamlit Community Cloud; treat a deployment there as a demo until persistent storage and backups are implemented.

## Brand and acknowledgements

The user-provided IhingaAI logo is stored in `assets/brand/`. Its original bitmap is 192×172 px, with a high-density resampled version supplied for layout rendering; it is not a native vector logo. The application has an **About & Data Sources** page available to every authenticated role. See `DATA_SOURCES.md` for source attribution and limitations.
