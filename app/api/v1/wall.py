"""
Wall posts API endpoints.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_comment_repo,
    get_current_user,
    get_current_user_optional,
    get_wall_post_repo,
)
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.wall_post import CreateWallPostRequest, WallPostResponse
from app.repositories.comment_repo import CommentRepository
from app.repositories.wall_post_repo import WallPostRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wall", tags=["Wall"])


def _serialize_wall_post(row: dict, current_user_id: Optional[int]) -> dict:
    karma = int(row.get("karma_score") or 0)
    is_hidden = karma < 0 and (current_user_id is None or current_user_id != row.get("author_id"))
    author_id = row.get("author_id")
    include_raw = current_user_id is not None and current_user_id == author_id

    created_at = row.get("created_at")
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    elif created_at is not None:
        created_at = str(created_at)

    updated_at = row.get("updated_at")
    if isinstance(updated_at, datetime):
        updated_at = updated_at.isoformat()
    elif updated_at is not None:
        updated_at = str(updated_at)

    payload = {
        "id": row.get("id"),
        "author_id": author_id,
        "author_wallet": row.get("author_wallet"),
        "entity_type": row.get("entity_type"),
        "entity_id": row.get("entity_id"),
        "entity_key": row.get("entity_key"),
        "body_html": None if is_hidden else row.get("body_html"),
        "raw_body": row.get("raw_body") if include_raw and not is_hidden else None,
        "content_theme": row.get("content_theme"),
        "karma_score": karma,
        "comments_count": int(row.get("comments_count") or 0),
        "is_hidden": is_hidden,
        "created_at": created_at,
        "updated_at": updated_at,
        "user_vote": row.get("user_vote"),
    }
    return payload


@router.get("/posts", response_model=dict)
async def list_wall_posts(
    entity_type: str = Query(..., description="domain | wallet"),
    entity_id: Optional[int] = Query(None),
    entity_key: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_current_user_optional),
    repo: WallPostRepository = Depends(get_wall_post_repo),
) -> dict:
    """List wall posts for a wallet or domain page."""
    try:
        total = await repo.count_posts(entity_type, entity_id, entity_key)
        offset = (page - 1) * per_page
        rows = await repo.list_posts(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_key=entity_key,
            user_id=current_user["id"] if current_user else None,
            limit=per_page,
            offset=offset,
        )
    except BadRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    user_id = current_user["id"] if current_user else None
    posts = [_serialize_wall_post(r, user_id) for r in rows]
    return {
        "posts": posts,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, math.ceil(total / per_page)) if per_page else 1,
    }


@router.post("/posts", status_code=status.HTTP_201_CREATED, response_model=WallPostResponse)
async def create_wall_post(
    request: CreateWallPostRequest,
    entity_type: str = Query(...),
    entity_id: Optional[int] = Query(None),
    entity_key: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    repo: WallPostRepository = Depends(get_wall_post_repo),
    comment_repo: CommentRepository = Depends(get_comment_repo),
) -> dict:
    """Create a wall post. Author automatically receives an upvote."""
    try:
        row = await repo.create_post(
            author_id=current_user["id"],
            entity_type=entity_type,
            entity_id=entity_id,
            entity_key=entity_key,
            raw_body=request.body,
            content_theme=request.content_theme,
        )
    except BadRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    # Auto-like the post by the author (free vote path)
    post_id = row.get("id")
    if post_id:
        try:
            await comment_repo.set_vote(
                user_id=current_user["id"],
                target_type="wall_post",
                target_id=post_id,
                target_key=None,
                value=1,
            )
        except (BadRequestError, NotFoundError) as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.message)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to auto-like wall post %s: %s", post_id, exc)

    post = await repo.get_post(post_id, current_user["id"])
    if not post:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load wall post")
    return _serialize_wall_post(post, current_user["id"])


@router.get("/posts/{post_id}", response_model=WallPostResponse)
async def get_wall_post(
    post_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    repo: WallPostRepository = Depends(get_wall_post_repo),
) -> dict:
    """Fetch a single wall post by id."""
    post = await repo.get_post(post_id, current_user["id"] if current_user else None)
    if not post:
        raise HTTPException(status_code=404, detail="Wall post not found")
    return _serialize_wall_post(post, current_user["id"] if current_user else None)


@router.delete("/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_wall_post(
    post_id: int,
    current_user: dict = Depends(get_current_user),
    repo: WallPostRepository = Depends(get_wall_post_repo),
):
    """Delete a wall post if the current user is the author."""
    deleted = await repo.delete_post(post_id, current_user["id"])
    if not deleted:
        # Determine whether post exists for better error message
        post = await repo.get_post(post_id, current_user["id"])
        if post:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's wall post")
        raise HTTPException(status_code=404, detail="Wall post not found")
