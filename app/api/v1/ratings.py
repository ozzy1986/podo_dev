"""
Public rating API routes (no auth required; optional auth for karma/user_vote).
"""

import math
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException

from app.db.postgresql import get_pg_pool
from app.repositories.rating_repo import RatingRepository
from app.repositories.domain_repo import DomainRepository
from app.api.deps import get_domain_repo, get_comment_repo, get_current_user_optional
from app.repositories.comment_repo import CommentRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Ratings"])


def _get_rating_repo() -> RatingRepository:
    """Get rating repository."""
    return RatingRepository(get_pg_pool())


def _serialize(data: dict) -> dict:
    """Convert Decimal/datetime values to JSON-safe types."""
    result = {}
    for k, v in data.items():
        if isinstance(v, Decimal):
            result[k] = float(v)
        elif isinstance(v, datetime):
            result[k] = v.isoformat()
        else:
            result[k] = v
    return result


def _paginated(total: int, per_page: int) -> int:
    """Compute total_pages for pagination."""
    return max(1, math.ceil(total / per_page)) if per_page > 0 else 1


@router.get("/domain/{domain_name}")
async def get_public_domain_by_name(
    domain_name: str,
    domain_repo: DomainRepository = Depends(get_domain_repo),
    comment_repo: CommentRepository = Depends(get_comment_repo),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Get public domain info by name (for domain page and comments). Returns id, domain, owner_wallet, karma, user_vote, etc."""
    domain = await domain_repo.get_by_domain(domain_name)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")
    row = await domain_repo.db.fetchrow(
        "SELECT d.id, d.domain, d.sld_length, d.verified, d.is_mining, d.total_earnings, d.weight, "
        "d.creation_date, d.verification_time, d.description, d.parking_mode, d.parking_content, d.content_theme, u.wallet AS owner_wallet "
        "FROM domains d JOIN users u ON d.user_id = u.id WHERE d.domain = $1",
        domain_name,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Domain not found")
    out = _serialize(dict(row))
    domain_id = out["id"]
    out["karma"] = await comment_repo.get_entity_karma("domain", domain_id, None)
    out["user_vote"] = await comment_repo.get_user_vote(
        current_user["id"], "domain", domain_id, None
    ) if current_user else None
    return out


@router.get("/domains/rating")
async def domains_rating(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    sort_by: str = Query('rating'),
    sort_order: str = Query('desc', pattern='^(asc|desc)$'),
    wallet: Optional[str] = Query(None),
    sld_length: Optional[str] = Query('18'),
    registrar_id: Optional[int] = Query(None),
    hoster_id: Optional[int] = Query(None),
    zone: Optional[str] = Query(None),
    repo: RatingRepository = Depends(_get_rating_repo),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Get public domain ratings with karma and user_vote when authenticated."""
    sld = None if sld_length == 'all' else (int(sld_length) if sld_length else None)
    user_id = current_user["id"] if current_user else None
    result = await repo.get_domains_rating(
        page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order,
        wallet=wallet, sld_length=sld if sld_length != 'all' else 'all',
        registrar_id=registrar_id, hoster_id=hoster_id, zone=zone,
        user_id=user_id,
    )
    result["domains"] = [_serialize(i) for i in result.pop("items", [])]
    result["total_pages"] = _paginated(result["total"], result["per_page"])
    return result


@router.get("/domains/rating/by-registration-date")
async def domains_rating_by_date(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    sort_order: str = Query('asc', pattern='^(asc|desc)$'),
    wallet: Optional[str] = Query(None),
    repo: RatingRepository = Depends(_get_rating_repo),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Get domains sorted by registration date with karma and user_vote when authenticated."""
    user_id = current_user["id"] if current_user else None
    result = await repo.get_domains_rating_by_registration_date(
        page=page, per_page=per_page, sort_order=sort_order, wallet=wallet,
        user_id=user_id,
    )
    result["domains"] = [_serialize(i) for i in result.pop("items", [])]
    result["total_pages"] = _paginated(result["total"], result["per_page"])
    return result


@router.get("/registrars/rating")
async def registrars_rating(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    repo: RatingRepository = Depends(_get_rating_repo),
):
    """Get registrar ratings. No authentication required."""
    result = await repo.get_registrars_rating(page=page, per_page=per_page)
    result["registrars"] = [_serialize(i) for i in result.pop("items", [])]
    return result


@router.get("/hosters/rating")
async def hosters_rating(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    repo: RatingRepository = Depends(_get_rating_repo),
):
    """Get hoster ratings. No authentication required."""
    result = await repo.get_hosters_rating(page=page, per_page=per_page)
    result["hosters"] = [_serialize(i) for i in result.pop("items", [])]
    return result


@router.get("/zones/rating")
async def zones_rating(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    repo: RatingRepository = Depends(_get_rating_repo),
):
    """Get domain zone ratings. No authentication required."""
    result = await repo.get_zones_rating(page=page, per_page=per_page)
    result["zones"] = [_serialize(i) for i in result.pop("items", [])]
    return result


@router.get("/wallets/rating")
async def wallets_rating(
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    sort_by: str = Query('rating'),
    sort_order: str = Query('desc', pattern='^(asc|desc)$'),
    repo: RatingRepository = Depends(_get_rating_repo),
):
    """Get wallet ratings. No authentication required."""
    result = await repo.get_wallets_rating(
        page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order,
    )
    items = [_serialize(i) for i in result.pop("items", [])]
    for w in items:
        if "domain_count" in w:
            w["domains_count"] = w.pop("domain_count", 0)
        w["rating"] = w.get("total_earnings", 0)
    result["wallets"] = items
    result["total_pages"] = _paginated(result["total"], result["per_page"])
    return result
