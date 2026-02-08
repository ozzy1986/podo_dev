"""
Authentication Pydantic models.
"""

from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator


class RegisterRequest(BaseModel):
    """User registration request."""
    
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    language: str = Field('en', pattern='^(en|ru|ar)$', description="Language preference")


class LoginRequest(BaseModel):
    """User login request."""
    
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., description="Password")


class WalletLoginRequest(BaseModel):
    """Wallet login request. Accepts both wallet/data (WX format) and wallet_address/message."""
    
    wallet_address: str | None = Field(None, min_length=35, max_length=35, description="Waves wallet address")
    wallet: str | None = Field(None, min_length=35, max_length=35, description="Waves wallet (alias)")
    signature: str = Field(..., description="Signature from wallet")
    public_key: str = Field(..., description="Public key")
    message: str | None = Field(None, description="Original message that was signed")
    data: str | None = Field(None, description="Original data/message (WX format)")
    host: str | None = Field(None, description="Host used for signature (WX format)")
    referrer: str | None = Field(None, description="Full referrer URL sent to WX (r=), for signature verification")

    @model_validator(mode='after')
    def require_wallet_and_message(self) -> 'WalletLoginRequest':
        addr = self.wallet_address or self.wallet
        msg = self.message or self.data
        if not addr:
            raise ValueError('Either wallet_address or wallet is required')
        if not msg:
            raise ValueError('Either message or data is required')
        return self

    def get_wallet_address(self) -> str:
        return self.wallet_address or self.wallet or ""

    def get_message(self) -> str:
        return self.message or self.data or ""

    def get_host(self) -> str:
        """Host used for WX-style auth (e.g. dev.d.onl). Optional."""
        return (self.host or "").strip()

    def get_referrer(self) -> str:
        """Full referrer URL (e.g. https://dev.d.onl) sent to WX as r=. Optional."""
        return (self.referrer or "").strip()


class RefreshTokenRequest(BaseModel):
    """Request to refresh an access token using a refresh token."""

    refresh_token: str = Field(..., description="Refresh token")


class AuthResponse(BaseModel):
    """Authentication response with access + refresh tokens."""

    token: str = Field(..., description="JWT access token")
    refresh_token: Optional[str] = Field(None, description="JWT refresh token (for mobile clients)")
    token_type: str = Field(default="Bearer", description="Token type")
    user: 'UserResponse' = Field(..., description="User information")


class UserResponse(BaseModel):
    """User information response."""

    id: int = Field(..., description="User ID")
    wallet: Optional[str] = Field(None, description="Waves wallet address")
    email: Optional[str] = Field(None, description="Email address")
    language: str = Field(..., description="Language preference")
    accumulated_balance: float = Field(..., description="Accumulated balance")
    payout_mode: str = Field(..., description="Payout mode (manual/auto)")
    created_at: str = Field(..., description="Registration date")

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_created_at(cls, v: Union[str, datetime]) -> str:
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)


# Forward reference resolution
AuthResponse.model_rebuild()
