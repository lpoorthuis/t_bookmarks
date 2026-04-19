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


@dataclass(slots=True)
class Settings:
    app_host: str = os.environ.get("APP_HOST", "127.0.0.1")
    app_port: int = int(os.environ.get("APP_PORT", "8000"))
    app_secret_key: str = os.environ.get("APP_SECRET_KEY", secrets.token_urlsafe(32))
    database_path: Path = Path(os.environ.get("DATABASE_PATH", str(BASE_DIR / "data" / "t_bookmarks.sqlite3")))
    x_client_id: str = os.environ.get("X_CLIENT_ID", "")
    x_client_secret: str = os.environ.get("X_CLIENT_SECRET", "")
    x_redirect_uri: str = os.environ.get("X_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
    x_scopes: tuple[str, ...] = tuple(os.environ.get("X_SCOPES", "bookmark.read tweet.read users.read offline.access").split())
    sync_interval_minutes: int = int(os.environ.get("SYNC_INTERVAL_MINUTES", "360"))
    request_timeout_seconds: int = int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30"))
    log_dir: Path = Path(os.environ.get("LOG_DIR", str(BASE_DIR / "logs")))
    log_level: str = os.environ.get("LOG_LEVEL", "INFO")
    x_authorize_url: str = "https://x.com/i/oauth2/authorize"
    x_token_url: str = "https://api.x.com/2/oauth2/token"
    x_api_base_url: str = "https://api.x.com/2"

    @property
    def scope_string(self) -> str:
        return " ".join(self.x_scopes)


settings = Settings()
settings.database_path.parent.mkdir(parents=True, exist_ok=True)
