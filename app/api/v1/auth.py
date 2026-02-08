"""
Authentication API routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service, get_current_user
from app.services.auth_service import AuthService
from app.models.auth import (
    RegisterRequest,
    LoginRequest,
    WalletLoginRequest,
    RefreshTokenRequest,
    AuthResponse,
    UserResponse
)
from app.core.exceptions import AuthError, ValidationError, ConflictError

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Register a new user with email and password.
    
    - **email**: Valid email address
    - **password**: Minimum 8 characters
    - **language**: Language preference (en, ru, ar)
    """
    try:
        result = await auth_service.register_with_email(
            email=request.email,
            password=request.password,
            language=request.language,
        )
        return AuthResponse(
            token=result['token'],
            refresh_token=result.get('refresh_token'),
            user=UserResponse(**result['user']),
        )
    except (ValidationError, ConflictError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/login", response_model=AuthResponse)
async def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Login with email and password.
    
    - **email**: Email address
    - **password**: Password
    """
    try:
        result = await auth_service.login_with_email(
            email=request.email,
            password=request.password,
        )
        return AuthResponse(
            token=result['token'],
            refresh_token=result.get('refresh_token'),
            user=UserResponse(**result['user']),
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/login-wallet", response_model=AuthResponse)
async def login_wallet(
    request: WalletLoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Login with Waves wallet signature.

    - **wallet_address**: Waves wallet address (3P...)
    - **signature**: Signature from wallet
    - **public_key**: Public key
    - **message**: Original message that was signed
    """
    try:
        result = await auth_service.login_with_wallet(
            wallet_address=request.get_wallet_address(),
            signature=request.signature,
            public_key=request.public_key,
            message=request.get_message(),
            host=request.get_host(),
            referrer=request.get_referrer(),
        )
        return AuthResponse(
            token=result['token'],
            refresh_token=result.get('refresh_token'),
            user=UserResponse(**result['user']),
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/refresh", response_model=AuthResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Exchange a refresh token for a new access + refresh token pair.

    Mobile clients should call this when their access token expires
    instead of requiring the user to log in again.
    """
    try:
        result = await auth_service.refresh_tokens(request.refresh_token)
        return AuthResponse(
            token=result['token'],
            refresh_token=result.get('refresh_token'),
            user=UserResponse(**result['user'])
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user information.
    
    Requires authentication token in Authorization header or X-Auth-Token header.
    """
    return UserResponse(**current_user)
