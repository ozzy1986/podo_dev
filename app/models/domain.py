"""
Domain Pydantic models.
"""

from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field


class AddDomainRequest(BaseModel):
    """Add domain request."""
    
    domain: str = Field(..., min_length=3, max_length=253, description="Domain name")


class UpdateDescriptionRequest(BaseModel):
    """Update domain description request."""
    
    description: Optional[str] = Field(None, max_length=500, description="Domain description")


class UpdateParkingRequest(BaseModel):
    """Update parking content request."""
    
    parking_content: Optional[str] = Field(None, description="HTML content for parking page")
    parking_mode: str = Field('redirect', pattern='^(redirect|non_redirect)$', description="Parking mode")


class DomainResponse(BaseModel):
    """Domain information response."""
    
    id: int = Field(..., description="Domain ID")
    domain: str = Field(..., description="Domain name")
    sld: str = Field(..., description="Second-level domain")
    tld: str = Field(..., description="Top-level domain")
    sld_length: int = Field(..., description="SLD length")
    verified: bool = Field(..., description="Verification status")
    is_mining: bool = Field(..., description="Mining status")
    nonce: str = Field(..., description="Verification nonce")
    description: Optional[str] = Field(None, description="Domain description")
    parking_mode: Optional[str] = Field(None, description="Parking mode")
    a_record_points_to_us: Optional[bool] = Field(None, description="A-record verification status")
    created_at: str = Field(..., description="Creation date")
    last_check: Optional[str] = Field(None, description="Last verification check")


class VerificationInfoResponse(BaseModel):
    """Domain verification information."""
    
    domain: str = Field(..., description="Domain name")
    txt_record: str = Field(..., description="TXT record value to add")
    instructions: str = Field(..., description="Verification instructions")
