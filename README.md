# t_bookmarks

Local-first app that imports your X bookmarks, stores them in SQLite, and makes them searchable through a local HTML UI.

## Features

- OAuth 2.0 Authorization Code + PKCE login for X
- Bookmark sync from `GET /2/users/{id}/bookmarks`
- SQLite storage with FTS5 full-text search
- Local FastAPI backend
- Local HTML/JS UI
- Manual sync + optional periodic background sync

## Requirements

- Python 3.12+
- An approved X developer account
- An X Project + App with OAuth 2.0 enabled
- Redirect URI configured, e.g. `http://127.0.0.1:8000/auth/callback`
- Scopes:
  - `bookmark.read`
  - `tweet.read`
  - `users.read`
  - `offline.access`

## Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for Python environment and dependency management.

1. Create the environment and install dependencies:

   ```bash
   uv sync
   ```

2. Copy env file:

   ```bash
   cp .env.example .env
   ```

3. Fill in `.env`:

   - `X_CLIENT_ID`
   - `X_CLIENT_SECRET` (optional for public clients)
   - `X_REDIRECT_URI`
   - `APP_SECRET_KEY`

4. Install the git pre-commit hook:

   ```bash
   uv run pre-commit install
   ```

5. Run the app:

   ```bash
   uv run uvicorn app.main:app --reload
   ```

6. Open:

   ```
   http://127.0.0.1:8000
   ```

## Code quality

Run the checks manually:

```bash
uv run ruff check . --fix
uv run ruff format .
uv run ty check .
uv run pre-commit run --all-files
```

The pre-commit hook runs:

- `ruff check --fix`
- `ruff format`
- `ty check --fix`

## Pi extension

A project-local pi extension is included at `.pi/extensions/python-quality-on-agent-end.ts`.

It is auto-discovered by pi and will:

- run `uv run ruff check . --fix`
- run `uv run ruff format .`
- run `uv run ty check . --fix`
- do this automatically on every `agent_end`
- expose `/quality-check` for manual runs

If pi is already running, use `/reload` to pick up the extension.

## API cost

The X API uses pay-per-use pricing. **Measured on this account: only the
bookmarked posts are billed, as "owned reads" at $0.001 each — author profiles
and media returned via expansions are free.** (A probe of a 99-post page that
also returned 74 authors and 35 media cost exactly $0.10 = 99 × $0.001.) So the
cost depends on **how many posts you read across UTC days**, not on the author
expansion. Controls:

- `INCREMENTAL_MAX_RESULTS` (default `10`) vs `FULL_MAX_RESULTS` (default `99`) —
  the real lever. Routine incremental polling pays per post returned, so a small
  page makes the recurring "anything new?" check cheap (~$0.01/day instead of
  ~$0.10/day); full syncs keep the large page since they read every bookmark
  regardless. Avoid unnecessary full syncs (they re-read all bookmarks).
- `X_INCLUDE_AUTHOR_EXPANSION` (default `true`) — does **not** meaningfully change
  cost (authors are free); it only trims payload size. Author name/handle/avatar
  power search, so leave it on unless you have a reason not to.

Every sync records its billable footprint and an estimated cost in the
`api_usage` table, surfaced under `cost` in `GET /api/status`. The estimate is an
upper bound: it does not model X's 24h UTC deduplication window (re-reading the
same resource within a UTC day is charged once). The **Developer Console balance
is the source of truth**; cost rates change, so verify `COST_*_USD` in the Console.

> The optional `GET /2/usage/tweets` cross-check is a project-level endpoint and
> usually returns **403** with this app's user (PKCE) token, since it needs
> app-only access. That is expected — the probe and sync skip it and still
> estimate cost from the response footprint.

### Verify spend after recharging credits

```bash
uv run python -m scripts.probe_cost            # one read with current settings
uv run python -m scripts.probe_cost --no-author # compare footprint without authors
```

The probe makes **one real bookmarks request** (a few credits — that is the
point) and prints the footprint + an estimated `TOTAL`. Steps:

1. Note your credit balance in the Developer Console.
2. Run the probe, then refresh the Console and compare the balance **drop** to
   the printed `TOTAL`. The drop tracks the bookmarked posts only (~`posts ×
   $0.001`); author/media counts do not add to it.
3. Run it again the same UTC day → the drop should be ~$0 (dedup).

## Notes

- Tokens are stored locally in SQLite.
- The app binds to `127.0.0.1` by default.
- Bookmark data is private; keep the database file secure.
- Logs are written to `./logs/app.log` and `./logs/sync.log` by default.
- Full syncs use `FULL_MAX_RESULTS=99` as a workaround for an X API pagination quirk where requesting `100` returned `99` results without a `next_token`. Incremental syncs use the smaller `INCREMENTAL_MAX_RESULTS` to keep routine polling cheap (see "API cost").
- Scheduled background sync no longer runs immediately at process startup; it runs after the configured interval. This avoids accidental paid API calls during repeated local restarts (for example with `uvicorn --reload`).
- Incremental sync stops early once a page contains no unseen bookmark IDs, which significantly reduces paid requests on steady-state runs.
- Bookmark extraction now focuses on bookmarked posts and omits referenced tweet expansions to avoid pulling non-bookmarked resources.

## Project layout

- `app/auth` - OAuth, PKCE, token handling
- `app/xapi` - X API client
- `app/sync` - bookmark sync orchestration
- `app/search` - SQLite FTS search
- `app/api` - backend routes
- `app/ui` - HTML/CSS/JS UI
- `app/db` - schema and DB helpers
