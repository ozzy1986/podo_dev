"""
FastAPI middleware for CORS, logging, error handling, and rate limiting.
"""

import time
import logging
import json
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


def make_error_response(
    status_code: int,
    error: str,
    details: dict | None = None
) -> JSONResponse:
    """Build a standardized API error response envelope."""
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "error": error,
            "details": details or {},
            "status_code": status_code,
        },
    )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging requests and responses with timing."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        path = request.url.path
        query = str(request.url.query) if request.url.query else ""
        full_url = f"{path}?{query}" if query else path
        client = request.client.host if request.client else "unknown"
        method = request.method

        logger.debug("request_start method=%s path=%s client=%s", method, full_url, client)

        try:
            response = await call_next(request)
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                "request_error method=%s path=%s client=%s elapsed=%.3fs error=%s",
                method, full_url, client, process_time, e,
                exc_info=True,
            )
            raise

        process_time = time.time() - start_time
        log_level = (
            logging.ERROR if response.status_code >= 500
            else logging.WARNING if response.status_code >= 400
            else logging.INFO
        )
        logger.log(
            log_level,
            "request_done method=%s path=%s client=%s status=%d elapsed=%.3fs",
            method, path, client, response.status_code, process_time,
        )

        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Middleware for handling application exceptions with standardized envelope."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except AppException as e:
            return make_error_response(e.status_code, e.message, e.details)
        except Exception as e:
            logger.error("unhandled_error path=%s error=%s", request.url.path, e, exc_info=True)
            from app.config import get_settings
            settings = get_settings()
            error_msg = str(e) if settings.is_development else "Internal server error"
            details = {"message": str(e)} if settings.is_development else {}
            return make_error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_msg,
                details,
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Token bucket rate limiting middleware.
    Limits requests per IP address with configurable rate and burst.
    """

    def __init__(self, app, rate_per_minute: int = 60, burst: int = 10):
        super().__init__(app)
        self.rate_per_minute = rate_per_minute
        self.burst = burst
        self.tokens_per_second = rate_per_minute / 60.0
        # IP -> (tokens, last_refill_time)
        self._buckets: dict = defaultdict(lambda: [float(burst), time.time()])
        # Stricter limits for auth endpoints
        self._auth_rate = max(10, rate_per_minute // 6)
        self._auth_buckets: dict = defaultdict(lambda: [10.0, time.time()])

    def _consume_token(self, bucket: list, rate: float, max_tokens: float) -> bool:
        """Try to consume a token from the bucket. Returns True if allowed."""
        tokens, last_time = bucket
        now = time.time()
        elapsed = now - last_time

        # Refill tokens
        tokens = min(max_tokens, tokens + elapsed * (rate / 60.0))
        bucket[1] = now

        if tokens >= 1.0:
            bucket[0] = tokens - 1.0
            return True

        bucket[0] = tokens
        return False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        # Use stricter limits for auth endpoints
        is_auth = path.startswith("/api/v1/auth/") or path.startswith("/api/auth/")

        if is_auth:
            allowed = self._consume_token(
                self._auth_buckets[client_ip],
                self._auth_rate,
                10.0
            )
        else:
            allowed = self._consume_token(
                self._buckets[client_ip],
                self.rate_per_minute,
                float(self.burst)
            )

        if not allowed:
            logger.warning(f"Rate limit exceeded for {client_ip} on {path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "details": {"retry_after_seconds": 60},
                    "status_code": 429
                },
                headers={"Retry-After": "60"}
            )

        return await call_next(request)


def setup_cors(app, origins: list):
    """Set up CORS middleware."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Process-Time"]
    )


def setup_exception_handlers(app):
    """
    Register global exception handlers so that FastAPI's HTTPException and
    Pydantic RequestValidationError return the same envelope as AppException.
    """
    from fastapi import HTTPException
    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        return make_error_response(exc.status_code, exc.message, exc.details)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return make_error_response(exc.status_code, detail)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = exc.errors()
        first = errors[0] if errors else {}
        msg = first.get("msg", "Validation error")
        return make_error_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            msg,
            {"validation_errors": errors},
        )
