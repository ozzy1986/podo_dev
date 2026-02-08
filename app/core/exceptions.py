"""
Custom exception hierarchy for the application.
"""

from typing import Any, Dict, Optional


class AppException(Exception):
    """Base exception for all application errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize application exception.
        
        Args:
            message: Error message
            status_code: HTTP status code
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppException):
    """Resource not found error."""
    
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=404, details=details)


class AuthError(AppException):
    """Authentication error."""
    
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=401, details=details)


class PermissionError(AppException):
    """Permission/authorization error."""
    
    def __init__(self, message: str = "Permission denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=403, details=details)


class ValidationError(AppException):
    """Validation error."""
    
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=422, details=details)


class RateLimitError(AppException):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=429, details=details)


class ConflictError(AppException):
    """Conflict error (e.g., duplicate resource)."""
    
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=409, details=details)


class BadRequestError(AppException):
    """Bad request error."""
    
    def __init__(self, message: str = "Bad request", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)


class ServiceUnavailableError(AppException):
    """Service unavailable error."""
    
    def __init__(self, message: str = "Service unavailable", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=503, details=details)


class DatabaseError(AppException):
    """Database operation error."""
    
    def __init__(self, message: str = "Database error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class BlockchainError(AppException):
    """Blockchain operation error."""
    
    def __init__(self, message: str = "Blockchain error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=500, details=details)


class DNSError(AppException):
    """DNS verification error."""
    
    def __init__(self, message: str = "DNS verification failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, status_code=400, details=details)
