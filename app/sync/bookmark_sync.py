from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.auth.service import AuthError, AuthService
from app.db.sqlite import Database
from app.search.service import SearchService
from app.sync.normalizer import (
    normalize_media,
    normalize_posts,
    normalize_users,
    utcnow_iso,
)
from app.xapi.client import XApiClient

logger = logging.getLogger("app.sync")


class BookmarkSyncService:
    def __init__(
        self,
        db: Database,
        auth_service: AuthService,
        x_client: XApiClient,
        search_service: SearchService,
    ):
        self.db = db
        self.auth_service = auth_service
        self.x_client = x_client
        self.search_service = search_service
        self._task: asyncio.Task[None] | None = None
        self._status: dict[str, Any] = {
            "running": False,
            "run_id": None,
            "started_at": None,
            "finished_at": None,
            "mode": None,
            "pages_fetched": 0,
            "posts_seen": 0,
            "posts_inserted": 0,
            "posts_updated": 0,
            "posts_deactivated": 0,
            "message": None,
            "error": None,
        }

    def get_sync_status(self) -> dict[str, Any]:
        return dict(self._status)

    def is_running(self) -> bool:
        return bool(self._task and not self._task.done())

    def start_sync(self, full: bool = True) -> dict[str, Any]:
        if self.is_running():
            logger.info("Sync start requested while sync already running")
            return self.get_sync_status()
        logger.info("Scheduling %s sync", "full" if full else "incremental")
        self._task = asyncio.create_task(self._run_sync(full=full))
        return self.get_sync_status()

    async def _run_sync(self, full: bool = True) -> None:
        mode = "full" if full else "incremental"
        started_at = utcnow_iso()
        run_id = self._create_run(mode=mode, started_at=started_at)
        self._status.update(
            {
                "running": True,
                "run_id": run_id,
                "started_at": started_at,
                "finished_at": None,
                "mode": mode,
                "pages_fetched": 0,
                "posts_seen": 0,
                "posts_inserted": 0,
                "posts_updated": 0,
                "posts_deactivated": 0,
                "message": "Starting sync",
                "error": None,
            }
        )
        try:
            logger.info("Starting sync run_id=%s mode=%s", run_id, mode)
            access_token = await self.auth_service.get_valid_access_token()
            user_id = self.auth_service.get_current_user_id()
            seen_bookmarked_ids: set[str] = set()
            pagination_token: str | None = None
            page_counter = 0
            pages_limit = None if full else 3

            while True:
                page_counter += 1
                self._status["message"] = f"Fetching page {page_counter}"
                payload = await self._fetch_page_with_retries(
                    access_token, user_id, pagination_token
                )
                users = normalize_users(payload)
                posts, bookmarked_ids = normalize_posts(payload)
                media = normalize_media(payload)
                page_stats = self._persist_page(
                    run_id, users, posts, media, bookmarked_ids
                )
                seen_bookmarked_ids.update(bookmarked_ids)

                meta = payload.get("meta") or {}
                self._status["pages_fetched"] += 1
                self._status["posts_seen"] += page_stats["posts_seen"]
                self._status["posts_inserted"] += page_stats["posts_inserted"]
                self._status["posts_updated"] += page_stats["posts_updated"]

                pagination_token = meta.get("next_token")
                logger.info(
                    "Processed bookmarks page run_id=%s page=%s result_count=%s next_token_present=%s inserted=%s updated=%s seen_total=%s",
                    run_id,
                    page_counter,
                    meta.get("result_count"),
                    bool(pagination_token),
                    page_stats["posts_inserted"],
                    page_stats["posts_updated"],
                    self._status["posts_seen"],
                )
                if meta.get("result_count") == 99 and not pagination_token:
                    logger.warning(
                        "Bookmarks endpoint returned 99 results without next_token. This is a known X API quirk when requesting 100 items; the client now defaults to 99 to preserve pagination."
                    )
                if not pagination_token:
                    break
                if pages_limit is not None and page_counter >= pages_limit:
                    break

            deactivated = 0
            if full:
                deactivated = self._deactivate_missing_bookmarks(
                    run_id, seen_bookmarked_ids
                )
                self._status["posts_deactivated"] = deactivated
                self._set_app_state("last_full_sync_at", utcnow_iso())
            self._set_app_state("last_sync_at", utcnow_iso())
            self._finish_run(run_id, "success", None, deactivated)
            finished_at = utcnow_iso()
            self._status.update(
                {
                    "running": False,
                    "finished_at": finished_at,
                    "message": "Sync completed",
                }
            )
            logger.info(
                "Completed sync run_id=%s mode=%s pages=%s bookmarks_seen=%s inserted=%s updated=%s deactivated=%s",
                run_id,
                mode,
                self._status["pages_fetched"],
                self._status["posts_seen"],
                self._status["posts_inserted"],
                self._status["posts_updated"],
                deactivated,
            )
        except (AuthError, httpx.HTTPError, RuntimeError) as exc:
            logger.exception("Sync run_id=%s failed", run_id)
            self._finish_run(
                run_id, "failed", str(exc), self._status["posts_deactivated"]
            )
            self._status.update(
                {
                    "running": False,
                    "finished_at": utcnow_iso(),
                    "message": "Sync failed",
                    "error": str(exc),
                }
            )

    async def _fetch_page_with_retries(
        self, access_token: str, user_id: str, pagination_token: str | None
    ) -> dict[str, Any]:
        delay = 1.0
        for attempt in range(5):
            try:
                return await self.x_client.get_bookmarks_page(
                    access_token, user_id, pagination_token
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in {429, 500, 502, 503, 504} and attempt < 4:
                    retry_after = exc.response.headers.get("Retry-After")
                    sleep_for = (
                        float(retry_after)
                        if retry_after and retry_after.isdigit()
                        else delay
                    )
                    logger.warning(
                        "Bookmarks page fetch failed with status=%s; retrying in %s seconds (attempt %s/5)",
                        status,
                        sleep_for,
                        attempt + 1,
                    )
                    await asyncio.sleep(sleep_for)
                    delay *= 2
                    continue
                logger.error(
                    "Bookmarks page fetch failed with status=%s and will not be retried",
                    status,
                )
                raise
        raise RuntimeError("Bookmark page fetch exhausted retries without returning")

    def _create_run(self, mode: str, started_at: str) -> int:
        with self.db.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO sync_runs(started_at, status, mode) VALUES (?, 'running', ?)",
                (started_at, mode),
            )
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Failed to create sync run record")
            return int(lastrowid)

    def _finish_run(
        self, run_id: int, status: str, error_message: str | None, deactivated: int
    ) -> None:
        with self.db.connect() as connection:
            connection.execute(
                """
                UPDATE sync_runs
                SET finished_at = ?, status = ?, pages_fetched = ?, posts_seen = ?, posts_inserted = ?,
                    posts_updated = ?, posts_deactivated = ?, error_message = ?
                WHERE id = ?
                """,
                (
                    utcnow_iso(),
                    status,
                    self._status["pages_fetched"],
                    self._status["posts_seen"],
                    self._status["posts_inserted"],
                    self._status["posts_updated"],
                    deactivated,
                    error_message,
                    run_id,
                ),
            )

    def _persist_page(
        self,
        run_id: int,
        users: list[dict[str, Any]],
        posts: list[dict[str, Any]],
        media: list[dict[str, Any]],
        bookmarked_ids: list[str],
    ) -> dict[str, int]:
        posts_inserted = 0
        posts_updated = 0
        with self.db.connect() as connection:
            for user in users:
                connection.execute(
                    """
                    INSERT INTO users(id, username, name, description, verified, profile_image_url, raw_json, updated_at)
                    VALUES (:id, :username, :name, :description, :verified, :profile_image_url, :raw_json, :updated_at)
                    ON CONFLICT(id) DO UPDATE SET
                        username=excluded.username,
                        name=excluded.name,
                        description=excluded.description,
                        verified=excluded.verified,
                        profile_image_url=excluded.profile_image_url,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    user,
                )

            for post in posts:
                exists = connection.execute(
                    "SELECT 1 FROM posts WHERE id = ?", (post["id"],)
                ).fetchone()
                if exists:
                    posts_updated += 1
                else:
                    posts_inserted += 1
                connection.execute(
                    """
                    INSERT INTO posts(
                        id, author_id, text, full_text, created_at, lang, possibly_sensitive, public_metrics_json,
                        entities_json, attachments_json, referenced_tweets_json, conversation_id, raw_json, updated_at
                    ) VALUES (
                        :id, :author_id, :text, :full_text, :created_at, :lang, :possibly_sensitive, :public_metrics_json,
                        :entities_json, :attachments_json, :referenced_tweets_json, :conversation_id, :raw_json, :updated_at
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        author_id=excluded.author_id,
                        text=excluded.text,
                        full_text=excluded.full_text,
                        created_at=excluded.created_at,
                        lang=excluded.lang,
                        possibly_sensitive=excluded.possibly_sensitive,
                        public_metrics_json=excluded.public_metrics_json,
                        entities_json=excluded.entities_json,
                        attachments_json=excluded.attachments_json,
                        referenced_tweets_json=excluded.referenced_tweets_json,
                        conversation_id=excluded.conversation_id,
                        raw_json=excluded.raw_json,
                        updated_at=excluded.updated_at
                    """,
                    post,
                )

            for item in media:
                connection.execute(
                    """
                    INSERT INTO media(media_key, post_id, type, url, preview_image_url, alt_text, width, height, raw_json)
                    VALUES (:media_key, :post_id, :type, :url, :preview_image_url, :alt_text, :width, :height, :raw_json)
                    ON CONFLICT(media_key) DO UPDATE SET
                        post_id=excluded.post_id,
                        type=excluded.type,
                        url=excluded.url,
                        preview_image_url=excluded.preview_image_url,
                        alt_text=excluded.alt_text,
                        width=excluded.width,
                        height=excluded.height,
                        raw_json=excluded.raw_json
                    """,
                    item,
                )

            now = utcnow_iso()
            for post_id in bookmarked_ids:
                connection.execute(
                    """
                    INSERT INTO bookmarks(post_id, is_bookmarked, first_seen_at, last_seen_at, inactive_at, last_sync_run_id)
                    VALUES (?, 1, ?, ?, NULL, ?)
                    ON CONFLICT(post_id) DO UPDATE SET
                        is_bookmarked=1,
                        last_seen_at=excluded.last_seen_at,
                        inactive_at=NULL,
                        last_sync_run_id=excluded.last_sync_run_id
                    """,
                    (post_id, now, now, run_id),
                )

        for post in posts:
            self.search_service.reindex_post(post["id"])

        return {
            "posts_seen": len(bookmarked_ids),
            "posts_inserted": posts_inserted,
            "posts_updated": posts_updated,
        }

    def _deactivate_missing_bookmarks(self, run_id: int, seen_ids: set[str]) -> int:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT post_id FROM bookmarks WHERE is_bookmarked = 1"
            ).fetchall()
            to_deactivate = [
                row["post_id"] for row in rows if row["post_id"] not in seen_ids
            ]
            now = utcnow_iso()
            for post_id in to_deactivate:
                connection.execute(
                    "UPDATE bookmarks SET is_bookmarked = 0, inactive_at = ?, last_sync_run_id = ? WHERE post_id = ?",
                    (now, run_id, post_id),
                )
            return len(to_deactivate)

    def _set_app_state(self, key: str, value: str) -> None:
        with self.db.connect() as connection:
            connection.execute(
                "INSERT INTO app_state(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def get_sync_history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM sync_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_sync_timestamp(self) -> str | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT value FROM app_state WHERE key = 'last_sync_at'"
            ).fetchone()
        return row["value"] if row else None
