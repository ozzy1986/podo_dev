"""
Tests for wallet/domain wall API endpoints and repository helpers.
"""

import pytest

from app.api.deps import get_current_user_optional, get_wall_post_repo
from app.core.exceptions import BadRequestError
from app.repositories.wall_post_repo import WallPostRepository


def test_wall_post_sanitize_body_removes_disallowed_tags():
    raw = '<p>Hello <strong>World</strong><script>alert(1);</script><img src="https://example.com/img.png"></p>'
    normalized, cleaned = WallPostRepository.sanitize_body(raw)
    assert normalized.strip().startswith("<p>Hello")
    assert "<script" not in cleaned
    assert '<img src="https://example.com/img.png"' in cleaned


def test_wall_post_sanitize_body_rejects_empty():
    with pytest.raises(BadRequestError):
        WallPostRepository.sanitize_body("   ")


def test_list_wall_posts_hides_negative_karma(client, mock_wall_post_repo):
    mock_wall_post_repo.count_posts.return_value = 1
    mock_wall_post_repo.list_posts.return_value = [
        {
            "id": 7,
            "author_id": 2,
            "author_wallet": "3N7KTest",
            "entity_type": "domain",
            "entity_id": 10,
            "entity_key": None,
            "raw_body": "<p>Raw</p>",
            "body_html": "<p>Raw</p>",
            "content_theme": "light",
            "karma_score": -3,
            "created_at": "2025-01-02T00:00:00",
            "updated_at": None,
            "user_vote": None,
            "comments_count": 4,
        }
    ]

    client.app.dependency_overrides[get_wall_post_repo] = lambda: mock_wall_post_repo
    client.app.dependency_overrides[get_current_user_optional] = lambda: None

    try:
        resp = client.get("/api/v1/wall/posts?entity_type=domain&entity_id=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["total_pages"] == 1
        assert len(data["posts"]) == 1
        post = data["posts"][0]
        assert post["is_hidden"] is True
        assert post["body_html"] is None
        assert post["raw_body"] is None
        assert post["comments_count"] == 4
    finally:
        client.app.dependency_overrides.pop(get_wall_post_repo, None)
        client.app.dependency_overrides.pop(get_current_user_optional, None)


def test_delete_wall_post_forbidden_for_other_author(
    client,
    auth_headers,
    mock_wall_post_repo,
):
    mock_wall_post_repo.delete_post.return_value = False
    mock_wall_post_repo.get_post.return_value = {
        "id": 9,
        "author_id": 999,
        "author_wallet": "3N7KOther",
        "entity_type": "domain",
        "entity_id": 10,
        "entity_key": None,
        "raw_body": "<p>Raw</p>",
        "body_html": "<p>Raw</p>",
        "content_theme": "light",
        "karma_score": 5,
        "created_at": "2025-01-02T00:00:00",
        "updated_at": None,
        "user_vote": None,
        "comments_count": 0,
    }

    client.app.dependency_overrides[get_wall_post_repo] = lambda: mock_wall_post_repo

    try:
        resp = client.delete("/api/v1/wall/posts/9", headers=auth_headers)
        assert resp.status_code == 403
        error_detail = resp.json().get("error", "")
        assert "wall post" in error_detail.lower()
    finally:
        client.app.dependency_overrides.pop(get_wall_post_repo, None)


def test_delete_wall_post_not_found(
    client,
    auth_headers,
    mock_wall_post_repo,
):
    mock_wall_post_repo.delete_post.return_value = False
    mock_wall_post_repo.get_post.return_value = None

    client.app.dependency_overrides[get_wall_post_repo] = lambda: mock_wall_post_repo

    try:
        resp = client.delete("/api/v1/wall/posts/42", headers=auth_headers)
        assert resp.status_code == 404
        assert resp.json().get("error") == "Wall post not found"
    finally:
        client.app.dependency_overrides.pop(get_wall_post_repo, None)
