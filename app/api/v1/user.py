"""
User API routes - dashboard, stats, domains, balance, rewards, payouts, etc.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.exceptions import ValidationError
from app.models.user import LanguageUpdateRequest
from app.api.deps import (
    get_current_user,
    get_user_service,
    get_domain_service,
    get_reward_repo,
    get_payout_repo,
    get_app_settings,
)
from app.services.user_service import UserService
from app.services.domain_service import DomainService
from app.repositories.reward_repo import RewardRepository
from app.repositories.payout_repo import PayoutRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/user", tags=["User"])


def _serialize(obj: Any) -> Any:
    """Convert Decimal/datetime to JSON-safe types."""
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize(v) for v in obj]
    return obj


def _build_earnings_response(
    user: Dict,
    domains: List[Dict],
    timeseries: Dict[str, Any],
) -> Dict[str, Any]:
    """Build earnings response dict. Single source of truth for structure (DRY)."""
    total = user.get("total_earned", user.get("accumulated_balance", 0)) or 0
    return {
        "daily_earnings": timeseries.get("daily_earnings", {}),
        "weekly_earnings": timeseries.get("weekly_earnings", {}),
        "avg_daily": timeseries.get("avg_daily", 0),
        "avg_weekly": timeseries.get("avg_weekly", 0),
        "earnings_by_domain": {
            d.get("domain", ""): float(d.get("total_earnings") or 0) for d in domains
        },
        "total_confirmed": total,
        "total_pending": 0,
        "total_failed": 0,
        "total_earned": total,
        "accumulated_balance": user.get("accumulated_balance", 0),
    }


def _map_system_stats(raw: Dict) -> Dict:
    """Map backend system stats to frontend-expected fields."""
    domains_rewarded = raw.get("domains_rewarded", 0) or 0
    return {
        "total_domains": domains_rewarded,
        "active_domains": domains_rewarded,
        "verified_domains": domains_rewarded,
        "total_users": raw.get("unique_wallets", 0) or 0,
        "total_rewards_distributed": float(raw.get("total_distributed", 0) or 0),
        "successful_transactions": raw.get("confirmed_transactions", raw.get("total_rewards", 0)) or 0,
        "failed_transactions": raw.get("failed_transactions", 0) or 0,
    }


@router.get("/domains")
async def get_user_domains(
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=100),
):
    """Get domains owned by current user. Frontend expects { domains: [...] }."""
    domains = await domain_service.get_user_domains(
        user_id=current_user["id"],
        limit=per_page,
        offset=(page - 1) * per_page,
    )
    return {"domains": _serialize(domains)}


@router.get("/stats")
async def get_user_stats(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get user statistics. Frontend expects domains_count, active_mining, total_earned."""
    stats = await user_service.get_user_stats(current_user["id"])
    data = dict(stats)
    data["domains_count"] = data.get("total_domains", 0)
    data["active_mining"] = data.get("mining_domains", 0)
    data["total_earned"] = data.get("total_earned", data.get("accumulated_balance", 0))
    return _serialize(data)


