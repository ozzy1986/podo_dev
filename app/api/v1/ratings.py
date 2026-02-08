"""
Public rating API routes (no auth required).
"""

import math
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.db.postgresql import get_pg_pool
from app.repositories.rating_repo import RatingRepository

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
):
    """Get public domain ratings. No authentication required."""
    sld = None if sld_length == 'all' else (int(sld_length) if sld_length else None)
    result = await repo.get_domains_rating(
        page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order,
        wallet=wallet, sld_length=sld if sld_length != 'all' else 'all',
        registrar_id=registrar_id, hoster_id=hoster_id, zone=zone,
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
):
    """Get domains sorted by registration date. No authentication required."""
    result = await repo.get_domains_rating_by_registration_date(
        page=page, per_page=per_page, sort_order=sort_order, wallet=wallet,
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
