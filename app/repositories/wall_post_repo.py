"""
Repository for wall posts (wallet/domain walls with HTML content and voting).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import bleach

from app.repositories.base import BaseRepository
from app.core.exceptions import BadRequestError, NotFoundError

logger = logging.getLogger(__name__)


ALLOWED_ENTITY_TYPES = frozenset(("domain", "wallet"))
ALLOWED_THEMES = frozenset(("light", "dark"))


class WallPostRepository(BaseRepository):
    """Repository providing CRUD operations for wall posts."""

    MAX_BODY_LENGTH = 20000
    _ALLOWED_TAGS = {
        "a",
        "abbr",
        "blockquote",
        "br",
        "code",
        "div",
        "em",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "hr",
        "img",
        "li",
        "ol",
        "p",
        "pre",
        "span",
        "strong",
        "u",
        "ul",
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
    }
    _ALLOWED_ATTRIBUTES = {
        "*": ["class", "style"],
        "a": ["href", "title", "target", "rel"],
        "img": ["src", "alt", "title", "width", "height"],
        "div": ["data-*"],
        "span": ["data-*"],
        "table": ["border", "cellpadding", "cellspacing"],
        "td": ["colspan", "rowspan"],
        "th": ["colspan", "rowspan"],
    }
    _ALLOWED_PROTOCOLS = ["http", "https", "mailto", "ipfs"]

    @classmethod
    def sanitize_body(cls, raw_body: str) -> Tuple[str, str]:
        """
        Sanitize raw HTML body.

        Returns:
            Tuple of (normalized_raw_body, sanitized_html).
        """
        if not raw_body or not str(raw_body).strip():
            raise BadRequestError("Wall post cannot be empty")

        normalized = raw_body.strip()
        if len(normalized) > cls.MAX_BODY_LENGTH:
            raise BadRequestError("Wall post is too long (max 20000 characters)")

        cleaned = bleach.clean(
            normalized,
            tags=cls._ALLOWED_TAGS,
            attributes=cls._ALLOWED_ATTRIBUTES,
            protocols=cls._ALLOWED_PROTOCOLS,
            strip=True,
        )
        cleaned = bleach.linkify(cleaned, parse_email=True)

        if not cleaned.strip():
            raise BadRequestError("Wall post contains no allowed content")

        return normalized, cleaned

    @staticmethod
    def _normalize_theme(content_theme: Optional[str]) -> str:
        theme = (content_theme or "light").strip().lower()
        if theme not in ALLOWED_THEMES:
            theme = "light"
        return theme

    @staticmethod
    def _entity_params(
        entity_type: str, entity_id: Optional[int], entity_key: Optional[str]
    ) -> Tuple[str, Optional[int], Optional[str]]:
        if entity_type not in ALLOWED_ENTITY_TYPES:
            raise BadRequestError(f"Invalid entity_type: {entity_type}")
        if entity_type == "domain":
            if entity_id is None:
                raise BadRequestError("domain requires entity_id")
            return entity_type, entity_id, None
        # wallet
        if not entity_key or not str(entity_key).strip():
            raise BadRequestError("wallet requires entity_key")
        return entity_type, None, str(entity_key).strip()

    async def create_post(
        self,
        author_id: int,
        entity_type: str,
        entity_id: Optional[int],
        entity_key: Optional[str],
        raw_body: str,
        content_theme: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a wall post with sanitized HTML body."""
        et, eid, ek = self._entity_params(entity_type, entity_id, entity_key)
        normalized_raw, sanitized = self.sanitize_body(raw_body)
        theme = self._normalize_theme(content_theme)

        query = """
            INSERT INTO wall_posts (author_id, entity_type, entity_id, entity_key, raw_body, body_html, content_theme)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        row = await self.db.fetchrow(
            query,
            author_id,
            et,
            eid,
            ek,
            normalized_raw,
            sanitized,
            theme,
        )
        logger.debug("Created wall post %s for %s", row["id"] if row else None, et)
        return dict(row) if row else {}

    async def list_posts(
        self,
        entity_type: str,
        entity_id: Optional[int],
        entity_key: Optional[str],
        user_id: Optional[int],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        """List wall posts for an entity."""
        et, eid, ek = self._entity_params(entity_type, entity_id, entity_key)
        params: List[Any] = [et]

        if eid is not None:
            where_clause = "wp.entity_type = $1 AND wp.entity_id = $2"
            params.append(eid)
        else:
            where_clause = "wp.entity_type = $1 AND wp.entity_key = $2"
            params.append(ek)

        params.extend([user_id, limit, offset])

        query = f"""
            SELECT
                wp.id,
                wp.author_id,
                u.wallet AS author_wallet,
                wp.entity_type,
                wp.entity_id,
                wp.entity_key,
                wp.raw_body,
                wp.body_html,
                wp.content_theme,
                wp.karma_score,
                wp.created_at,
                wp.updated_at,
                COALESCE(uv.value, NULL) AS user_vote,
                COALESCE((
                    SELECT COUNT(*)
                    FROM comments c
                    WHERE c.entity_type = 'wall_post'
                      AND c.entity_id = wp.id
                      AND c.moderation_status = 'approved'
                ), 0) AS comments_count
            FROM wall_posts wp
            JOIN users u ON wp.author_id = u.id
            LEFT JOIN votes uv
              ON uv.target_type = 'wall_post'
             AND uv.target_id = wp.id
             AND uv.user_id = $3
            WHERE {where_clause}
            ORDER BY wp.created_at DESC
            LIMIT $4 OFFSET $5
        """

        rows = await self.db.fetch(query, *params)
        return [dict(r) for r in rows]

    async def count_posts(
        self,
        entity_type: str,
        entity_id: Optional[int],
        entity_key: Optional[str],
    ) -> int:
        """Count wall posts for an entity."""
        et, eid, ek = self._entity_params(entity_type, entity_id, entity_key)
        if eid is not None:
            query = """
                SELECT COUNT(*) FROM wall_posts
                WHERE entity_type = $1 AND entity_id = $2
            """
            return await self.db.fetchval(query, et, eid) or 0
        query = """
            SELECT COUNT(*) FROM wall_posts
            WHERE entity_type = $1 AND entity_key = $2
        """
        return await self.db.fetchval(query, et, ek) or 0

    async def get_post(
        self,
        post_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get a single wall post by id."""
        query = """
            SELECT
                wp.id,
                wp.author_id,
                u.wallet AS author_wallet,
                wp.entity_type,
                wp.entity_id,
                wp.entity_key,
                wp.raw_body,
                wp.body_html,
                wp.content_theme,
                wp.karma_score,
                wp.created_at,
                wp.updated_at,
                COALESCE(uv.value, NULL) AS user_vote,
                COALESCE((
                    SELECT COUNT(*)
                    FROM comments c
                    WHERE c.entity_type = 'wall_post'
                      AND c.entity_id = wp.id
                      AND c.moderation_status = 'approved'
                ), 0) AS comments_count
            FROM wall_posts wp
            JOIN users u ON wp.author_id = u.id
            LEFT JOIN votes uv
              ON uv.target_type = 'wall_post'
             AND uv.target_id = wp.id
             AND uv.user_id = $2
            WHERE wp.id = $1
        """
        row = await self.db.fetchrow(query, post_id, user_id)
        return dict(row) if row else None

    async def delete_post(self, post_id: int, author_id: int) -> bool:
        """Delete a wall post if the author matches."""
        result = await self.db.fetchrow(
            "DELETE FROM wall_posts WHERE id = $1 AND author_id = $2 RETURNING id",
            post_id,
            author_id,
        )
        return result is not None

    async def assert_post_exists(self, post_id: int) -> Dict[str, Any]:
        """Ensure wall post exists, raising NotFoundError otherwise."""
        post = await self.get_post(post_id)
        if not post:
            raise NotFoundError(f"Wall post {post_id} not found")
        return post
