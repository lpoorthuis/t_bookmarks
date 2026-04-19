from __future__ import annotations

import json
import re
from typing import Any

from app.db.sqlite import Database


def _build_x_url(username: str | None, post_id: str) -> str:
    handle = username or "i"
    return f"https://x.com/{handle}/status/{post_id}"


class SearchService:
    def __init__(self, db: Database):
        self.db = db

    def reindex_post(self, post_id: str) -> None:
        with self.db.connect() as connection:
            row = connection.execute(
                """
                SELECT p.id, p.full_text, p.entities_json, u.username, u.name
                FROM posts p
                LEFT JOIN users u ON u.id = p.author_id
                WHERE p.id = ?
                """,
                (post_id,),
            ).fetchone()
            if not row:
                return
            entities = json.loads(row["entities_json"] or "{}") if row["entities_json"] else {}
            hashtags = " ".join(item.get("tag", "") for item in entities.get("hashtags", []) if item.get("tag"))
            mentions = " ".join(item.get("username", "") for item in entities.get("mentions", []) if item.get("username"))
            urls = " ".join((item.get("expanded_url") or item.get("url") or "") for item in entities.get("urls", []))
            connection.execute("DELETE FROM post_search WHERE post_id = ?", (post_id,))
            connection.execute(
                """
                INSERT INTO post_search(post_id, full_text, author_username, author_name, hashtags, mentions, urls)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["full_text"] or "",
                    row["username"] or "",
                    row["name"] or "",
                    hashtags,
                    mentions,
                    urls,
                ),
            )

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        filters = filters or {}
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        where_clauses = []
        params: list[Any] = []
        join_fts = False
        select_score = "0.0 AS score"
        order_by = "b.last_seen_at DESC, p.created_at DESC"

        if query.strip():
            join_fts = True
            where_clauses.append("post_search MATCH ?")
            params.append(self._to_fts_query(query))
            select_score = "bm25(post_search) AS score"
            order_by = "score, b.last_seen_at DESC, p.created_at DESC"

        active_only = str(filters.get("active_only", "true")).lower() != "false"
        if active_only:
            where_clauses.append("b.is_bookmarked = 1")

        if author := filters.get("author"):
            where_clauses.append("u.username = ?")
            params.append(author)

        if language := filters.get("lang"):
            where_clauses.append("p.lang = ?")
            params.append(language)

        if str(filters.get("has_media", "false")).lower() == "true":
            where_clauses.append("EXISTS (SELECT 1 FROM media m WHERE m.post_id = p.id)")

        sql = f"""
            SELECT {select_score},
                   p.id, p.text, p.full_text, p.created_at, p.lang, p.possibly_sensitive,
                   p.entities_json, p.referenced_tweets_json, p.raw_json,
                   u.id AS author_id, u.username, u.name, u.profile_image_url,
                   b.is_bookmarked, b.last_seen_at,
                   EXISTS (SELECT 1 FROM media m WHERE m.post_id = p.id) AS has_media
            FROM posts p
            JOIN bookmarks b ON b.post_id = p.id
            LEFT JOIN users u ON u.id = p.author_id
            {"JOIN post_search ON post_search.post_id = p.id" if join_fts else ""}
            {"WHERE " + " AND ".join(where_clauses) if where_clauses else ""}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """

        count_sql = f"""
            SELECT COUNT(*) AS count
            FROM posts p
            JOIN bookmarks b ON b.post_id = p.id
            LEFT JOIN users u ON u.id = p.author_id
            {"JOIN post_search ON post_search.post_id = p.id" if join_fts else ""}
            {"WHERE " + " AND ".join(where_clauses) if where_clauses else ""}
        """

        with self.db.connect() as connection:
            count = connection.execute(count_sql, params).fetchone()["count"]
            rows = connection.execute(sql, [*params, page_size, offset]).fetchall()

        results = []
        for row in rows:
            text = row["full_text"] or row["text"] or ""
            results.append(
                {
                    "post_id": row["id"],
                    "text": text,
                    "snippet": self._make_snippet(text, query),
                    "created_at": row["created_at"],
                    "lang": row["lang"],
                    "has_media": bool(row["has_media"]),
                    "bookmarked": bool(row["is_bookmarked"]),
                    "author": {
                        "id": row["author_id"],
                        "username": row["username"],
                        "name": row["name"],
                        "profile_image_url": row["profile_image_url"],
                    },
                    "url": _build_x_url(row["username"], row["id"]),
                }
            )

        return {
            "query": query,
            "page": page,
            "page_size": page_size,
            "total": count,
            "results": results,
        }

    def get_post(self, post_id: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            post = connection.execute(
                """
                SELECT p.*, u.username, u.name, u.profile_image_url,
                       b.is_bookmarked, b.first_seen_at, b.last_seen_at, b.inactive_at
                FROM posts p
                LEFT JOIN users u ON u.id = p.author_id
                LEFT JOIN bookmarks b ON b.post_id = p.id
                WHERE p.id = ?
                """,
                (post_id,),
            ).fetchone()
            if not post:
                return None
            media_rows = connection.execute(
                "SELECT media_key, type, url, preview_image_url, alt_text, width, height FROM media WHERE post_id = ?",
                (post_id,),
            ).fetchall()

        entities = json.loads(post["entities_json"] or "{}") if post["entities_json"] else {}
        return {
            "id": post["id"],
            "text": post["full_text"] or post["text"] or "",
            "created_at": post["created_at"],
            "lang": post["lang"],
            "possibly_sensitive": bool(post["possibly_sensitive"]),
            "author": {
                "id": post["author_id"],
                "username": post["username"],
                "name": post["name"],
                "profile_image_url": post["profile_image_url"],
            },
            "media": [dict(row) for row in media_rows],
            "entities": {
                "hashtags": [item.get("tag") for item in entities.get("hashtags", []) if item.get("tag")],
                "mentions": [item.get("username") for item in entities.get("mentions", []) if item.get("username")],
                "urls": [item.get("expanded_url") or item.get("url") for item in entities.get("urls", []) if item.get("expanded_url") or item.get("url")],
            },
            "bookmarked": bool(post["is_bookmarked"]) if post["is_bookmarked"] is not None else False,
            "first_seen_at": post["first_seen_at"],
            "last_seen_at": post["last_seen_at"],
            "inactive_at": post["inactive_at"],
            "x_url": _build_x_url(post["username"], post["id"]),
            "raw_json": json.loads(post["raw_json"] or "{}"),
        }

    @staticmethod
    def _to_fts_query(query: str) -> str:
        tokens = [token.strip() for token in re.findall(r'"[^"]+"|\S+', query) if token.strip()]
        normalized = []
        for token in tokens:
            if token.startswith('"') and token.endswith('"'):
                normalized.append(token)
            else:
                normalized.append(f'{token}*')
        return " AND ".join(normalized)

    @staticmethod
    def _make_snippet(text: str, query: str, radius: int = 140) -> str:
        if not text:
            return ""
        terms = [term.strip('"').lower() for term in query.split() if term.strip()]
        lower_text = text.lower()
        for term in terms:
            index = lower_text.find(term)
            if index != -1:
                start = max(0, index - radius // 2)
                end = min(len(text), start + radius)
                snippet = text[start:end]
                return ("..." if start > 0 else "") + snippet + ("..." if end < len(text) else "")
        return text[:radius] + ("..." if len(text) > radius else "")
