# SocialBoost AI — Creator Analytics Studio

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

### Production data persistence

The default SQLite database is for local development only. Render Free web services
use an ephemeral filesystem: local SQLite files can disappear when the service spins
down, restarts, or redeploys. This can make an existing account appear to have invalid
credentials because its `users` row no longer exists. A Vercel frontend redeploy does
not erase a database by itself; this is a backend-storage configuration issue.

For a free hosted setup, create a durable PostgreSQL project (for example, Neon), copy
its connection URL, and set it as the backend-only `DATABASE_URL` environment variable
on Render. The backend accepts `postgres://` and `postgresql://` URLs and normalizes
them to the installed psycopg 3 driver. Never put this value in a `NEXT_PUBLIC_*`
variable or commit it to GitHub.

After setting `DATABASE_URL`, redeploy the Render backend and check
`https://YOUR-BACKEND/health`. It should report `"database": "postgresql"` and
`"database_storage": "managed_postgresql"`. If it reports SQLite, durable account
storage has not been enabled yet.

**Keep `SECRET_KEY` unchanged across redeploys.** It signs login tokens and derives
the encryption key for stored OAuth credentials. Changing it invalidates existing JWTs
and makes previously encrypted OAuth tokens unreadable.

If you have a backup copy of the old `socialboost.db`, migrate its rows before asking
users to register again:

```bash
# Run from the repository root; DATABASE_URL must point to an empty PostgreSQL database.
DATABASE_URL='postgresql://…' python backend/scripts/migrate_sqlite_to_postgres.py /path/to/socialboost.db --dry-run
DATABASE_URL='postgresql://…' python backend/scripts/migrate_sqlite_to_postgres.py /path/to/socialboost.db
```

The migration script never changes the SQLite source and refuses to write into a
non-empty target database. If Render has already discarded the only copy of the old
SQLite file, those deleted users cannot be reconstructed from the new empty database;
the persistent database prevents this from happening to future accounts.

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

## Configure public YouTube channel lookups

The public analytics page at `/app/youtube` can use a server-side `YOUTUBE_API_KEY` to read public channel totals and recent uploads without depending on a user's OAuth access token. In Google Cloud Console, enable **YouTube Data API v3**, create an API key, and restrict the key to that API. Add `YOUTUBE_API_KEY` to the **Render backend environment only**; never add it to Vercel or a `NEXT_PUBLIC_*` variable, and never commit it to GitHub.

When a server key is configured, public-channel requests use the key without sending the connected account's OAuth bearer token. If the key is not configured, SocialBoost falls back to the connected Google account and attempts to refresh expired access tokens. The OAuth-only connected-channel path continues to use OAuth rather than an API key.

## Configure YouTube OAuth on Render

The Integrations page only shows **Connect YouTube** after both `YT_CLIENT_ID` and
`YT_CLIENT_SECRET` are configured on the backend. These are Google Cloud OAuth
credentials; do not put the client secret in Vercel or the frontend.

1. In [Google Cloud Console](https://console.cloud.google.com/), select or create a project.
2. Open **APIs & Services → Library** and enable **YouTube Data API v3**.
3. Configure **Google Auth Platform** (OAuth consent screen). While the app is in
   Testing, add the Google account you will use to connect as a test user.
4. Create an OAuth client of type **Web application**.
5. Add this exact **Authorized redirect URI** to the OAuth client:
   `https://socialboost-yzx2.onrender.com/social/oauth/youtube/callback`
6. In Render → SocialBoost → **Environment**, set:
   - `YT_CLIENT_ID` = the Web application client ID.
   - `YT_CLIENT_SECRET` = the matching client secret.
   - `OAUTH_REDIRECT_BASE` = `https://socialboost-yzx2.onrender.com` (base URL only, no callback path).
   - `FRONTEND_URL` = `https://socialboostweb.vercel.app`.
7. Save the environment variables and let Render deploy. Refresh
   `/app/integrations`; YouTube should show **Connect YouTube**. Sign in with the
   Google account that owns or manages the channel and approve the read-only
   YouTube scope.

Google requires the redirect URI in the request to exactly match an authorized
URI on the OAuth client. For apps left in external **Testing** with YouTube
scopes, refresh tokens can expire after seven days; publish/verify the consent
screen as appropriate before relying on long-running unattended syncs. See the
[Google server-side OAuth guide](https://developers.google.com/youtube/data/guides/auth/server-side-web-apps)
and [Google OAuth token lifetime rules](https://developers.google.com/identity/protocols/oauth2).

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
