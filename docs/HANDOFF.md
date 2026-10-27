# SocialBoost AI — Signal Studio · Handoff / Restart Prompt

Paste this whole file into a fresh session to resume exactly where work stopped.

## What this project is

Full-stack social-video analysis studio. FastAPI + SQLite backend, Next.js (App Router)
frontend. Analysis, prediction, calendar and connected-account statistics all read from
data the user uploads or imports — nothing in the UI is a placeholder metric.

## Where things stand (all of this is DONE)

1. **Backend hardened** — validated inputs, real error paths, per-workspace scoping.
2. **Frontend contract-aligned** — every page talks to the endpoints in `frontend/src/lib/api.ts`.
3. **Full "Duotone premium" redesign** — whole app + marketing. Light canvas `#EFEEEA`,
   paper `#FFFFFF`, ink `#0C0C0A`, signal orange `#F0501F`, cobalt `#2B3AD4`, plus the
   `--night*` dark family. Display type Space Grotesk 700, labels Inter 600, mono for data.
   Old CSS var names (`--porcelain`, `--bg`, `--fg`, `--surface`, `--border`) kept as aliases.
4. **All mock / seeded demo data removed** (user directive: "remove all mock data, ill try my
   original"). Selected scope was "wipe all content, keep accounts" + "remove those too" for
   the landing's illustrative mock-ups. Landing mock-ups are now honest empty states.
5. **End-to-end walkthrough: 42/42 steps passed, zero bugs found.** Run against a throwaway
   account, which was then fully deleted and vacuumed. Honesty verified: before training a
   prediction returns `score: null / category: "unknown" / model_version: "none"`; after
   training it returns real numbers. Bad inputs return 400s.

## Environment (important)

- **Not a git repository.** All changes are uncommitted files on disk.
- Windows. Always `npm.cmd` (not `npm`). Prepend `C:\Program Files\nodejs` to PATH.
  Python: `C:\Users\varun\AppData\Local\Programs\Python\Python312`.
- Prefer `C:\Users\varun\AppData\Local\Temp\opencode` for scratch files.
- **Encoding hazard:** PowerShell `Get-Content -Raw` + `Set-Content` previously corrupted
  UTF-8 in 14 files (repaired once already). For bulk text edits use
  `[System.IO.File]::ReadAllText/WriteAllBytes` with explicit UTF-8, or the `edit` tool.
- Servers: backend `http://127.0.0.1:8000` (uvicorn, started from `backend/`);
  frontend production `http://127.0.0.1:3000` (`npm.cmd run start`, started from `frontend/`).
  Restart either if it is not responding.
- Demo login: `test@test.com` / `pass123` (hint is shown on `/login`).

## Database state (post-wipe, verified)

- 3 users: `test@test.com`, `a@b.com`, `varunpaji@gmail.com`; 3 workspaces; 3 preferences.
- 1 video: the owner's own upload `17003196_3840_2160_60fps.mp4`
  (16:9, 3840×2160, 59.94fps, `has_audio=0`), with 1 analysis job + result, in the workspace
  owned by `test@test.com`.
- Every other content table is 0: videos(1), analysis_jobs(1), analysis_results(1),
  historical_posts, dataset_imports, model_versions, predictions, drafts, scheduled_posts,
  social_accounts.
- `ml/artifacts/` is empty. `uploads/` contains only that one 42.9 MB file.
- Backups from the wipe: DB at
  `C:\Users\varun\AppData\Local\Temp\opencode\backup-socialboost-20261019-151731.db`;
  removed files at `C:\Users\varun\AppData\Local\Temp\opencode\mock-backup-20261019-151930\`.

## REMAINING WORK — the user picked all four of these

### 1. Clear the lint debt (NOT STARTED — nothing fixed yet)

`npm.cmd run lint` → **89 errors / 6 warnings**, all in `frontend/src`. Full report saved at
`docs/handoff/lint-report.txt`. Breakdown:

| Count | Rule |
|-------|------|
| 82 | `@typescript-eslint/no-explicit-any` |
| 5 | `@typescript-eslint/no-unused-vars` |
| 4 | `react-hooks` "Calling setState synchronously within an effect" (e.g. `src/lib/auth.tsx:16`) |
| 2 | "Cannot create components during render" |
| 1 | `@next/next/no-location-assign-relative-destination` (e.g. `src/lib/auth.tsx:31`) |
| 1 | `react/no-unescaped-entities` |

None of it blocks the build. Work through the report file by file.

### 2. Fix README / docs drift caused by the wipe (NOT STARTED)

- `README.md` lines 84–85 point at `ml/data/sample_history.csv`, which was deleted.
- `README.md` line 95 says the demo login was "created by the seed data" — there is no seed
  data any more.
- `ml/scripts/train_models.py` and `ml/scripts/validate_dataset.py` still **default** to the
  deleted `ml/data/sample_history.csv`, so running them with no argument fails confusingly.
  Decide: require an explicit CSV path (preferred — consistent with "no mock data"), or ship
  a small fixture.

### 3. Visual polish pass (NOT STARTED)

- Deeper "poster-grade" pass on `/app/analyze/[id]` and `/app/platform-comparison`.
- Tune orange / contrast at wide desktop width (the dev browser used was only ~800 px, so the
  desktop rail was never visually captured).

### 4. End-to-end walkthrough — DONE (see above). Re-run after any fix.

Optionally re-run `docs/handoff/e2e_walkthrough.py` (it creates a throwaway account, exercises
every frontend-facing endpoint, then `docs/handoff/e2e_cleanup.py` removes it). Update the
`EMAIL` inside the cleanup script from the run output each time.

## Smaller things noticed but not actioned

- `/coach/*` endpoints exist (`train`, `status`, `score`, `winners`, `voice/*`) and are
  **never called by the frontend** — dead API surface. Wire a page or leave as future.
- Backend `ml_service.py` uses `datetime.utcnow()` (deprecated in Python 3.12). Left as-is to
  avoid changing stored-timestamp semantics.
- `docs/` was empty; this handoff folder fills it.

## For the user's own data

- **Reconnect Instagram + YouTube** at `/app/integrations` — the sandbox connections were
  wiped on purpose, so `/app` currently reads "NO ACCOUNT LINKED YET".
- **Import a history CSV** (≥10 rows) at `/app/datasets`, then **train** at `/app/predictions`
  so predictions become real instead of illustrative.
- Their upload is **16:9 with no audio track**, so the aspect check reports "review" and
  speech / audio metrics correctly report **unavailable**. A 9:16 clip with audio gives the
  full readout.
- That upload sits in the **demo workspace** (`test@test.com`). `varunpaji@gmail.com` is empty.

## By design — NOT "left to build" (unless the user asks for new scope)

OCR, speech recognition, live publishing, and real OAuth token exchange are unimplemented and
clearly labelled in the UI. Sandbox scheduling is labelled as sandbox. The scheduler records a
non-sandbox post as failed with an explanation rather than pretending it published.

## Honesty contract to preserve

- No fake metrics anywhere. A metric that was not measured is reported as unavailable.
- Predictions are explicitly illustrative until a workspace model is trained on ≥10 real rows.
- Never invent a number to make a screen look fuller.

## Key files

- `frontend/src/app/globals.css` — duotone design system; every page inherits it.
- `frontend/src/components/app/ui.tsx` — shared workspace primitives.
- `frontend/src/app/app/layout.tsx` — workspace shell + rail nav (Datasets 09, Accounts 10, Settings 11).
- `frontend/src/app/page.tsx` — landing; all illustrative mock-ups replaced with empty states.
- `frontend/src/components/SiteNav.tsx`, `frontend/src/components/Brand.tsx` — marketing nav + wordmark.
- `frontend/src/app/{product,how-it-works,pricing,login,signup}/page.tsx` — marketing/auth surfaces.
- `frontend/src/lib/api.ts` — typed API client (BASE `http://127.0.0.1:8000`, token key `sb_token`).
- `backend/app/api/*.py` — routers; `backend/app/services/*.py` — analysis, ML, scheduler, adapters.
- `backend/socialboost.db` — the live DB described above.
