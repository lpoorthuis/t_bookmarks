from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings


class XApiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def _get(self, path: str, access_token: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(f"{self.settings.x_api_base_url}{path}", headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    async def get_me(self, access_token: str) -> dict[str, Any]:
        payload = await self._get("/users/me", access_token, params={"user.fields": "id,name,username"})
        return payload["data"]

    async def get_bookmarks_page(
        self,
        access_token: str,
        user_id: str,
        pagination_token: str | None = None,
        max_results: int = 100,
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
                    "referenced_tweets",
                    "possibly_sensitive",
                    "conversation_id",
                ]
            ),
            "expansions": ",".join(
                [
                    "author_id",
                    "attachments.media_keys",
                    "referenced_tweets.id",
                    "referenced_tweets.id.author_id",
                ]
            ),
            "user.fields": "id,name,username,verified,profile_image_url,description",
            "media.fields": "media_key,type,url,preview_image_url,alt_text,width,height",
        }
        if pagination_token:
            params["pagination_token"] = pagination_token
        return await self._get(f"/users/{user_id}/bookmarks", access_token, params=params)
