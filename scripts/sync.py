"""Run a bookmark sync from the command line.

Defaults to a FULL crawl: re-reads every bookmark and deactivates ones you have
removed on X (the UI only runs incremental syncs, which never deactivate). Cost is
roughly bookmark_count x $0.001, deduped within a UTC day.

    uv run python -m scripts.sync                # full crawl (detect removals)
    uv run python -m scripts.sync --incremental  # cheap, new bookmarks only
"""

from __future__ import annotations

import argparse
import asyncio

from app.auth.oauth_client import OAuthClient
from app.auth.service import AuthService
from app.auth.token_store import TokenStore
from app.config import BASE_DIR, settings
from app.db.sqlite import Database
from app.search.service import SearchService
from app.sync.bookmark_sync import BookmarkSyncService
from app.xapi.client import XApiClient


async def _run(full: bool) -> None:
    db = Database(settings.database_path)
    db.initialize(BASE_DIR / "app" / "db" / "schema.sql")

    x_client = XApiClient(settings)
    token_store = TokenStore(db)
    auth_service = AuthService(OAuthClient(settings), token_store, x_client)
    search_service = SearchService(db)
    sync_service = BookmarkSyncService(
        db, auth_service, x_client, search_service, settings
    )

    mode = "full" if full else "incremental"
    print(f"Starting {mode} sync...")
    sync_service.start_sync(full=full)
    while sync_service.is_running():
        await asyncio.sleep(0.5)

    status = sync_service.get_sync_status()
    if status.get("error"):
        print(f"Sync failed: {status['error']}")
        return
    print(
        f"Done ({status['mode']}): pages={status['pages_fetched']} "
        f"posts_read={status['posts_read']} new={status['new_bookmarks_seen']} "
        f"inserted={status['posts_inserted']} updated={status['posts_updated']} "
        f"deactivated={status['posts_deactivated']} "
        f"est_cost=${status['est_cost_usd']:.4f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync X bookmarks into the local DB.")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Run a cheap incremental sync (new bookmarks only) instead of a full crawl.",
    )
    args = parser.parse_args()
    asyncio.run(_run(full=not args.incremental))


if __name__ == "__main__":
    main()
