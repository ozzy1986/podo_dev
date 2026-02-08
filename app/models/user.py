"""
User API request/response models.
"""

from pydantic import BaseModel, Field


class LanguageUpdateRequest(BaseModel):
    """Request body for updating user language preference."""

    language: str = Field(..., min_length=2, max_length=10, description="Language code (en, ru, ar)")
