"""
Common Pydantic models for API.
"""

from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Error response model."""
    
    error: str = Field(..., description="Error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Error details")
    status_code: int = Field(..., description="HTTP status code")


class SuccessResponse(BaseModel):
    """Success response model."""
    
    success: bool = Field(True, description="Success flag")
    message: Optional[str] = Field(None, description="Success message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


class PaginationParams(BaseModel):
    """Pagination parameters."""
    
    page: int = Field(1, ge=1, description="Page number")
    per_page: int = Field(20, ge=1, le=100, description="Items per page")
    
    @property
    def offset(self) -> int:
        """Calculate offset from page and per_page."""
        return (self.page - 1) * self.per_page
    
    @property
    def limit(self) -> int:
        """Get limit (same as per_page)."""
        return self.per_page


class PaginatedResponse(BaseModel):
    """Paginated response model."""
    
    items: list = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page")
    per_page: int = Field(..., description="Items per page")
    pages: int = Field(..., description="Total number of pages")
    
    @classmethod
    def create(cls, items: list, total: int, pagination: PaginationParams):
        """
        Create paginated response.
        
        Args:
            items: List of items for current page
            total: Total number of items
            pagination: Pagination parameters
        
        Returns:
            PaginatedResponse instance
        """
        pages = (total + pagination.per_page - 1) // pagination.per_page
        return cls(
            items=items,
            total=total,
            page=pagination.page,
            per_page=pagination.per_page,
            pages=pages
        )
