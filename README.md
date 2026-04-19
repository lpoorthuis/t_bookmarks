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

4. Run the app:

   ```bash
   uv run uvicorn app.main:app --reload
   ```

5. Open:

   ```
   http://127.0.0.1:8000
   ```

## Notes

- Tokens are stored locally in SQLite.
- The app binds to `127.0.0.1` by default.
- Bookmark data is private; keep the database file secure.
- Logs are written to `./logs/app.log` and `./logs/sync.log` by default.
- The bookmarks sync uses `max_results=99` as a workaround for an X API pagination quirk where requesting `100` returned `99` results without a `next_token`.

## Project layout

- `app/auth` - OAuth, PKCE, token handling
- `app/xapi` - X API client
- `app/sync` - bookmark sync orchestration
- `app/search` - SQLite FTS search
- `app/api` - backend routes
- `app/ui` - HTML/CSS/JS UI
- `app/db` - schema and DB helpers
