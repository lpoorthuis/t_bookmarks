from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class XApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def _get(
        self, path: str, access_token: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        logger.debug("GET %s params=%s", path, params)
        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout_seconds
        ) as client:
            response = await client.get(
                f"{self.settings.x_api_base_url}{path}", headers=headers, params=params
            )
            response.raise_for_status()
            payload = response.json()
            meta = payload.get("meta")
            if meta is not None:
                logger.info("X API GET %s meta=%s", path, meta)
            else:
                logger.info("X API GET %s status=%s", path, response.status_code)
            return payload

    async def get_me(self, access_token: str) -> dict[str, Any]:
        payload = await self._get(
            "/users/me", access_token, params={"user.fields": "id,name,username"}
        )
        return payload["data"]

    async def get_bookmarks_page(
        self,
        access_token: str,
        user_id: str,
        pagination_token: str | None = None,
        max_results: int = 99,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "max_results": max_results,
            "tweet.fields": ",".join(
                [
                    "created_at",
                    "author_id",
                    "text",
                    "lang",
                    "entities",
                    "public_metrics",
                    "note_tweet",
                    "attachments",
                    "possibly_sensitive",
                    "conversation_id",
                ]
            ),
            # Keep responses focused on the bookmarked posts themselves.
            # Avoid fetching referenced tweet expansions because those are not
            # bookmarks and can increase billable resource volume.
            "expansions": "author_id,attachments.media_keys",
            "user.fields": "id,name,username",
            "media.fields": "media_key,type,url,preview_image_url",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        if max_results >= 100:
            logger.warning(
                "Requested max_results=%s for bookmarks. X API currently appears to return only 99 rows and omit next_token at 100; using 99 is safer.",
                max_results,
            )
        return await self._get(
            f"/users/{user_id}/bookmarks", access_token, params=params
        )
