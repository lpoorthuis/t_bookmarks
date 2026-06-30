from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_env_file()


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(slots=True)
class Settings:
    app_host: str = os.environ.get("APP_HOST", "127.0.0.1")
    app_port: int = int(os.environ.get("APP_PORT", "8000"))
    app_secret_key: str = os.environ.get("APP_SECRET_KEY", secrets.token_urlsafe(32))
    database_path: Path = Path(
        os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "t_bookmarks.sqlite3"))
    )
    x_client_id: str = os.environ.get("X_CLIENT_ID", "")
    x_client_secret: str = os.environ.get("X_CLIENT_SECRET", "")
    x_redirect_uri: str = os.environ.get(
        "X_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback"
    )
    x_scopes: tuple[str, ...] = tuple(
        os.environ.get(
            "X_SCOPES", "bookmark.read tweet.read users.read offline.access"
        ).split()
    )
    sync_interval_minutes: int = int(os.environ.get("SYNC_INTERVAL_MINUTES", "360"))
    request_timeout_seconds: int = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))
    log_dir: Path = Path(os.environ.get("LOG_DIR", str(BASE_DIR / "logs")))
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    x_authorize_url: str = "https://x.com/i/oauth2/authorize"
    x_token_url: str = "https://api.x.com/2/oauth2/token"
    x_api_base_url: str = "https://api.x.com/2"
    x_usage_url: str = "https://api.x.com/2/usage/tweets"

    # Cost controls. MEASURED: only the bookmarked posts are billed ($0.001 each);
    # expansion authors and media are free. So the lever is reads-per-UTC-day:
    # poll incrementally with a small page so the routine "anything new?" check is
    # cheap. The author toggle does not affect cost (authors are free); it only
    # trims payload size, so it defaults on to keep author data for search.
    include_author_expansion: bool = _env_bool("X_INCLUDE_AUTHOR_EXPANSION", True)
    incremental_max_results: int = int(os.environ.get("INCREMENTAL_MAX_RESULTS", "10"))
    full_max_results: int = int(os.environ.get("FULL_MAX_RESULTS", "99"))

    # Pay-per-use rates in USD per resource. VERIFY current values in the X
    # Developer Console; X changed these multiple times in 2026 and the public
    # docs are not authoritative. Used only for local cost estimation, not billing.
    # cost_user_read_usd is unused for bookmarks (expansion authors are not billed).
    cost_owned_read_usd: float = float(os.environ.get("COST_OWNED_READ_USD", "0.001"))
    cost_user_read_usd: float = float(os.environ.get("COST_USER_READ_USD", "0.010"))
    cost_post_read_usd: float = float(os.environ.get("COST_POST_READ_USD", "0.005"))

    @property
    def scope_string(self) -> str:
        return " ".join(self.x_scopes)


settings = Settings()
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
