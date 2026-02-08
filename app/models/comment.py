"""
Comment and vote Pydantic models.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class CreateCommentRequest(BaseModel):
    """Create comment request."""

    body: str = Field(..., min_length=1, max_length=10000, description="Comment text")
    parent_id: Optional[int] = Field(None, description="Parent comment id for replies")


class SetVoteRequest(BaseModel):
    """Set vote (like/dislike) request."""

    value: int = Field(..., description="1 or -1")


class CommentResponse(BaseModel):
    """Comment in list/detail response."""

    id: int
    author_id: int
    author_wallet: Optional[str] = None
    parent_id: Optional[int] = None
    entity_type: str
    entity_id: Optional[int] = None
    entity_key: Optional[str] = None
    body: str
    moderation_status: str
    karma_score: int
    created_at: str
    updated_at: Optional[str] = None
    replies: Optional[List["CommentResponse"]] = None
    user_vote: Optional[int] = None


CommentResponse.model_rebuild()
