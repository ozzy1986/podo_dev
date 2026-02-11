"""
Tests for comments and votes API: create comment (auto-like), set_vote, block dislike on own comment/domain, paid votes (409, success, insufficient balance).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.api.deps import get_comment_repo, get_domain_repo, get_current_user, get_user_repo
from app.core.exceptions import PaidVoteRequiredError


@pytest.fixture
def sample_user():
    return {"id": 1, "wallet": "3N7KTest", "email": "u@ex.com", "language": "en"}


@pytest.fixture
def auth_headers_comments(test_app, sample_user):
    """Auth headers and overrides for comments API tests (current_user id=1)."""
    test_app.dependency_overrides[get_current_user] = lambda: sample_user
    yield {"Authorization": "Bearer test-token"}
    test_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_comment_repo():
    repo = MagicMock()
    repo.create_comment = AsyncMock()
    repo.get_comment = AsyncMock(return_value=None)
    repo.set_vote = AsyncMock()
    repo.add_paid_votes = AsyncMock()
    repo.list_comments = AsyncMock(return_value=[])
    repo.count_comments = AsyncMock(return_value=0)
    repo.list_replies = AsyncMock(return_value=[])
    repo.get_user_vote = AsyncMock(return_value=None)
    repo.get_entity_karma = AsyncMock(return_value=0)
    repo.remove_vote = AsyncMock(return_value=True)
    repo.delete_comment = AsyncMock(return_value=True)
    repo.update_comment_moderation = AsyncMock()
    return repo


@pytest.fixture
def mock_user_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value={"id": 1, "accumulated_balance": 100.0})
    repo.update_balance = AsyncMock(return_value={"id": 1, "accumulated_balance": 95.0})
    return repo


@pytest.fixture
def mock_domain_repo():
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_domain = AsyncMock(return_value=None)
    return repo


@pytest.mark.asyncio
async def test_create_comment_adds_author_like(client, test_app, auth_headers_comments, mock_comment_repo, sample_user):
    """Creating a comment automatically adds a like from the author and returns user_vote=1."""
    created_row = {
        "id": 99,
        "author_id": sample_user["id"],
        "author_wallet": sample_user["wallet"],
        "parent_id": None,
        "entity_type": "domain",
        "entity_id": 10,
        "entity_key": None,
        "body": "Hello",
        "moderation_status": "approved",
        "karma_score": 1,
        "created_at": "2025-01-01T12:00:00",
        "updated_at": None,
    }
    mock_comment_repo.create_comment.return_value = created_row
    mock_comment_repo.get_comment.return_value = {**created_row, "karma_score": 1}
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo

    try:
        resp = client.post(
            "/api/v1/comments?entity_type=domain&entity_id=10",
            json={"body": "Hello"},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_vote"] == 1
        assert data["karma_score"] == 1
        assert mock_comment_repo.set_vote.called
        call_kw = mock_comment_repo.set_vote.call_args[1]
        assert call_kw["user_id"] == sample_user["id"]
        assert call_kw["target_type"] == "comment"
        assert call_kw["target_id"] == 99
        assert call_kw["value"] == 1
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)


@pytest.mark.asyncio
async def test_set_vote_dislike_own_comment_returns_400(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, sample_user):
    """Disliking your own comment returns 400."""
    mock_comment_repo.get_comment.return_value = {"id": 5, "author_id": sample_user["id"]}
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=comment&target_id=5&value=-1",
            json={"value": -1},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 400
        body = resp.json()
        msg = (body.get("detail") or body.get("error") or "").lower()
        assert "cannot dislike your own comment" in msg
        mock_comment_repo.set_vote.assert_not_called()
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)


@pytest.mark.asyncio
async def test_set_vote_dislike_own_domain_returns_400(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, sample_user):
    """Disliking your own domain returns 400."""
    mock_comment_repo.get_comment.return_value = None
    mock_domain_repo.get_by_id.return_value = {"id": 10, "user_id": sample_user["id"]}
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=domain&target_id=10&value=-1",
            json={"value": -1},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 400
        body = resp.json()
        msg = (body.get("detail") or body.get("error") or "").lower()
        assert "cannot dislike your own domain" in msg
        mock_comment_repo.set_vote.assert_not_called()
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)


@pytest.mark.asyncio
async def test_set_vote_like_own_comment_allowed(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, sample_user):
    """Liking your own comment is allowed (e.g. after create)."""
    mock_comment_repo.get_comment.return_value = {"id": 5, "author_id": sample_user["id"]}
    mock_comment_repo.set_vote.return_value = {"value": 1}
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=comment&target_id=5&value=1",
            json={"value": 1},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 200
        assert resp.json().get("value") == 1
        mock_comment_repo.set_vote.assert_called_once()
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)


def _assert_409_paid_vote_envelope(resp, body):
    """Assert response is 409 with envelope shape required by frontend (ok, error, details.code)."""
    assert resp.status_code == 409, f"expected 409 got {resp.status_code}"
    assert body.get("ok") is False, "envelope must have ok: false so frontend can show paid form"
    assert "error" in body, "envelope must have error message"
    details = body.get("details") or {}
    assert details.get("code") == "PAID_VOTE_REQUIRED", (
        f"details.code must be PAID_VOTE_REQUIRED so frontend shows paid form, got {details!r}"
    )


@pytest.mark.asyncio
async def test_set_vote_same_direction_returns_409_paid_vote_required(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, sample_user):
    """When user already voted in same direction, API returns 409 with envelope (ok, error, details.code)."""
    mock_comment_repo.get_comment.return_value = {"id": 5, "author_id": 999}
    mock_comment_repo.set_vote.side_effect = PaidVoteRequiredError("Paid vote required")
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=comment&target_id=5&value=1",
            json={"value": 1},
            headers=auth_headers_comments,
        )
        body = resp.json()
        _assert_409_paid_vote_envelope(resp, body)
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)


@pytest.mark.asyncio
async def test_set_vote_domain_409_paid_vote_required_envelope(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, sample_user):
    """POST /votes for domain with same-direction vote returns 409 with full envelope (catches wrong body in production)."""
    mock_domain_repo.get_by_id.return_value = {"id": 448, "user_id": 999}
    mock_comment_repo.set_vote.side_effect = PaidVoteRequiredError("Paid vote required")
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=domain&value=-1&target_id=448",
            json={"value": -1},
            headers=auth_headers_comments,
        )
        body = resp.json()
        _assert_409_paid_vote_envelope(resp, body)
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)


@pytest.mark.asyncio
async def test_set_paid_vote_success(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, mock_user_repo, sample_user):
    """Paid vote with sufficient balance: deducts balance, adds votes, returns karma."""
    mock_domain_repo.get_by_id.return_value = {"id": 10, "user_id": 999}
    mock_comment_repo.add_paid_votes.return_value = {"value": 1, "amount": 6}
    mock_comment_repo.get_entity_karma.return_value = 10
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo
    test_app.dependency_overrides[get_user_repo] = lambda: mock_user_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=domain&target_id=10&value=1",
            json={"value": 1, "amount": 5},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("value") == 1
        assert data.get("karma") == 10
        mock_user_repo.update_balance.assert_called_once()
        assert mock_user_repo.update_balance.call_args[0][1] == -5.0
        mock_comment_repo.add_paid_votes.assert_called_once()
        add_kw = mock_comment_repo.add_paid_votes.call_args[1]
        assert add_kw["amount"] == 5
        assert add_kw["value"] == 1
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)
        test_app.dependency_overrides.pop(get_user_repo, None)


@pytest.mark.asyncio
async def test_set_paid_vote_amount_one_uses_paid_path(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, mock_user_repo, sample_user):
    """Submitting amount=1 from paid form uses paid path (deducts 1 token), not free path."""
    mock_domain_repo.get_by_id.return_value = {"id": 10, "user_id": 999}
    mock_comment_repo.add_paid_votes.return_value = {"value": 1, "amount": 1}
    mock_comment_repo.get_entity_karma.return_value = 5
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo
    test_app.dependency_overrides[get_user_repo] = lambda: mock_user_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=domain&target_id=10&value=1",
            json={"value": 1, "amount": 1},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 200
        mock_comment_repo.add_paid_votes.assert_called_once()
        mock_user_repo.update_balance.assert_called_once()
        assert mock_user_repo.update_balance.call_args[0][1] == -1.0
        mock_comment_repo.set_vote.assert_not_called()
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)
        test_app.dependency_overrides.pop(get_user_repo, None)


@pytest.mark.asyncio
async def test_set_paid_vote_insufficient_balance_returns_400(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, mock_user_repo, sample_user):
    """Paid vote with amount greater than balance returns 400."""
    mock_user_repo.get_by_id.return_value = {"id": 1, "accumulated_balance": 2.0}
    mock_domain_repo.get_by_id.return_value = {"id": 10, "user_id": 999}
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo
    test_app.dependency_overrides[get_user_repo] = lambda: mock_user_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=domain&target_id=10&value=1",
            json={"value": 1, "amount": 5},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "insufficient" in (body.get("error") or body.get("detail") or "").lower()
        mock_comment_repo.add_paid_votes.assert_not_called()
        mock_user_repo.update_balance.assert_not_called()
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)
        test_app.dependency_overrides.pop(get_user_repo, None)


@pytest.mark.asyncio
async def test_set_paid_vote_no_existing_vote_refunds_and_returns_400(client, test_app, auth_headers_comments, mock_comment_repo, mock_domain_repo, mock_user_repo, sample_user):
    """Paid vote when no vote row exists: add_paid_votes raises BadRequestError; balance is refunded."""
    from app.core.exceptions import BadRequestError as AppBadRequestError

    mock_domain_repo.get_by_id.return_value = {"id": 10, "user_id": 999}
    mock_comment_repo.add_paid_votes.side_effect = AppBadRequestError("No vote found; use free vote first")
    test_app.dependency_overrides[get_comment_repo] = lambda: mock_comment_repo
    test_app.dependency_overrides[get_domain_repo] = lambda: mock_domain_repo
    test_app.dependency_overrides[get_user_repo] = lambda: mock_user_repo

    try:
        resp = client.post(
            "/api/v1/votes?target_type=domain&target_id=10&value=1",
            json={"value": 1, "amount": 3},
            headers=auth_headers_comments,
        )
        assert resp.status_code == 400
        assert mock_user_repo.update_balance.call_count == 2
        calls = mock_user_repo.update_balance.call_args_list
        assert calls[0][0][1] == -3.0
        assert calls[1][0][1] == 3.0
    finally:
        test_app.dependency_overrides.pop(get_comment_repo, None)
        test_app.dependency_overrides.pop(get_domain_repo, None)
        test_app.dependency_overrides.pop(get_user_repo, None)
