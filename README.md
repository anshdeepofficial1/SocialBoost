# SocialBoost AI — Signal Studio

Full-stack social video analysis studio: FastAPI + SQLite backend, Next.js frontend.
Analysis, prediction, calendar and connected-account statistics all read from data
you upload or import. Nothing in the UI is a placeholder metric.

## Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

The server creates missing tables and upgrades an existing development database
on startup (`app/db/schema.py`). No manual reset is needed.

### Tests

```bash
cd backend
python -m pytest -q
```

The suite runs against a temporary database, upload directory and model
directory, so your development data is untouched.

### Configuration

Copy `.env.example` to `.env`. Relative paths are resolved against the project
root, so the server behaves identically whether started from the repository root
or from `backend/`.

## Frontend

```bash
cd frontend
npm install
npm run dev
```

Production:

```bash
npm run build
npm start
```

Set `NEXT_PUBLIC_API_URL` if the backend is not on `http://127.0.0.1:8000`.

## What the backend actually does

| Area | Behaviour |
| --- | --- |
| Auth | Email + password (bcrypt), JWT bearer tokens, per-user workspace |
| Upload | MP4/MOV/WebM/MKV, size-limited, metadata read with OpenCV |
| Analysis | Real frame measurements (brightness, contrast, scene changes, black frames), rule-based opening score with its basis listed, technical checks, recommendations |
| Predictions | Random forest per workspace, trained on your imported history; ranges, confidence and feature importance come from that model |
| Datasets | CSV import with required-column validation, row rejection, duplicate `post_id` detection, template download |
| Calendar | Real month scheduling, update/cancel/delete, restart-safe jobs |
| Publishing | Sandbox jobs are marked `sandbox`. Live publishing is not implemented, so non-sandbox jobs are marked `failed` with an explanation — never `published` |
| Connected accounts | Sandbox connections store the handle and derive statistics from imported history |
| Analytics | Aggregates per workspace, per platform, with a consistent engagement definition (likes + comments + shares over views) |
| Drafts | Workspace-scoped caption/title drafts, optionally attached to a video |

### Capabilities that are deliberately reported as unavailable

* **OAuth authorisation** — without provider credentials the start endpoint
  returns `400` and sandbox mode is used instead. With `IG_*`/`YT_*` client
  id and secret configured, the full OAuth flow runs: state-protected
  authorisation, server-side token exchange, tokens encrypted at rest with a
  `SECRET_KEY`-derived key, one-time state consumption, and a redirect back to
  the frontend. Read-only scopes only.
* **Live publishing** — not implemented. See the publishing row above.
  OAuth-linked YouTube accounts can pull live channel statistics (subscribers,
  views) on Recalculate; everything unreachable falls back to imported history.
* **Speech recognition** — not installed. Analysis reports
  `speech_analysis: "unavailable"` instead of inventing a transcript.
* **OCR** — only runs when Tesseract is installed; otherwise the report states
  that on-screen text was not read.
* **Audio detection** — `has_audio` is reported as `false` because `ffprobe` is
  not part of this build.

## ML scripts

```bash
python ml/scripts/validate_dataset.py ml/data/sample_history.csv
python ml/scripts/train_models.py ml/data/sample_history.csv
python ml/scripts/predict.py --platform instagram --duration 24 --caption "How I edit"
python ml/scripts/evaluate_models.py
```

Models are stored per workspace under `ml/artifacts/`, so one account can never
score another account's data.

## Demo login

`test@test.com` / `pass123` (created by the seed data in the development database).
