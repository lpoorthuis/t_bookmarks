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

## Notes

- Tokens are stored locally in SQLite.
- The app binds to `127.0.0.1` by default.
- Bookmark data is private; keep the database file secure.
- Logs are written to `./logs/app.log` and `./logs/sync.log` by default.
- The bookmarks sync uses `max_results=99` as a workaround for an X API pagination quirk where requesting `100` returned `99` results without a `next_token`.
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
