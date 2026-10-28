# SocialBoost AI — Creator Analytics Studio

Full-stack social video analysis studio: FastAPI backend, Next.js frontend, SQLite for local development and durable PostgreSQL for production.
Analysis, predictions, calendar and connected-account statistics read from uploaded files, real provider-synced Instagram/YouTube posts, and optional CSV history. Provider metrics that are not returned remain unavailable rather than being fabricated.

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
* **Speech recognition** — local `faster-whisper` (CPU/int8; default model `tiny`) transcribes uploaded video audio when the package/model can initialise. Speech is reported as unavailable rather than fabricated if inference cannot run.
* **On-screen text (OCR)** — local `RapidOCR` is the primary engine, with optional Tesseract fallback. The report includes timestamps/confidence where available and matches detected text to nearby transcript segments by word overlap; this alignment is evidence, not a semantic truth guarantee.
* **Audio detection** — PyAV inspects the uploaded media container for an actual audio stream. Unsupported or malformed containers are marked as undetected rather than assumed to contain audio.

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

## Machine-learning and video-analysis methods

The current workspace models in `backend/app/services/ml_service.py` are:

- **RandomForestRegressor** (scikit-learn, 150 trees): predicts a video's view count from duration, caption length, title length, hashtag count, publication hour/day, and a one-hot platform feature. The expected-view interval is currently the prediction ±25%; it is a heuristic interval, not a calibrated statistical confidence interval.
- **RandomForestClassifier** (scikit-learn, 150 trees): classifies an example as above or below the workspace's median observed view count. The classifier is used as a supporting category signal.
- **Evaluation:** held-out MAE and R² for view regression, held-out accuracy for classification, plus the training-data p10/p50/p90 view percentiles and Random Forest feature importances. These metrics should be interpreted cautiously on small or imbalanced datasets.
- **Training source:** workspace-scoped `HistoricalPost` rows with known, actual view counts from synced provider posts and/or CSV imports. Missing view counts are excluded from supervised training. Engagement-rate summaries only use rows with the required engagement components present.

Video opening analysis additionally uses **faster-whisper** on CPU/int8 for local speech transcription and **RapidOCR** for OCR on sampled frames from the first three seconds. The system timestamps OCR text and speech segments and reports text overlap as evidence; it does not claim that this alignment alone predicts retention. Hook Lab and caption checks currently use transparent deterministic heuristics, not a generative language model. No external inference API is required for these local video-analysis steps, although the first use may need to download the local model assets and the hosted service must have enough memory to initialise them.

## Machine-learning models and evidence pipeline

SocialBoost has two workspace-scoped performance models plus a content-aware Growth Coach. They train only on that workspace's stored history and use real, non-null view-count labels. Syncing linked accounts populates the same `HistoricalPost` dataset used by Overview, Analytics, Recommendations and model training; CSV import is optional for older history that the provider API no longer exposes.

1. **RandomForestRegressor (scikit-learn)** — estimates post views from features such as platform, duration, publication time/day, caption/title length and hashtag count. Model evaluation includes R² and mean absolute error (MAE).
2. **RandomForestClassifier (scikit-learn)** — classifies whether a post is above or below that workspace's median view count.
3. **HistGradientBoostingRegressor (scikit-learn)** — Growth Coach builds a relative growth index from view/engagement signals and produces median, 10th-percentile and 90th-percentile estimates. It uses time-ordered `TimeSeriesSplit` validation and permutation importance when the available history supports them.
4. **TF-IDF + TruncatedSVD** — converts caption/title/hashtag text into numeric text features for the Growth Coach; `StandardScaler` scales numeric features. These are feature-extraction/preprocessing methods, not additional supervised prediction models.

**Video perception is separate from view prediction:** local faster-whisper performs speech-to-text; RapidOCR (or optional Tesseract) reads on-screen text; timestamped word overlap checks where detected screen text appears near spoken text. Hook scoring is a transparent rule-based heuristic, not a learned retention prediction. None of these algorithms can guarantee that a post will go viral or cause account growth.

Minimum training data is enforced by the backend settings (10 samples by default). Missing metrics remain unknown rather than being silently changed to zeros; the app does not fabricate private reach, saves or retention values when a provider does not expose them.

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
