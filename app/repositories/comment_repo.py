"""
Comment and vote repository: comments (threaded), votes (like/dislike), karma.
"""

import logging
from typing import Optional, Dict, Any, List

from app.repositories.base import BaseRepository
from app.core.exceptions import NotFoundError, ConflictError, BadRequestError, PaidVoteRequiredError

logger = logging.getLogger(__name__)

ENTITY_TYPES = frozenset(("domain", "wallet", "registrar", "hoster", "zone", "wall_post"))
VOTE_TARGET_TYPES = frozenset(("comment", "domain", "registrar", "hoster", "zone", "wallet", "wall_post"))
MODERATION_STATUSES = frozenset(("pending", "approved", "rejected"))


def _entity_params(entity_type: str, entity_id: Optional[int], entity_key: Optional[str]) -> tuple:
    if entity_type not in ENTITY_TYPES:
        raise BadRequestError(f"Invalid entity_type: {entity_type}")
    if entity_type in ("domain", "registrar", "hoster"):
        if entity_id is None:
            raise BadRequestError(f"{entity_type} requires entity_id")
        return (entity_type, entity_id, None)
    if entity_type in ("wallet", "zone"):
        if not entity_key or not str(entity_key).strip():
            raise BadRequestError(f"{entity_type} requires entity_key")
        return (entity_type, None, str(entity_key).strip())
    if entity_type == "wall_post":
        if entity_id is None:
            raise BadRequestError("wall_post requires entity_id")
        return (entity_type, entity_id, None)
    raise BadRequestError(f"Invalid entity_type: {entity_type}")


def _vote_target_params(target_type: str, target_id: Optional[int], target_key: Optional[str]) -> tuple:
    if target_type not in VOTE_TARGET_TYPES:
        raise BadRequestError(f"Invalid target_type: {target_type}")
    if target_type in ("comment", "domain", "registrar", "hoster", "wall_post"):
        if target_id is None:
            raise BadRequestError(f"{target_type} vote requires target_id")
        return (target_type, target_id, None)
    if target_type in ("zone", "wallet"):
        if not target_key or not str(target_key).strip():
            raise BadRequestError(f"{target_type} vote requires target_key")
        return (target_type, None, str(target_key).strip())
    raise BadRequestError(f"Invalid target_type: {target_type}")


