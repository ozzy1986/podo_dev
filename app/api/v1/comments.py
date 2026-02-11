"""
Comments and votes API (social layer).
"""

import math
import logging
from typing import Optional
from decimal import Decimal
from datetime import datetime

from fastapi import APIRouter, Depends, Query, HTTPException, status

from app.api.deps import get_comment_repo, get_domain_repo, get_current_user, get_current_user_optional, get_user_repo
from app.repositories.comment_repo import CommentRepository
from app.repositories.domain_repo import DomainRepository
from app.repositories.user_repo import UserRepository
from app.models.comment import CreateCommentRequest, SetVoteRequest, CommentResponse
from app.core.exceptions import NotFoundError, BadRequestError, PermissionError as AppPermissionError, PaidVoteRequiredError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Comments and votes"])


def _serialize_comment(row: dict, user_vote: Optional[int] = None) -> dict:
    out = {
        "id": row["id"],
        "author_id": row["author_id"],
        "author_wallet": row.get("author_wallet"),
        "parent_id": row.get("parent_id"),
        "entity_type": row["entity_type"],
        "entity_id": row.get("entity_id"),
        "entity_key": row.get("entity_key"),
        "body": row["body"],
        "moderation_status": row["moderation_status"],
        "karma_score": int(row.get("karma_score") or 0),
        "created_at": row["created_at"].isoformat() if isinstance(row.get("created_at"), datetime) else str(row.get("created_at")),
        "updated_at": row["updated_at"].isoformat() if isinstance(row.get("updated_at"), datetime) else str(row.get("updated_at")) if row.get("updated_at") else None,
        "user_vote": user_vote,
    }
    if isinstance(row.get("karma_score"), Decimal):
        out["karma_score"] = int(row["karma_score"])
    return out


@router.get("/comments", response_model=dict)
async def list_comments(
    entity_type: str = Query(..., description="domain | wallet | registrar | hoster | zone"),
    entity_id: Optional[int] = Query(None),
    entity_key: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """List root comments for an entity. Replies are not nested here; use GET /comments/{id} for thread."""
    try:
        total = await repo.count_comments(entity_type, entity_id, entity_key, only_approved=True)
        offset = (page - 1) * per_page
        rows = await repo.list_comments(entity_type, entity_id, entity_key, only_approved=True, limit=per_page, offset=offset)
    except BadRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    user_id = current_user["id"] if current_user else None
    items = []
    for r in rows:
        uv = await repo.get_user_vote(user_id, "comment", r["id"], None) if user_id else None
        items.append(_serialize_comment(r, uv))

    return {
        "comments": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, math.ceil(total / per_page)) if per_page else 1,
    }


