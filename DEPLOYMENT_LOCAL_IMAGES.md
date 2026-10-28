# IhingaAI: local-image deployment release

This complete source package is based on the latest GitHub-ready branded baseline.
The photo library is stored under `assets/backgrounds`, `assets/headers`, `assets/cards`, and `assets/crops`.
The principal landing and section-banner backgrounds are embedded from local JPEGs rather than fetched from Unsplash.
Most other page banners are already loaded from `assets/headers` by the app. The 14 crop photographs include generic placeholder imagery for crops other than maize; do not present them as photographic proof of those species.

## Running locally

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Cloud deployment

Push the contents of the IhingaAI directory (including the two frozen models) to a new repository. Configure Streamlit Community Cloud with `app.py` as the entry point. Set any Gemini API secret in Streamlit's Secrets management, not in Git. Do not upload local SQLite databases, user photos, or credentials. The app's local SQLite storage is not durable on Community Cloud; use the hosted app for demos only until persistent storage is added.

## Checks performed

All Python modules compiled successfully. Both model artifact files were included. All direct Unsplash image references in `app.py` and `assets/theme.css` were removed. The package was screened for bundled private DB and `secrets.toml` files. Live browser and cloud tests are not included.
