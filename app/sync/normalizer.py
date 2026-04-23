from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value or {}, separators=(",", ":"), ensure_ascii=False)


def extract_full_text(post: dict[str, Any]) -> str:
    note_tweet = post.get("note_tweet") or {}
    return note_tweet.get("text") or post.get("text") or ""


def extract_entities(post: dict[str, Any]) -> dict[str, list[str]]:
    entities = post.get("entities") or {}
    return {
        "hashtags": [
            item.get("tag", "")
            for item in entities.get("hashtags", [])
            if item.get("tag")
        ],
        "mentions": [
            item.get("username", "")
            for item in entities.get("mentions", [])
            if item.get("username")
        ],
        "urls": [
            item.get("expanded_url") or item.get("url")
            for item in entities.get("urls", [])
            if item.get("expanded_url") or item.get("url")
        ],
    }


def normalize_users(payload: dict[str, Any]) -> list[dict[str, Any]]:
    users = payload.get("includes", {}).get("users", [])
    now = utcnow_iso()
    normalized = []
    for user in users:
        normalized.append(
            {
                "id": user["id"],
                "username": user.get("username"),
                "name": user.get("name"),
                "description": user.get("description"),
                "verified": int(bool(user.get("verified"))),
                "profile_image_url": user.get("profile_image_url"),
                "raw_json": _json(user),
                "updated_at": now,
            }
        )
    return normalized


def normalize_posts(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    primary = payload.get("data", [])
    posts = []
    bookmarked_ids = []
    now = utcnow_iso()

    for post in primary:
        post_id = post["id"]
        bookmarked_ids.append(post_id)
        posts.append(
            {
                "id": post_id,
                "author_id": post.get("author_id"),
                "text": post.get("text", ""),
                "full_text": extract_full_text(post),
                "created_at": post.get("created_at"),
                "lang": post.get("lang"),
                "possibly_sensitive": int(bool(post.get("possibly_sensitive"))),
                "public_metrics_json": _json(post.get("public_metrics")),
                "entities_json": _json(post.get("entities")),
                "attachments_json": _json(post.get("attachments")),
                "referenced_tweets_json": _json(post.get("referenced_tweets")),
                "conversation_id": post.get("conversation_id"),
                "raw_json": _json(post),
                "updated_at": now,
            }
        )
    return posts, bookmarked_ids


def normalize_media(payload: dict[str, Any]) -> list[dict[str, Any]]:
    posts = payload.get("data", [])
    media_by_key = {
        item["media_key"]: item for item in payload.get("includes", {}).get("media", [])
    }
    rows: list[dict[str, Any]] = []
    for post in posts:
        attachments = post.get("attachments") or {}
        for media_key in attachments.get("media_keys", []):
            media = media_by_key.get(media_key)
            if not media:
                continue
            rows.append(
                {
                    "media_key": media_key,
                    "post_id": post["id"],
                    "type": media.get("type"),
                    "url": media.get("url"),
                    "preview_image_url": media.get("preview_image_url"),
                    "alt_text": media.get("alt_text"),
                    "width": media.get("width"),
                    "height": media.get("height"),
                    "raw_json": _json(media),
                }
            )
    return rows
