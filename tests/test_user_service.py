"""
Unit tests for UserService with mocked repositories.
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock
from app.services.user_service import UserService
from app.core.exceptions import NotFoundError, ValidationError


@pytest.fixture
def mock_user_repo():
    """Mock UserRepository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_domain_repo():
    """Mock DomainRepository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def user_service(mock_user_repo, mock_domain_repo):
    """Create UserService with mocked repos."""
    return UserService(mock_user_repo, mock_domain_repo)


@pytest.mark.asyncio
async def test_get_user_success(user_service, mock_user_repo, sample_user):
    """Test getting user successfully."""
    mock_user_repo.get_by_id.return_value = sample_user
    
    result = await user_service.get_user(1)
    
    assert result == sample_user
    mock_user_repo.get_by_id.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_get_user_not_found(user_service, mock_user_repo):
    """Test getting non-existent user raises NotFoundError."""
    mock_user_repo.get_by_id.return_value = None
    
    with pytest.raises(NotFoundError, match="not found"):
        await user_service.get_user(999)


@pytest.mark.asyncio
async def test_update_wallet_valid(user_service, mock_user_repo, sample_user):
    """Test updating wallet with valid address."""
    updated_user = {**sample_user, "wallet": "3NewWallet1234567890"}
    mock_user_repo.update_wallet.return_value = updated_user
    
    result = await user_service.update_wallet(1, "3NewWallet1234567890")
    
    assert result == updated_user
    mock_user_repo.update_wallet.assert_called_once_with(1, "3NewWallet1234567890")


@pytest.mark.asyncio
async def test_update_wallet_invalid_no_prefix(user_service):
    """Test updating wallet without '3' prefix raises ValidationError."""
    with pytest.raises(ValidationError, match="Invalid Waves wallet"):
        await user_service.update_wallet(1, "InvalidWallet123")


@pytest.mark.asyncio
async def test_update_wallet_invalid_empty(user_service):
    """Test updating wallet with empty string raises ValidationError."""
    with pytest.raises(ValidationError, match="Invalid Waves wallet"):
        await user_service.update_wallet(1, "")


@pytest.mark.asyncio
async def test_update_language_valid(user_service, mock_user_repo, sample_user):
    """Test updating language with valid codes."""
    for lang in ["en", "ru", "ar"]:
        updated_user = {**sample_user, "language": lang}
        mock_user_repo.update_language.return_value = updated_user
        
        result = await user_service.update_language(1, lang)
        assert result["language"] == lang


@pytest.mark.asyncio
async def test_update_language_invalid(user_service):
    """Test updating language with invalid code raises ValidationError."""
    with pytest.raises(ValidationError, match="Invalid language"):
        await user_service.update_language(1, "invalid")


@pytest.mark.asyncio
async def test_get_balance(user_service, mock_user_repo, sample_user):
    """Test getting user balance."""
    sample_user["accumulated_balance"] = 150.0
    sample_user["accumulated_units"] = 15000000000
    sample_user["payout_mode"] = "auto"
    sample_user["payout_threshold"] = 100.0
    
    mock_user_repo.get_by_id.return_value = sample_user
    
    result = await user_service.get_balance(1)
    
    assert result["balance"] == 150.0
    assert result["balance_units"] == 15000000000
    assert result["payout_mode"] == "auto"
    assert result["payout_threshold"] == 100.0


@pytest.mark.asyncio
async def test_update_payout_settings_manual(user_service, mock_user_repo, sample_user):
    """Test updating payout settings to manual."""
    updated_user = {**sample_user, "payout_mode": "manual", "payout_threshold": None}
    mock_user_repo.update_payout_settings.return_value = updated_user
    
    result = await user_service.update_payout_settings(1, "manual")
    
    assert result["payout_mode"] == "manual"
    mock_user_repo.update_payout_settings.assert_called_once_with(1, "manual", None)


@pytest.mark.asyncio
async def test_update_payout_settings_auto_with_threshold(user_service, mock_user_repo, sample_user):
    """Test updating payout settings to auto with valid threshold."""
    updated_user = {**sample_user, "payout_mode": "auto", "payout_threshold": 100.0}
    mock_user_repo.update_payout_settings.return_value = updated_user
    
    result = await user_service.update_payout_settings(1, "auto", 100.0)
    
    assert result["payout_mode"] == "auto"
    assert result["payout_threshold"] == 100.0


@pytest.mark.asyncio
async def test_update_payout_settings_auto_no_threshold(user_service):
    """Test updating to auto without threshold raises ValidationError."""
    with pytest.raises(ValidationError, match="threshold must be at least 100"):
        await user_service.update_payout_settings(1, "auto", None)


@pytest.mark.asyncio
async def test_update_payout_settings_auto_threshold_too_low(user_service):
    """Test updating to auto with threshold < 100 raises ValidationError."""
    with pytest.raises(ValidationError, match="threshold must be at least 100"):
        await user_service.update_payout_settings(1, "auto", 50.0)


@pytest.mark.asyncio
async def test_update_payout_settings_invalid_mode(user_service):
    """Test updating with invalid payout mode raises ValidationError."""
    with pytest.raises(ValidationError, match="must be 'manual' or 'auto'"):
        await user_service.update_payout_settings(1, "invalid_mode")


@pytest.mark.asyncio
async def test_update_widget_preferences_valid(user_service, mock_user_repo):
    """Test updating widget preferences with valid list."""
    enabled_widgets = ["earnings", "domains", "stats"]
    
    result = await user_service.update_widget_preferences(1, enabled_widgets)
    
    assert result == {"enabled_widgets": enabled_widgets}
    mock_user_repo.update_widget_preferences.assert_called_once()
    call_args = mock_user_repo.update_widget_preferences.call_args
    assert call_args[0][0] == 1
    assert "enabled_widgets" in call_args[0][1]


@pytest.mark.asyncio
async def test_update_widget_preferences_invalid_type(user_service):
    """Test updating widget preferences with non-list raises ValidationError."""
    with pytest.raises(ValidationError, match="must be a list"):
        await user_service.update_widget_preferences(1, "not_a_list")


@pytest.mark.asyncio
async def test_update_widget_preferences_non_string_ids(user_service):
    """Test updating widget preferences with non-string IDs raises ValidationError."""
    with pytest.raises(ValidationError, match="must be a string"):
        await user_service.update_widget_preferences(1, [1, 2, 3])


@pytest.mark.asyncio
async def test_get_user_stats(user_service, mock_user_repo, mock_domain_repo, sample_user):
    """Test getting user statistics."""
    sample_user["accumulated_balance"] = 200.0
    sample_user["wallet"] = "3TestWallet1234567890"
    sample_user["created_at"] = "2025-01-01T00:00:00"
    
    mock_user_repo.get_by_id.return_value = sample_user
    mock_domain_repo.count_user_domains.return_value = 5
    mock_domain_repo.get_user_domains.return_value = [
        {"is_mining": True},
        {"is_mining": True},
        {"is_mining": False},
    ]
    
    result = await user_service.get_user_stats(1)
    
    assert result["total_domains"] == 5
    assert result["mining_domains"] == 2
    assert result["accumulated_balance"] == 200.0
    assert result["wallet"] == "3TestWallet1234567890"
    assert result["member_since"] == "2025-01-01T00:00:00"
