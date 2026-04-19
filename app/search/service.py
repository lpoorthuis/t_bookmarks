from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.db.sqlite import Database


def _build_x_url(username: str | None, post_id: str) -> str:
    handle = username or "i"
    return f"https://x.com/{handle}/status/{post_id}"


@dataclass(frozen=True)
class PropertyDefinition:
    key: str
    label: str
    expression: str
    value_type: str
    operators: tuple[str, ...]
    sortable: bool = True
    filterable: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "type": self.value_type,
            "operators": list(self.operators),
            "sortable": self.sortable,
            "filterable": self.filterable,
        }


TEXT_OPERATORS = ("eq", "ne", "contains", "not_contains", "starts_with", "ends_with", "in", "not_in", "is_null", "is_not_null")
NUMBER_OPERATORS = ("eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "is_null", "is_not_null")
BOOL_OPERATORS = ("eq", "ne", "is_null", "is_not_null")
DATE_OPERATORS = ("eq", "ne", "gt", "gte", "lt", "lte", "is_null", "is_not_null")


PROPERTY_DEFINITIONS: dict[str, PropertyDefinition] = {
    # Bookmark properties
    "bookmark.post_id": PropertyDefinition("bookmark.post_id", "Bookmark post ID", "b.post_id", "text", TEXT_OPERATORS),
    "bookmark.is_bookmarked": PropertyDefinition("bookmark.is_bookmarked", "Bookmarked", "b.is_bookmarked", "boolean", BOOL_OPERATORS),
    "bookmark.first_seen_at": PropertyDefinition("bookmark.first_seen_at", "First seen at", "b.first_seen_at", "datetime", DATE_OPERATORS),
    "bookmark.last_seen_at": PropertyDefinition("bookmark.last_seen_at", "Last seen at", "b.last_seen_at", "datetime", DATE_OPERATORS),
    "bookmark.inactive_at": PropertyDefinition("bookmark.inactive_at", "Inactive at", "b.inactive_at", "datetime", DATE_OPERATORS),
    "bookmark.last_sync_run_id": PropertyDefinition("bookmark.last_sync_run_id", "Last sync run ID", "b.last_sync_run_id", "number", NUMBER_OPERATORS),
    # Post properties
    "post.id": PropertyDefinition("post.id", "Post ID", "p.id", "text", TEXT_OPERATORS),
    "post.author_id": PropertyDefinition("post.author_id", "Post author ID", "p.author_id", "text", TEXT_OPERATORS),
    "post.text": PropertyDefinition("post.text", "Post text", "p.text", "text", TEXT_OPERATORS),
    "post.full_text": PropertyDefinition("post.full_text", "Full text", "p.full_text", "text", TEXT_OPERATORS),
    "post.created_at": PropertyDefinition("post.created_at", "Created at", "p.created_at", "datetime", DATE_OPERATORS),
    "post.lang": PropertyDefinition("post.lang", "Language", "p.lang", "text", TEXT_OPERATORS),
    "post.possibly_sensitive": PropertyDefinition("post.possibly_sensitive", "Possibly sensitive", "p.possibly_sensitive", "boolean", BOOL_OPERATORS),
    "post.conversation_id": PropertyDefinition("post.conversation_id", "Conversation ID", "p.conversation_id", "text", TEXT_OPERATORS),
    "post.public_metrics_json": PropertyDefinition("post.public_metrics_json", "Public metrics JSON", "p.public_metrics_json", "json", TEXT_OPERATORS),
    "post.entities_json": PropertyDefinition("post.entities_json", "Entities JSON", "p.entities_json", "json", TEXT_OPERATORS),
    "post.attachments_json": PropertyDefinition("post.attachments_json", "Attachments JSON", "p.attachments_json", "json", TEXT_OPERATORS),
    "post.referenced_tweets_json": PropertyDefinition("post.referenced_tweets_json", "Referenced tweets JSON", "p.referenced_tweets_json", "json", TEXT_OPERATORS),
    "post.raw_json": PropertyDefinition("post.raw_json", "Post raw JSON", "p.raw_json", "json", TEXT_OPERATORS),
    "post.updated_at": PropertyDefinition("post.updated_at", "Post updated at", "p.updated_at", "datetime", DATE_OPERATORS),
    # Metrics extracted from post JSON
    "post.metrics.like_count": PropertyDefinition("post.metrics.like_count", "Like count", "COALESCE(CAST(json_extract(p.public_metrics_json, '$.like_count') AS INTEGER), 0)", "number", NUMBER_OPERATORS),
    "post.metrics.reply_count": PropertyDefinition("post.metrics.reply_count", "Reply count", "COALESCE(CAST(json_extract(p.public_metrics_json, '$.reply_count') AS INTEGER), 0)", "number", NUMBER_OPERATORS),
    "post.metrics.retweet_count": PropertyDefinition("post.metrics.retweet_count", "Retweet count", "COALESCE(CAST(json_extract(p.public_metrics_json, '$.retweet_count') AS INTEGER), 0)", "number", NUMBER_OPERATORS),
    "post.metrics.quote_count": PropertyDefinition("post.metrics.quote_count", "Quote count", "COALESCE(CAST(json_extract(p.public_metrics_json, '$.quote_count') AS INTEGER), 0)", "number", NUMBER_OPERATORS),
    "post.metrics.bookmark_count": PropertyDefinition("post.metrics.bookmark_count", "Bookmark count", "COALESCE(CAST(json_extract(p.public_metrics_json, '$.bookmark_count') AS INTEGER), 0)", "number", NUMBER_OPERATORS),
    "post.metrics.impression_count": PropertyDefinition("post.metrics.impression_count", "Impression count", "COALESCE(CAST(json_extract(p.public_metrics_json, '$.impression_count') AS INTEGER), 0)", "number", NUMBER_OPERATORS),
    # Author properties
    "author.id": PropertyDefinition("author.id", "Author ID", "u.id", "text", TEXT_OPERATORS),
    "author.username": PropertyDefinition("author.username", "Author username", "u.username", "text", TEXT_OPERATORS),
    "author.name": PropertyDefinition("author.name", "Author name", "u.name", "text", TEXT_OPERATORS),
    "author.description": PropertyDefinition("author.description", "Author description", "u.description", "text", TEXT_OPERATORS),
    "author.verified": PropertyDefinition("author.verified", "Author verified", "u.verified", "boolean", BOOL_OPERATORS),
    "author.profile_image_url": PropertyDefinition("author.profile_image_url", "Author profile image URL", "u.profile_image_url", "text", TEXT_OPERATORS),
    "author.raw_json": PropertyDefinition("author.raw_json", "Author raw JSON", "u.raw_json", "json", TEXT_OPERATORS),
    "author.updated_at": PropertyDefinition("author.updated_at", "Author updated at", "u.updated_at", "datetime", DATE_OPERATORS),
    # Derived properties
    "derived.has_media": PropertyDefinition("derived.has_media", "Has media", "EXISTS (SELECT 1 FROM media m WHERE m.post_id = p.id)", "boolean", BOOL_OPERATORS),
    "derived.media_count": PropertyDefinition("derived.media_count", "Media count", "(SELECT COUNT(*) FROM media m WHERE m.post_id = p.id)", "number", NUMBER_OPERATORS),
    "derived.hashtags": PropertyDefinition("derived.hashtags", "Hashtags", "COALESCE(post_search.hashtags, '')", "text", TEXT_OPERATORS),
    "derived.mentions": PropertyDefinition("derived.mentions", "Mentions", "COALESCE(post_search.mentions, '')", "text", TEXT_OPERATORS),
    "derived.urls": PropertyDefinition("derived.urls", "URLs", "COALESCE(post_search.urls, '')", "text", TEXT_OPERATORS),
}


class SearchService:
    def __init__(self, db: Database):
        self.db = db

    def list_properties(self) -> list[dict[str, Any]]:
        return [definition.as_dict() for definition in PROPERTY_DEFINITIONS.values()]

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
        sort_by: str | None = None,
        sort_order: str = "desc",
    ) -> dict[str, Any]:
        filters = filters or {}
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        offset = (page - 1) * page_size

        where_clauses: list[str] = []
        params: list[Any] = []
        select_score = "0.0 AS score"
        order_by = "b.last_seen_at DESC, p.created_at DESC"
        join_post_search = "LEFT JOIN post_search ON post_search.post_id = p.id"

        if query.strip():
            join_post_search = "JOIN post_search ON post_search.post_id = p.id"
            where_clauses.append("post_search MATCH ?")
            params.append(self._to_fts_query(query))
            select_score = "bm25(post_search) AS score"
            order_by = "score ASC, b.last_seen_at DESC, p.created_at DESC"

        generic_rules = list(filters.get("rules", []))
        if filters.get("active_only", False):
            generic_rules.append(
                {
                    "field": "bookmark.is_bookmarked",
                    "operator": "eq",
                    "value": True,
                }
            )
        if filters.get("author"):
            generic_rules.append(
                {
                    "field": "author.username",
                    "operator": "eq",
                    "value": filters["author"],
                }
            )
        if filters.get("lang"):
            generic_rules.append(
                {
                    "field": "post.lang",
                    "operator": "eq",
                    "value": filters["lang"],
                }
            )
        if filters.get("has_media"):
            generic_rules.append(
                {
                    "field": "derived.has_media",
                    "operator": "eq",
                    "value": True,
                }
            )

        for rule in generic_rules:
            clause, clause_params = self._compile_rule(rule)
            if clause:
                where_clauses.append(clause)
                params.extend(clause_params)

        if sort_by:
            order_by = self._compile_sort(sort_by, sort_order, query_present=bool(query.strip()))

        sql = f"""
            SELECT {select_score},
                   p.id, p.text, p.full_text, p.created_at, p.lang, p.possibly_sensitive,
                   p.entities_json, p.referenced_tweets_json, p.raw_json,
                   u.id AS author_id, u.username, u.name, u.profile_image_url,
                   b.is_bookmarked, b.first_seen_at, b.last_seen_at, b.inactive_at,
                   EXISTS (SELECT 1 FROM media m WHERE m.post_id = p.id) AS has_media,
                   (SELECT COUNT(*) FROM media m WHERE m.post_id = p.id) AS media_count,
                   COALESCE(CAST(json_extract(p.public_metrics_json, '$.like_count') AS INTEGER), 0) AS like_count,
                   COALESCE(CAST(json_extract(p.public_metrics_json, '$.reply_count') AS INTEGER), 0) AS reply_count,
                   COALESCE(CAST(json_extract(p.public_metrics_json, '$.retweet_count') AS INTEGER), 0) AS retweet_count,
                   COALESCE(CAST(json_extract(p.public_metrics_json, '$.quote_count') AS INTEGER), 0) AS quote_count,
                   COALESCE(CAST(json_extract(p.public_metrics_json, '$.bookmark_count') AS INTEGER), 0) AS bookmark_count,
                   COALESCE(CAST(json_extract(p.public_metrics_json, '$.impression_count') AS INTEGER), 0) AS impression_count
            FROM posts p
            JOIN bookmarks b ON b.post_id = p.id
            LEFT JOIN users u ON u.id = p.author_id
            {join_post_search}
            {"WHERE " + " AND ".join(where_clauses) if where_clauses else ""}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """

        count_sql = f"""
            SELECT COUNT(*) AS count
            FROM posts p
            JOIN bookmarks b ON b.post_id = p.id
            LEFT JOIN users u ON u.id = p.author_id
            {join_post_search}
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
                    "possibly_sensitive": bool(row["possibly_sensitive"]),
                    "has_media": bool(row["has_media"]),
                    "media_count": row["media_count"],
                    "bookmarked": bool(row["is_bookmarked"]),
                    "first_seen_at": row["first_seen_at"],
                    "last_seen_at": row["last_seen_at"],
                    "inactive_at": row["inactive_at"],
                    "metrics": {
                        "like_count": row["like_count"],
                        "reply_count": row["reply_count"],
                        "retweet_count": row["retweet_count"],
                        "quote_count": row["quote_count"],
                        "bookmark_count": row["bookmark_count"],
                        "impression_count": row["impression_count"],
                    },
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
            "sort_by": sort_by,
            "sort_order": sort_order,
            "filters": generic_rules,
            "results": results,
        }

    def get_post(self, post_id: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            post = connection.execute(
                """
                SELECT p.*, u.username, u.name, u.profile_image_url,
                       b.is_bookmarked, b.first_seen_at, b.last_seen_at, b.inactive_at, b.last_sync_run_id
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
        public_metrics = json.loads(post["public_metrics_json"] or "{}") if post["public_metrics_json"] else {}
        return {
            "id": post["id"],
            "text": post["full_text"] or post["text"] or "",
            "created_at": post["created_at"],
            "lang": post["lang"],
            "possibly_sensitive": bool(post["possibly_sensitive"]),
            "conversation_id": post["conversation_id"],
            "public_metrics": public_metrics,
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
            "last_sync_run_id": post["last_sync_run_id"],
            "x_url": _build_x_url(post["username"], post["id"]),
            "raw_json": json.loads(post["raw_json"] or "{}"),
        }

    def _compile_rule(self, rule: dict[str, Any]) -> tuple[str | None, list[Any]]:
        field = rule.get("field")
        operator = rule.get("operator")
        value = rule.get("value")
        if not field or not operator:
            return None, []
        definition = PROPERTY_DEFINITIONS.get(field)
        if not definition or operator not in definition.operators:
            return None, []

        expression = definition.expression

        if operator == "is_null":
            return f"{expression} IS NULL", []
        if operator == "is_not_null":
            return f"{expression} IS NOT NULL", []

        if definition.value_type == "boolean":
            normalized = 1 if self._to_bool(value) else 0
            comparator = "=" if operator == "eq" else "!="
            return f"{expression} {comparator} ?", [normalized]

        if operator in {"in", "not_in"}:
            values = self._normalize_multi_value(value)
            if not values:
                return None, []
            placeholders = ", ".join("?" for _ in values)
            comparator = "IN" if operator == "in" else "NOT IN"
            return f"{expression} {comparator} ({placeholders})", values

        if operator in {"contains", "not_contains", "starts_with", "ends_with"}:
            text_value = "" if value is None else str(value)
            if operator == "contains":
                return f"{expression} LIKE ?", [f"%{text_value}%"]
            if operator == "not_contains":
                return f"{expression} NOT LIKE ?", [f"%{text_value}%"]
            if operator == "starts_with":
                return f"{expression} LIKE ?", [f"{text_value}%"]
            return f"{expression} LIKE ?", [f"%{text_value}"]

        comparator = {
            "eq": "=",
            "ne": "!=",
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
        }.get(operator)
        if comparator is None:
            return None, []

        normalized_value = self._normalize_scalar_value(definition.value_type, value)
        return f"{expression} {comparator} ?", [normalized_value]

    def _compile_sort(self, sort_by: str, sort_order: str, query_present: bool) -> str:
        definition = PROPERTY_DEFINITIONS.get(sort_by)
        if not definition or not definition.sortable:
            return "score ASC, b.last_seen_at DESC, p.created_at DESC" if query_present else "b.last_seen_at DESC, p.created_at DESC"
        direction = "ASC" if str(sort_order).lower() == "asc" else "DESC"
        tie_breaker = "p.id ASC"
        if query_present:
            return f"{definition.expression} {direction}, score ASC, {tie_breaker}"
        return f"{definition.expression} {direction}, {tie_breaker}"

    @staticmethod
    def _normalize_scalar_value(value_type: str, value: Any) -> Any:
        if value_type == "number":
            if value is None or value == "":
                return 0
            if isinstance(value, (int, float)):
                return value
            text = str(value)
            return float(text) if "." in text else int(text)
        if value_type == "boolean":
            return 1 if SearchService._to_bool(value) else 0
        return "" if value is None else str(value)

    @staticmethod
    def _normalize_multi_value(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return parsed
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return [value]

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _to_fts_query(query: str) -> str:
        tokens = [token.strip() for token in re.findall(r'"[^"]+"|\S+', query) if token.strip()]
        normalized = []
        for token in tokens:
            if token.startswith('"') and token.endswith('"'):
                normalized.append(token)
            else:
                normalized.append(f"{token}*")
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
