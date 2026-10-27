# KBN5 — 5 Minutes in Kiriburu

KBN5 is a local quick-commerce prototype with a central Flask API,
a Flutter customer app, a customer website, Firebase Authentication,
and a shared business database.

## Local development

Use Python and a virtual environment in Termux.

The local database defaults to SQLite at `instance/kbn5.db`.
Set `DATABASE_URL` in `.env` to use another supported database.

## Deployment

Render uses `requirements-render.txt` and `render.yaml`.
Configure Firebase project settings before enabling authentication.
Production image uploads need persistent or cloud storage.