@router.get("/balance")
async def get_balance(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get user balance. Frontend expects accumulated_balance, pending_payout."""
    data = await user_service.get_balance(current_user["id"])
    return _serialize({
        **data,
        "accumulated_balance": data.get("balance", 0),
        "pending_payout": data.get("pending_payout", 0),
    })


@router.get("/language")
async def get_language(
    current_user: dict = Depends(get_current_user),
):
    """Get user language preference."""
    return {"language": current_user.get("language", "en")}


@router.put("/language")
async def update_language(
    request: LanguageUpdateRequest,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Update user language preference. Accepts { language: str }."""
    try:
        await user_service.update_language(current_user["id"], request.language)
        return {"language": request.language}
    except ValidationError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/widgets")
async def get_widgets(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Get widget preferences. Frontend expects { enabled_widgets: [...] }."""
    user = await user_service.get_user(current_user["id"])
    prefs = user.get("widget_preferences")
    if isinstance(prefs, str):
        import json
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}
    enabled = prefs.get("enabled_widgets", []) if isinstance(prefs, dict) else []
    return {"enabled_widgets": enabled}


@router.post("/widgets")
async def set_widgets(
    request: Request,
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
):
    """Save widget preferences. Frontend sends { enabled_widgets: [...] }."""
    body = await request.json()
    enabled_widgets = body.get("enabled_widgets", [])
    if not isinstance(enabled_widgets, list):
        raise HTTPException(status_code=400, detail="enabled_widgets must be a list")
    logger.info(f"Saving widget preferences for user {current_user['id']}: {enabled_widgets}")
    result = await user_service.update_widget_preferences(
        current_user["id"], enabled_widgets
    )
    return result


@router.get("/rewards")
async def get_rewards(
    current_user: dict = Depends(get_current_user),
    reward_repo: RewardRepository = Depends(get_reward_repo),
):
    """Get user rewards (recent). Frontend expects rewards, count."""
    wallet = current_user.get("wallet")
    if not wallet:
        return {"rewards": [], "count": 0}
    try:
        from app.db.clickhouse import get_ch_client
        ch = get_ch_client()
        rows = ch.execute_dict(
            "SELECT * FROM rewards_log WHERE wallet = %(wallet)s ORDER BY created_at DESC LIMIT 50",
            {"wallet": wallet},
        )
        rows = _serialize(rows)
        return {"rewards": rows, "count": len(rows)}
    except Exception as e:
        logger.warning(f"get_rewards failed: {e}")
        return {"rewards": [], "count": 0}


@router.get("/payouts")
async def get_payouts(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    payout_repo: PayoutRepository = Depends(get_payout_repo),
):
    """Get user payouts. Frontend expects payouts, payouts_count, payout_mode, payout_threshold, last_payout_at, pending_payout."""
    rows = await payout_repo.get_user_payout_history(
        current_user["id"], limit=50, offset=0
    )
    user = await user_service.get_user(current_user["id"])
    rows = _serialize(rows)
    last_payout = (rows[0].get("processed_at") or rows[0].get("created_at")) if rows else user.get("last_payout_at")
    return {
        "payouts": rows,
        "payouts_count": len(rows),
        "payout_mode": user.get("payout_mode", "manual"),
        "payout_threshold": user.get("payout_threshold"),
        "last_payout_at": last_payout,
        "pending_payout": user.get("pending_payout", 0),
    }


def _build_domain_health(domains: List[Dict]) -> Dict:
    """Build full domain health structure expected by frontend."""
    from datetime import datetime, date
    today = date.today()
    expiring_days = 30
    expiring_soon = []
    failed_checks_list = []
    needs_verification = []
    healthy = []
    for d in domains:
        domain_name = d.get("domain")
        verified = d.get("verified", False)
        is_mining = d.get("is_mining", False)
        failed = d.get("failed_checks", 0) or 0
        expires_at = d.get("domain_expires_at")
        item = {"domain": domain_name, "verified": verified, "is_mining": is_mining, "last_check": d.get("last_check")}
        if expires_at:
            try:
                exp_date = expires_at.date() if isinstance(expires_at, datetime) else expires_at
                if isinstance(exp_date, date) and (exp_date - today).days <= expiring_days:
                    expiring_soon.append(item)
            except (TypeError, AttributeError):
                pass
        if failed > 0:
            failed_checks_list.append(item)
        if not verified:
            needs_verification.append(item)
        elif is_mining:
            healthy.append(item)
    return {
        "domains": [{"domain": d.get("domain"), "verified": d.get("verified"), "is_mining": d.get("is_mining"), "last_check": d.get("last_check")} for d in domains],
        "expiring_soon": _serialize(expiring_soon),
        "failed_checks": _serialize(failed_checks_list),
        "needs_verification": _serialize(needs_verification),
        "healthy": _serialize(healthy),
        "total_domains": len(domains),
        "expiring_count": len(expiring_soon),
        "failed_count": len(failed_checks_list),
        "needs_verification_count": len(needs_verification),
    }


@router.get("/domains/health")
async def get_domain_health(
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service),
):
    """Get domain health status. Frontend expects expiring_soon, failed_checks, needs_verification, healthy, counts."""
    domains = await domain_service.get_user_domains(
        user_id=current_user["id"], limit=200
    )
    return _serialize(_build_domain_health(domains))


@router.get("/earnings")
async def get_earnings(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    domain_service: DomainService = Depends(get_domain_service),
    reward_repo: RewardRepository = Depends(get_reward_repo),
):
    """Get user earnings. Frontend expects daily_earnings, weekly_earnings, avg_daily, avg_weekly, earnings_by_domain, total_confirmed, total_pending, total_failed."""
    user = await user_service.get_user(current_user["id"])
    domains = await domain_service.get_user_domains(current_user["id"], limit=500)
    timeseries = await reward_repo.get_user_earnings_timeseries(
        current_user.get("wallet") or ""
    )
    return _serialize(_build_earnings_response(user, domains, timeseries))


@router.get("/dashboard")
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service),
    domain_service: DomainService = Depends(get_domain_service),
    payout_repo: PayoutRepository = Depends(get_payout_repo),
    reward_repo: RewardRepository = Depends(get_reward_repo),
):
    """Combined dashboard data in one request."""
    import time
    t0 = time.time()
    user_id = current_user["id"]

    balance = await user_service.get_balance(user_id)
    stats_raw = await user_service.get_user_stats(user_id)
    stats = dict(stats_raw)
    stats["domains_count"] = stats.get("total_domains", 0)
    stats["active_mining"] = stats.get("mining_domains", 0)
    stats["total_earned"] = stats.get("total_earned", stats.get("accumulated_balance", 0))
    domains = await domain_service.get_user_domains(user_id, limit=100)
    payouts_rows = await payout_repo.get_user_payout_history(user_id, limit=20)

    user = await user_service.get_user(user_id)
    prefs = user.get("widget_preferences")
    if isinstance(prefs, str):
        import json
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}
    enabled_widgets = prefs.get("enabled_widgets", []) if isinstance(prefs, dict) else []

    query_time = int((time.time() - t0) * 1000)

    try:
        from app.db.clickhouse import get_ch_client
        ch = get_ch_client()
        rewards = ch.execute_dict(
            "SELECT * FROM rewards_log WHERE wallet = %(wallet)s ORDER BY created_at DESC LIMIT 20",
            {"wallet": current_user.get("wallet", "")},
        ) if current_user.get("wallet") else []
        sys_stats = ch.execute_dict(
            """SELECT
                COUNT(*) as total_rewards,
                SUM(amount) as total_distributed,
                uniq(wallet) as unique_wallets,
                uniq(domain_id) as domains_rewarded,
                countIf(status = 'confirmed') as confirmed_transactions,
                countIf(status = 'failed') as failed_transactions
            FROM rewards_log"""
        )
        system_stats = sys_stats[0] if sys_stats else {}
    except Exception as e:
        logger.warning(f"Dashboard CH query failed: {e}")
        rewards = []
        system_stats = {}

    domain_health = _build_domain_health(domains)
    payouts_ser = _serialize(payouts_rows)
    payouts_obj = {
        "payouts": payouts_ser,
        "payouts_count": len(payouts_ser),
        "payout_mode": user.get("payout_mode", "manual"),
        "payout_threshold": user.get("payout_threshold"),
        "last_payout_at": (payouts_ser[0].get("processed_at") or payouts_ser[0].get("created_at")) if payouts_ser else user.get("last_payout_at"),
        "pending_payout": user.get("pending_payout", 0),
    }
    timeseries = await reward_repo.get_user_earnings_timeseries(
        current_user.get("wallet") or ""
    )
    earnings_obj = _build_earnings_response(user, domains, timeseries)
    sys_map = _map_system_stats(system_stats)

    return _serialize({
        "balance": {**balance, "accumulated_balance": balance.get("balance", 0), "pending_payout": balance.get("pending_payout", 0)},
        "stats": stats,
        "domains": {"domains": domains},
        "rewards": {"rewards": _serialize(rewards), "count": len(rewards)},
        "payouts": payouts_obj,
        "domain_health": domain_health,
        "earnings": earnings_obj,
        "system_stats": sys_map,
        "widget_preferences": {"enabled_widgets": enabled_widgets},
        "_meta": {"query_time_ms": query_time, "processing_time_ms": int((time.time() - t0) * 1000)},
    })
