"""
Unit tests for app.core.exceptions – exception hierarchy.
"""

import pytest

from app.core.exceptions import (
    AppException,
    NotFoundError,
    AuthError,
    ValidationError,
    RateLimitError,
    ConflictError,
    BadRequestError,
    ServiceUnavailableError,
    DatabaseError,
    BlockchainError,
    DNSError,
)


# ---------------------------------------------------------------------------
# AppException base class
# ---------------------------------------------------------------------------

class TestAppException:

    def test_default_status_code(self):
        exc = AppException("something broke")
        assert exc.status_code == 500
        assert exc.message == "something broke"
        assert exc.details == {}

    def test_custom_status_code(self):
        exc = AppException("nope", status_code=418)
        assert exc.status_code == 418

    def test_details(self):
        exc = AppException("err", details={"field": "name"})
        assert exc.details == {"field": "name"}

    def test_is_exception(self):
        exc = AppException("test")
        assert isinstance(exc, Exception)

    def test_str_representation(self):
        exc = AppException("readable message")
        assert str(exc) == "readable message"


# ---------------------------------------------------------------------------
# Subclass status codes
# ---------------------------------------------------------------------------

_SUBCLASS_CASES = [
    (NotFoundError, 404, "Resource not found"),
    (AuthError, 401, "Authentication failed"),
    (ValidationError, 422, "Validation failed"),
    (RateLimitError, 429, "Rate limit exceeded"),
    (ConflictError, 409, "Resource conflict"),
    (BadRequestError, 400, "Bad request"),
    (ServiceUnavailableError, 503, "Service unavailable"),
    (DatabaseError, 500, "Database error"),
    (BlockchainError, 500, "Blockchain error"),
    (DNSError, 400, "DNS verification failed"),
]


class TestExceptionSubclasses:

    @pytest.mark.parametrize("exc_cls, expected_code, default_msg", _SUBCLASS_CASES)
    def test_default_status_code(self, exc_cls, expected_code, default_msg):
        exc = exc_cls()
        assert exc.status_code == expected_code

    @pytest.mark.parametrize("exc_cls, expected_code, default_msg", _SUBCLASS_CASES)
    def test_default_message(self, exc_cls, expected_code, default_msg):
        exc = exc_cls()
        assert exc.message == default_msg

    @pytest.mark.parametrize("exc_cls, expected_code, default_msg", _SUBCLASS_CASES)
    def test_custom_message(self, exc_cls, expected_code, default_msg):
        exc = exc_cls("custom message")
        assert exc.message == "custom message"
        assert exc.status_code == expected_code

    @pytest.mark.parametrize("exc_cls, expected_code, default_msg", _SUBCLASS_CASES)
    def test_inherits_app_exception(self, exc_cls, expected_code, default_msg):
        exc = exc_cls()
        assert isinstance(exc, AppException)
        assert isinstance(exc, Exception)

    @pytest.mark.parametrize("exc_cls, expected_code, default_msg", _SUBCLASS_CASES)
    def test_details_passthrough(self, exc_cls, expected_code, default_msg):
        exc = exc_cls(details={"key": "val"})
        assert exc.details == {"key": "val"}
