from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.db.sqlite import Database


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TokenStore:
    def __init__(self, db: Database):
        self.db = db

    def save_oauth_state(self, state: str, code_verifier: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO oauth_states(state, code_verifier, created_at) VALUES (?, ?, ?)",
                (state, code_verifier, utcnow_iso()),
            )

    def pop_oauth_state(self, state: str) -> str | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT code_verifier FROM oauth_states WHERE state = ?", (state,)
            ).fetchone()
            connection.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
        return row["code_verifier"] if row else None

    def save_token(self, token_payload: dict[str, Any], user: dict[str, Any]) -> None:
        expires_in = token_payload.get("expires_in")
        expires_at = None
        if expires_in is not None:
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(expires_in))).isoformat()
        with self.db.connect() as connection:
            connection.execute(
                """
                INSERT INTO tokens(
                    provider, access_token, refresh_token, token_type, scope, expires_at,
                    user_id, username, name, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider) DO UPDATE SET
                    access_token=excluded.access_token,
                    refresh_token=COALESCE(excluded.refresh_token, tokens.refresh_token),
                    token_type=excluded.token_type,
                    scope=excluded.scope,
                    expires_at=excluded.expires_at,
                    user_id=excluded.user_id,
                    username=excluded.username,
                    name=excluded.name,
                    updated_at=excluded.updated_at
                """,
                (
                    "x",
                    token_payload["access_token"],
                    token_payload.get("refresh_token"),
                    token_payload.get("token_type", "bearer"),
                    token_payload.get("scope", ""),
                    expires_at,
                    user.get("id"),
                    user.get("username"),
                    user.get("name"),
                    utcnow_iso(),
                ),
            )

    def get_token(self) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute("SELECT * FROM tokens WHERE provider = 'x'").fetchone()
        return dict(row) if row else None

    def clear(self) -> None:
        with self.db.connect() as connection:
            connection.execute("DELETE FROM tokens WHERE provider = 'x'")
            connection.execute("DELETE FROM oauth_states")

    def is_expired(self, token: dict[str, Any], leeway_seconds: int = 60) -> bool:
        expires_at = token.get("expires_at")
        if not expires_at:
            return False
        expires_dt = datetime.fromisoformat(expires_at)
        return expires_dt <= datetime.now(timezone.utc) + timedelta(seconds=leeway_seconds)
