from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Footprint:
    """Billable resources returned by a single X API response."""

    posts: int
    users: int
    media: int
    referenced_posts: int


@dataclass(frozen=True, slots=True)
class CostEstimate:
    posts_usd: float
    users_usd: float
    referenced_usd: float

    @property
    def total_usd(self) -> float:
        return self.posts_usd + self.users_usd + self.referenced_usd


def summarize_footprint(payload: dict[str, Any]) -> Footprint:
    """Count the resources in a bookmarks payload that may be billed.

    `referenced_posts` (includes.tweets) should be 0 for the current request
    shape; a non-zero value flags an accidental referenced-tweet expansion.
    """
    includes = payload.get("includes") or {}
    return Footprint(
        posts=len(payload.get("data") or []),
        users=len(includes.get("users") or []),
        media=len(includes.get("media") or []),
        referenced_posts=len(includes.get("tweets") or []),
    )


def estimate_cost(footprint: Footprint, settings: Settings) -> CostEstimate:
    """Estimate USD cost of a footprint.

    MEASURED on this account: the bookmarks (owned-read) endpoint bills only the
    primary bookmarked posts at $0.001 each. Expansion authors and media are
    returned for FREE — a 99-post page with 74 authors + 35 media cost exactly
    $0.10 (= 99 x $0.001), not $0.84. So `users_usd` is 0 here; the user-read rate
    only applies to a standalone users lookup, which this app does not make.

    Referenced posts (includes.tweets) would be separate non-owned post reads, but
    we never request that expansion. This is an UPPER BOUND: it does not model the
    24h UTC dedup window, so repeated same-day reads are counted again here even
    though X charges them once.
    """
    return CostEstimate(
        posts_usd=footprint.posts * settings.cost_owned_read_usd,
        users_usd=0.0,
        referenced_usd=footprint.referenced_posts * settings.cost_post_read_usd,
    )


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

    async def get_usage(self, access_token: str) -> dict[str, Any]:
        """Daily Post-consumption counts, for reconciling estimated vs real spend."""
        return await self._get("/usage/tweets", access_token)

    async def get_bookmarks_page(
        self,
        access_token: str,
        user_id: str,
        pagination_token: str | None = None,
        max_results: int = 99,
        include_author_expansion: bool = True,
    ) -> dict[str, Any]:
        # Author profiles (expansions=author_id + user.fields) are billed as
        # "user reads" at ~10x the owned-read price. Make them optional so routine
        # polling can stay cheap. Referenced-tweet expansions are always omitted:
        # those are not bookmarks and would add billable post reads.
        expansions = ["attachments.media_keys"]
        if include_author_expansion:
            expansions.insert(0, "author_id")
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
            "expansions": ",".join(expansions),
            "media.fields": "media_key,type,url,preview_image_url",
        }
        if include_author_expansion:
            params["user.fields"] = "id,name,username"
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