class CommentRepository(BaseRepository):
    """Repository for comments and votes."""

    async def create_comment(
        self,
        author_id: int,
        entity_type: str,
        entity_id: Optional[int],
        entity_key: Optional[str],
        body: str,
        parent_id: Optional[int] = None,
        moderation_status: str = "approved",
    ) -> Dict[str, Any]:
        """Create a comment. Default moderation_status=approved so comments pass."""
        if not body or not str(body).strip():
            raise BadRequestError("Comment body is required")
        if moderation_status not in MODERATION_STATUSES:
            moderation_status = "approved"
        et, eid, ek = _entity_params(entity_type, entity_id, entity_key)
        query = """
            INSERT INTO comments (author_id, parent_id, entity_type, entity_id, entity_key, body, moderation_status)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """
        row = await self.db.fetchrow(
            query, author_id, parent_id, et, eid, ek, body.strip()[:10000], moderation_status
        )
        return dict(row)

    async def get_comment(self, comment_id: int) -> Optional[Dict[str, Any]]:
        """Get comment by id."""
        return await self.fetch_one(
            "SELECT c.*, u.wallet AS author_wallet FROM comments c JOIN users u ON c.author_id = u.id WHERE c.id = $1",
            comment_id,
        )

    async def list_comments(
        self,
        entity_type: str,
        entity_id: Optional[int],
        entity_key: Optional[str],
        only_approved: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List root comments for an entity (no replies). Order by created_at desc."""
        et, eid, ek = _entity_params(entity_type, entity_id, entity_key)
        status_filter = " AND c.moderation_status = 'approved'" if only_approved else ""
        if eid is not None:
            q = f"""
                SELECT c.*, u.wallet AS author_wallet
                FROM comments c
                JOIN users u ON c.author_id = u.id
                WHERE c.entity_type = $1 AND c.entity_id = $2 AND c.parent_id IS NULL{status_filter}
                ORDER BY c.created_at DESC
                LIMIT $3 OFFSET $4
            """
            rows = await self.db.fetch(q, et, eid, limit, offset)
        else:
            q = f"""
                SELECT c.*, u.wallet AS author_wallet
                FROM comments c
                JOIN users u ON c.author_id = u.id
                WHERE c.entity_type = $1 AND c.entity_key = $2 AND c.parent_id IS NULL{status_filter}
                ORDER BY c.created_at DESC
                LIMIT $3 OFFSET $4
            """
            rows = await self.db.fetch(q, et, ek, limit, offset)
        return [dict(r) for r in rows]

    async def list_replies(self, parent_id: int, only_approved: bool = True) -> List[Dict[str, Any]]:
        """List direct replies to a comment. Order by created_at asc."""
        status_filter = " AND c.moderation_status = 'approved'" if only_approved else ""
        q = f"""
            SELECT c.*, u.wallet AS author_wallet
            FROM comments c
            JOIN users u ON c.author_id = u.id
            WHERE c.parent_id = $1{status_filter}
            ORDER BY c.created_at ASC
        """
        rows = await self.db.fetch(q, parent_id)
        return [dict(r) for r in rows]

    async def count_comments(
        self,
        entity_type: str,
        entity_id: Optional[int],
        entity_key: Optional[str],
        only_approved: bool = True,
    ) -> int:
        """Count root comments for an entity."""
        et, eid, ek = _entity_params(entity_type, entity_id, entity_key)
        status_filter = " AND moderation_status = 'approved'" if only_approved else ""
        if eid is not None:
            return await self.fetch_val(
                f"SELECT COUNT(*) FROM comments WHERE entity_type = $1 AND entity_id = $2 AND parent_id IS NULL{status_filter}",
                et,
                eid,
            ) or 0
        return await self.fetch_val(
            f"SELECT COUNT(*) FROM comments WHERE entity_type = $1 AND entity_key = $2 AND parent_id IS NULL{status_filter}",
            et,
            ek,
        ) or 0

    async def update_comment_moderation(self, comment_id: int, status: str) -> Dict[str, Any]:
        """Set moderation status (pending/approved/rejected)."""
        if status not in MODERATION_STATUSES:
            raise BadRequestError(f"Invalid moderation_status: {status}")
        row = await self.db.fetchrow(
            "UPDATE comments SET moderation_status = $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2 RETURNING *",
            status,
            comment_id,
        )
        if not row:
            raise NotFoundError(f"Comment {comment_id} not found")
        return dict(row)

    async def delete_comment(self, comment_id: int, author_id: int) -> bool:
        """Delete comment if author. Returns True if deleted."""
        row = await self.db.fetchrow(
            "DELETE FROM comments WHERE id = $1 AND author_id = $2 RETURNING id", comment_id, author_id
        )
        return row is not None

    # --- Votes ---

    async def set_vote(
        self,
        user_id: int,
        target_type: str,
        target_id: Optional[int],
        target_key: Optional[str],
        value: int,
    ) -> Dict[str, Any]:
        """Set or update free vote (+1 or -1). One free like and one free dislike per user per target. Raises PaidVoteRequiredError if user already voted in this direction."""
        if value not in (1, -1):
            raise BadRequestError("Vote value must be 1 or -1")
        tt, tid, tkey = _vote_target_params(target_type, target_id, target_key)
        if tid is not None:
            existing = await self.db.fetchrow(
                "SELECT id, value, amount, free_like_used, free_dislike_used FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id = $3 AND target_key IS NULL",
                user_id, tt, tid,
            )
        else:
            existing = await self.db.fetchrow(
                "SELECT id, value, amount, free_like_used, free_dislike_used FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id IS NULL AND target_key = $3",
                user_id, tt, tkey,
            )
        if existing:
            cur_val = existing.get("value")
            if cur_val is not None and cur_val == value:
                raise PaidVoteRequiredError("Paid vote required")
            # Opposite direction (or legacy row without value): switch vote, amount=1, set free_* for new direction
            free_like = existing.get("free_like_used") or (value == 1)
            free_dislike = existing.get("free_dislike_used") or (value == -1)
            row = await self.db.fetchrow(
                "UPDATE votes SET value = $1, amount = 1, free_like_used = $2, free_dislike_used = $3, updated_at = CURRENT_TIMESTAMP WHERE id = $4 RETURNING *",
                value, free_like, free_dislike, existing["id"],
            )
        else:
            free_like = value == 1
            free_dislike = value == -1
            row = await self.db.fetchrow(
                "INSERT INTO votes (user_id, target_type, target_id, target_key, value, amount, free_like_used, free_dislike_used) VALUES ($1, $2, $3, $4, $5, 1, $6, $7) RETURNING *",
                user_id, tt, tid, tkey, value, free_like, free_dislike,
            )
        return dict(row)

    async def add_paid_votes(
        self,
        user_id: int,
        target_type: str,
        target_id: Optional[int],
        target_key: Optional[str],
        value: int,
        amount: int,
    ) -> Dict[str, Any]:
        """Add paid votes to existing vote row (same direction). Requires existing row with same value. Returns updated row."""
        if value not in (1, -1):
            raise BadRequestError("Vote value must be 1 or -1")
        if amount < 1:
            raise BadRequestError("Paid vote amount must be at least 1")
        tt, tid, tkey = _vote_target_params(target_type, target_id, target_key)
        if tid is not None:
            existing = await self.db.fetchrow(
                "SELECT id, value FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id = $3 AND target_key IS NULL",
                user_id, tt, tid,
            )
        else:
            existing = await self.db.fetchrow(
                "SELECT id, value FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id IS NULL AND target_key = $3",
                user_id, tt, tkey,
            )
        if not existing:
            raise BadRequestError("No vote found; use free vote first")
        if existing["value"] != value:
            raise BadRequestError("Vote direction does not match existing vote")
        row = await self.db.fetchrow(
            "UPDATE votes SET amount = amount + $1, updated_at = CURRENT_TIMESTAMP WHERE id = $2 RETURNING *",
            amount, existing["id"],
        )
        return dict(row)

    async def remove_vote(
        self,
        user_id: int,
        target_type: str,
        target_id: Optional[int],
        target_key: Optional[str],
    ) -> bool:
        """Remove vote. Returns True if removed."""
        tt, tid, tkey = _vote_target_params(target_type, target_id, target_key)
        if tid is not None:
            r = await self.db.execute(
                "DELETE FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id = $3 AND target_key IS NULL",
                user_id,
                tt,
                tid,
            )
        else:
            r = await self.db.execute(
                "DELETE FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id IS NULL AND target_key = $3",
                user_id,
                tt,
                tkey,
            )
        return "DELETE" in r

    async def get_user_vote(
        self,
        user_id: int,
        target_type: str,
        target_id: Optional[int],
        target_key: Optional[str],
    ) -> Optional[int]:
        """Get current vote value (1 or -1) or None."""
        tt, tid, tkey = _vote_target_params(target_type, target_id, target_key)
        if tid is not None:
            val = await self.db.fetchval(
                "SELECT value FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id = $3 AND target_key IS NULL",
                user_id,
                tt,
                tid,
            )
        else:
            val = await self.db.fetchval(
                "SELECT value FROM votes WHERE user_id = $1 AND target_type = $2 AND target_id IS NULL AND target_key = $3",
                user_id,
                tt,
                tkey,
            )
        return val

    async def get_entity_karma(
        self,
        target_type: str,
        target_id: Optional[int],
        target_key: Optional[str],
    ) -> int:
        """Sum of votes for an entity: SUM(value * amount) (comment, domain, registrar, hoster, zone, wallet)."""
        tt, tid, tkey = _vote_target_params(target_type, target_id, target_key)
        if tid is not None:
            val = await self.db.fetchval(
                "SELECT COALESCE(SUM(v.value * COALESCE(v.amount, 1)), 0)::int FROM votes v WHERE v.target_type = $1 AND v.target_id = $2 AND v.target_key IS NULL",
                tt,
                tid,
            )
        else:
            val = await self.db.fetchval(
                "SELECT COALESCE(SUM(v.value * COALESCE(v.amount, 1)), 0)::int FROM votes v WHERE v.target_type = $1 AND v.target_id IS NULL AND v.target_key = $2",
                tt,
                tkey,
            )
        return int(val) if val is not None else 0

    async def get_user_karma(self, user_id: int) -> int:
        """User comment karma from stored users.comment_karma (updated by DB triggers)."""
        val = await self.db.fetchval(
            "SELECT comment_karma FROM users WHERE id = $1",
            user_id,
        )
        return int(val) if val is not None else 0

    async def get_user_domain_karma(self, user_id: int) -> int:
        """User domain karma from stored users.domain_karma (updated by DB triggers)."""
        val = await self.db.fetchval(
            "SELECT domain_karma FROM users WHERE id = $1",
            user_id,
        )
        return int(val) if val is not None else 0

    async def get_user_karmas(self, user_id: int) -> tuple[int, int]:
        """Return (comment_karma, domain_karma) from users table."""
        row = await self.db.fetchrow(
            "SELECT comment_karma, domain_karma FROM users WHERE id = $1",
            user_id,
        )
        if not row:
            return (0, 0)
        return (int(row["comment_karma"] or 0), int(row["domain_karma"] or 0))