@router.get("/comments/{comment_id}", response_model=dict)
async def get_comment(
    comment_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """Get a comment and its direct replies."""
    comment = await repo.get_comment(comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.get("moderation_status") != "approved":
        raise HTTPException(status_code=404, detail="Comment not found")

    user_id = current_user["id"] if current_user else None
    uv = await repo.get_user_vote(user_id, "comment", comment_id, None) if user_id else None
    out = _serialize_comment(comment, uv)

    replies = await repo.list_replies(comment_id, only_approved=True)
    out["replies"] = []
    for r in replies:
        ruv = await repo.get_user_vote(user_id, "comment", r["id"], None) if user_id else None
        out["replies"].append(_serialize_comment(r, ruv))

    return out


@router.post("/comments", status_code=status.HTTP_201_CREATED, response_model=dict)
async def create_comment(
    request: CreateCommentRequest,
    entity_type: str = Query(...),
    entity_id: Optional[int] = Query(None),
    entity_key: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """Create a comment on an entity (or reply with parent_id). Default: moderation approved (comments pass). Author gets an automatic like on their comment."""
    try:
        row = await repo.create_comment(
            author_id=current_user["id"],
            entity_type=entity_type,
            entity_id=entity_id,
            entity_key=entity_key,
            body=request.body,
            parent_id=request.parent_id,
            moderation_status="approved",
        )
        await repo.set_vote(
            user_id=current_user["id"],
            target_type="comment",
            target_id=row["id"],
            target_key=None,
            value=1,
        )
        comment = await repo.get_comment(row["id"])
        return _serialize_comment(dict(comment) if comment else dict(row), 1)
    except BadRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/comments/{comment_id}/moderation", response_model=dict)
async def set_comment_moderation(
    comment_id: int,
    status: str = Query(..., pattern="^(pending|approved|rejected)$"),
    current_user: dict = Depends(get_current_user),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """Set comment moderation status (premoderation). For now any authenticated user can change; restrict to admin later."""
    try:
        row = await repo.update_comment_moderation(comment_id, status)
    except BadRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message)
    return _serialize_comment(dict(row), None)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
    comment_id: int,
    current_user: dict = Depends(get_current_user),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """Delete own comment."""
    deleted = await repo.delete_comment(comment_id, current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Comment not found or not owner")


@router.post("/votes", response_model=dict)
async def set_vote(
    request: SetVoteRequest,
    target_type: str = Query(...),
    target_id: Optional[int] = Query(None),
    target_key: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    repo: CommentRepository = Depends(get_comment_repo),
    domain_repo: DomainRepository = Depends(get_domain_repo),
    user_repo: UserRepository = Depends(get_user_repo),
):
    """Set like (+1) or dislike (-1). Free path: amount omitted (one free vote). Paid path: amount sent (>= 1) deducts tokens. Returns 409 with code PAID_VOTE_REQUIRED when free vote already used in this direction."""
    if request.value == -1:
        if target_type == "comment" and target_id is not None:
            comment = await repo.get_comment(target_id)
            if comment and comment.get("author_id") == current_user["id"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot dislike your own comment")
        if target_type == "domain" and target_id is not None:
            domain = await domain_repo.get_by_id(target_id)
            if domain and domain.get("user_id") == current_user["id"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot dislike your own domain")

    # Explicit amount in body = paid vote (including 1). Omit amount = free vote only.
    use_paid_path = request.amount is not None
    amount = request.amount if use_paid_path else 1
    if use_paid_path and amount >= 1:
        # Paid vote: require sufficient balance, deduct, then add_paid_votes
        user = await user_repo.get_by_id(current_user["id"])
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        balance = float(user.get("accumulated_balance") or 0)
        if balance < amount:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient balance for this vote amount",
            )
        try:
            await user_repo.update_balance(current_user["id"], -float(amount), 0)
            row = await repo.add_paid_votes(
                user_id=current_user["id"],
                target_type=target_type,
                target_id=target_id,
                target_key=target_key,
                value=request.value,
                amount=amount,
            )
        except BadRequestError as e:
            await user_repo.update_balance(current_user["id"], float(amount), 0)
            raise HTTPException(status_code=e.status_code, detail=e.message)
        karma = await repo.get_entity_karma(target_type, target_id, target_key)
        return {"ok": True, "target_type": target_type, "target_id": target_id, "target_key": target_key, "value": row["value"], "karma": karma}
    try:
        row = await repo.set_vote(
            user_id=current_user["id"],
            target_type=target_type,
            target_id=target_id,
            target_key=target_key,
            value=request.value,
        )
    except PaidVoteRequiredError as e:
        raise e
    except BadRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"ok": True, "target_type": target_type, "target_id": target_id, "target_key": target_key, "value": row["value"]}


@router.delete("/votes", status_code=status.HTTP_204_NO_CONTENT)
async def remove_vote(
    target_type: str = Query(...),
    target_id: Optional[int] = Query(None),
    target_key: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """Remove your vote from a comment or entity."""
    try:
        removed = await repo.remove_vote(
            user_id=current_user["id"],
            target_type=target_type,
            target_id=target_id,
            target_key=target_key,
        )
    except BadRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    if not removed:
        raise HTTPException(status_code=404, detail="Vote not found")


@router.get("/karma", response_model=dict)
async def get_entity_karma(
    target_type: str = Query(...),
    target_id: Optional[int] = Query(None),
    target_key: Optional[str] = Query(None),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """Get karma (sum of votes) for an entity: comment, domain, registrar, hoster, zone, wallet."""
    try:
        karma = await repo.get_entity_karma(target_type, target_id, target_key)
    except BadRequestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return {"target_type": target_type, "target_id": target_id, "target_key": target_key, "karma": karma}


@router.get("/user/karma", response_model=dict)
async def get_my_karma(
    current_user: dict = Depends(get_current_user),
    repo: CommentRepository = Depends(get_comment_repo),
):
    """Get current user comment_karma and domain_karma (stored in DB, updated by triggers)."""
    comment_karma, domain_karma = await repo.get_user_karmas(current_user["id"])
    return {
        "user_id": current_user["id"],
        "karma": comment_karma,
        "comment_karma": comment_karma,
        "domain_karma": domain_karma,
    }
