"""
Pydantic models for wall post API schemas.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class CreateWallPostRequest(BaseModel):
    """Request body for creating a wall post."""

    body: str = Field(..., min_length=1, max_length=20000, description="HTML body (sanitized server-side)")
    content_theme: Optional[str] = Field(
        default="light",
        description="Theme for rendering user content (light | dark)",
        pattern="^(light|dark)$",
    )


class WallPostResponse(BaseModel):
    """Wall post response model."""

    id: int
    author_id: int
    author_wallet: Optional[str] = None
    entity_type: str
    entity_id: Optional[int] = None
    entity_key: Optional[str] = None
    body_html: Optional[str] = None
    raw_body: Optional[str] = None
    content_theme: str
    karma_score: int
    comments_count: int
    is_hidden: bool = False
    created_at: str
    updated_at: Optional[str] = None
    user_vote: Optional[int] = None
