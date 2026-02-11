"""
Rating repository for public domain/wallet/registrar/hoster/zone rankings.
"""

import logging
from typing import Dict, Optional, List, Any

from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

# Allowed sort columns for domains rating
_DOMAIN_SORT_MAP = {
    'rating': "COALESCE(d.total_earnings, 0)",
    'weight': "COALESCE(d.weight, 0)",
    'newest': "COALESCE(d.promoted_at, d.verification_time, d.creation_date)",
    'age': "EXTRACT(EPOCH FROM (NOW() - d.creation_date)) / 31557600.0",
    'creation_date': "d.creation_date",
    'length': "d.sld_length",
}

_WALLET_SORT_MAP = {
    'rating': "total_earnings",
    'domains_count': "domain_count",
}


class RatingRepository(BaseRepository):
    """Repository for public rating queries."""

    async def get_domains_rating(
        self,
        page: int = 1,
        per_page: int = 100,
        sort_by: str = 'rating',
        sort_order: str = 'desc',
        wallet: Optional[str] = None,
        sld_length: Optional[Any] = 18,
        registrar_id: Optional[int] = None,
        hoster_id: Optional[int] = None,
        zone: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict:
        """Get paginated domain ratings with karma and optional user_vote."""
        order = 'DESC' if sort_order == 'desc' else 'ASC'
        sort_col = _DOMAIN_SORT_MAP.get(sort_by, _DOMAIN_SORT_MAP['rating'])

        where_clauses = ["d.is_mining = TRUE"]
        params: list = []
        idx = 1

        if wallet:
            where_clauses.append(f"u.wallet = ${idx}")
            params.append(wallet)
            idx += 1

        if sld_length is not None and str(sld_length) != 'all':
            sld_val = int(sld_length)
            if sld_val >= 18:
                where_clauses.append(f"d.sld_length >= ${idx}")
            else:
                where_clauses.append(f"d.sld_length = ${idx}")
            params.append(sld_val)
            idx += 1

        if registrar_id is not None:
            where_clauses.append(f"d.registrar_id = ${idx}")
            params.append(registrar_id)
            idx += 1

        if hoster_id is not None:
            where_clauses.append(f"d.hoster_id = ${idx}")
            params.append(hoster_id)
            idx += 1

        if zone:
            where_clauses.append(f"LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', '')) = ${idx}")
            params.append(zone.lower())
            idx += 1

        where_sql = " AND ".join(where_clauses)

        # Count
        count_sql = f"""
            SELECT COUNT(*) FROM domains d
            JOIN users u ON d.user_id = u.id
            WHERE {where_sql}
        """
        total = await self.db.fetchval(count_sql, *params)

        # Promoted domains first, then by sort column
        order_sql = f"""
            CASE WHEN d.promoted_at IS NOT NULL AND d.promoted_at > NOW() - INTERVAL '7 days'
                 THEN 0 ELSE 1 END ASC,
            {sort_col} {order} NULLS LAST, d.domain ASC
        """

        offset = (page - 1) * per_page
        karma_select = ", (SELECT COALESCE(SUM(v.value), 0)::int FROM votes v WHERE v.target_type = 'domain' AND v.target_id = d.id) AS karma"
        if user_id is not None:
            params.extend([per_page, offset, user_id])
            user_vote_select = f", (SELECT v.value FROM votes v WHERE v.user_id = ${idx + 3} AND v.target_type = 'domain' AND v.target_id = d.id LIMIT 1) AS user_vote"
        else:
            params.extend([per_page, offset])
            user_vote_select = ", NULL::smallint AS user_vote"

        data_sql = f"""
            SELECT d.id, d.domain, d.description, d.sld_length, d.total_earnings, d.weight,
                   d.is_clickable, d.a_record_points_to_us, d.promoted_at, d.user_id, u.wallet,
                   d.creation_date, d.verification_time
                   {karma_select}
                   {user_vote_select}
            FROM domains d
            JOIN users u ON d.user_id = u.id
            WHERE {where_sql}
            ORDER BY {order_sql}
            LIMIT ${idx} OFFSET ${idx + 1}
        """
        rows = await self.db.fetch(data_sql, *params)
        items = [dict(r) for r in rows]
        for it in items:
            if it.get("user_vote") is not None:
                it["user_vote"] = int(it["user_vote"])
            else:
                it["user_vote"] = None
            it.setdefault("karma", 0)

        return {"items": items, "total": total, "page": page, "per_page": per_page}

    async def get_domains_rating_by_registration_date(
        self,
        page: int = 1,
        per_page: int = 100,
        sort_order: str = 'asc',
        wallet: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Dict:
        """Get domains sorted by registration/creation date with karma and optional user_vote."""
        order = 'ASC' if sort_order == 'asc' else 'DESC'

        where_clauses = ["d.verified = TRUE", "d.is_mining = TRUE"]
        params: list = []
        idx = 1

        if wallet:
            where_clauses.append(f"u.wallet = ${idx}")
            params.append(wallet)
            idx += 1

        where_sql = " AND ".join(where_clauses)

        total = await self.db.fetchval(
            f"SELECT COUNT(*) FROM domains d JOIN users u ON d.user_id = u.id WHERE {where_sql}",
            *params
        )

        offset = (page - 1) * per_page
        karma_select = ", (SELECT COALESCE(SUM(v.value), 0)::int FROM votes v WHERE v.target_type = 'domain' AND v.target_id = d.id) AS karma"
        if user_id is not None:
            params.extend([per_page, offset, user_id])
            user_vote_select = f", (SELECT v.value FROM votes v WHERE v.user_id = ${idx + 3} AND v.target_type = 'domain' AND v.target_id = d.id LIMIT 1) AS user_vote"
        else:
            params.extend([per_page, offset])
            user_vote_select = ", NULL::smallint AS user_vote"

        rows = await self.db.fetch(
            f"""
            SELECT d.id, d.domain, d.description, d.sld_length, d.total_earnings, d.weight,
                   d.is_clickable, d.a_record_points_to_us, d.promoted_at, d.user_id, u.wallet,
                   d.creation_date, d.verification_time
                   {karma_select}
                   {user_vote_select}
            FROM domains d
            JOIN users u ON d.user_id = u.id
            WHERE {where_sql}
            ORDER BY d.creation_date {order} NULLS LAST, d.domain ASC
            LIMIT ${idx} OFFSET ${idx + 1}
            """,
            *params
        )

        items = [dict(r) for r in rows]
        for it in items:
            if it.get("user_vote") is not None:
                it["user_vote"] = int(it["user_vote"])
            else:
                it["user_vote"] = None
            it.setdefault("karma", 0)

        return {"items": items, "total": total, "page": page, "per_page": per_page}

    async def get_registrars_rating(self, page: int = 1, per_page: int = 100) -> Dict:
        """Get registrar rankings by total earnings."""
        total = await self.db.fetchval(
            "SELECT COUNT(DISTINCT r.id) FROM registrars r JOIN domains d ON d.registrar_id = r.id AND d.is_mining = TRUE"
        )

        offset = (page - 1) * per_page
        rows = await self.db.fetch(
            """
            SELECT r.id, r.name, r.slug,
                   COALESCE(SUM(d.total_earnings), 0)::numeric(20,8) AS total_earnings,
                   COUNT(d.id) AS domains_count
            FROM registrars r
            LEFT JOIN domains d ON d.registrar_id = r.id AND d.is_mining = TRUE
            GROUP BY r.id, r.name, r.slug
            HAVING COUNT(d.id) > 0
            ORDER BY total_earnings DESC, r.name ASC
            LIMIT $1 OFFSET $2
            """,
            per_page, offset
        )

        return {"items": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page}

    async def get_hosters_rating(self, page: int = 1, per_page: int = 100) -> Dict:
        """Get hoster rankings by total earnings."""
        total = await self.db.fetchval(
            "SELECT COUNT(DISTINCT h.id) FROM hosters h JOIN domains d ON d.hoster_id = h.id AND d.is_mining = TRUE"
        )

        offset = (page - 1) * per_page
        rows = await self.db.fetch(
            """
            SELECT h.id, h.name, h.slug,
                   COALESCE(SUM(d.total_earnings), 0)::numeric(20,8) AS total_earnings,
                   COUNT(d.id) AS domains_count
            FROM hosters h
            LEFT JOIN domains d ON d.hoster_id = h.id AND d.is_mining = TRUE
            GROUP BY h.id, h.name, h.slug
            HAVING COUNT(d.id) > 0
            ORDER BY total_earnings DESC, h.name ASC
            LIMIT $1 OFFSET $2
            """,
            per_page, offset
        )

        return {"items": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page}

    async def get_zones_rating(self, page: int = 1, per_page: int = 100) -> Dict:
        """Get domain zone rankings by total earnings."""
        total = await self.db.fetchval(
            """
            SELECT COUNT(DISTINCT LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', '')))
            FROM domains d
            WHERE d.is_mining = TRUE AND d.domain LIKE '%%.%%'
            """
        )

        offset = (page - 1) * per_page
        rows = await self.db.fetch(
            """
            SELECT LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', '')) AS zone,
                   COALESCE(SUM(d.total_earnings), 0)::numeric(20,8) AS total_earnings,
                   COUNT(d.id) AS domains_count
            FROM domains d
            WHERE d.is_mining = TRUE AND d.domain LIKE '%%.%%'
            GROUP BY LOWER(REGEXP_REPLACE(d.domain, '^.*\\.', ''))
            ORDER BY total_earnings DESC, zone ASC
            LIMIT $1 OFFSET $2
            """,
            per_page, offset
        )

        return {"items": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page}

    async def get_wallets_rating(
        self,
        page: int = 1,
        per_page: int = 100,
        sort_by: str = 'rating',
        sort_order: str = 'desc',
    ) -> Dict:
        """Get wallet rankings."""
        order = 'DESC' if sort_order == 'desc' else 'ASC'
        sort_col = _WALLET_SORT_MAP.get(sort_by, 'total_earnings')

        total = await self.db.fetchval(
            """
            SELECT COUNT(DISTINCT u.wallet) FROM users u
            JOIN domains d ON u.id = d.user_id
            WHERE d.is_mining = TRUE AND u.wallet IS NOT NULL
            """
        )

        offset = (page - 1) * per_page
        rows = await self.db.fetch(
            f"""
            SELECT u.wallet,
                   COUNT(d.id) AS domain_count,
                   COALESCE(SUM(d.total_earnings), 0) AS total_earnings,
                   COALESCE(SUM(d.weight), 0) AS total_weight
            FROM users u
            JOIN domains d ON u.id = d.user_id
            WHERE d.is_mining = TRUE AND u.wallet IS NOT NULL
            GROUP BY u.wallet
            ORDER BY {sort_col} {order} NULLS LAST
            LIMIT $1 OFFSET $2
            """,
            per_page, offset
        )

        return {"items": [dict(r) for r in rows], "total": total, "page": page, "per_page": per_page}
