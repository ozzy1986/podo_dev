"""
Integration tests for UserRepository against real PostgreSQL database.

Tests all 12 methods with real database operations.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from app.repositories.user_repo import UserRepository
from app.core.exceptions import NotFoundError, ConflictError


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_user_with_email(real_pg_db):
    """Test creating a user with email."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    email = f"test_create_email_{timestamp}@test.d.onl"
    
    try:
        user = await repo.create(email=email, language="en")
        assert user["email"] == email
        assert user["language"] == "en"
        assert user["accumulated_balance"] == 0.0
        assert user["payout_mode"] == "manual"
    finally:
        await real_pg_db.execute("DELETE FROM users WHERE email = $1", email)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_user_with_wallet(real_pg_db):
    """Test creating a user with wallet."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    wallet = f"3TestWallet{timestamp:010d}"
    
    try:
        user = await repo.create(wallet_address=wallet, language="ru")
        assert user["wallet"] == wallet
        assert user["language"] == "ru"
    finally:
        await real_pg_db.execute("DELETE FROM users WHERE wallet = $1", wallet)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_user_with_telegram_id(real_pg_db):
    """Test creating a user with Telegram ID."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    telegram_id = 1000000000 + timestamp
    
    try:
        user = await repo.create(telegram_id=telegram_id, username="test_user")
        assert user["telegram_id"] == telegram_id
        assert user["username"] == "test_user"
    finally:
        await real_pg_db.execute("DELETE FROM users WHERE telegram_id = $1", telegram_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_user_duplicate_email(real_pg_db):
    """Test that creating duplicate email raises ConflictError."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    email = f"test_duplicate_{timestamp}@test.d.onl"
    
    try:
        await repo.create(email=email)
        with pytest.raises(ConflictError, match="already exists"):
            await repo.create(email=email)
    finally:
        await real_pg_db.execute("DELETE FROM users WHERE email = $1", email)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_user_duplicate_wallet(real_pg_db):
    """Test that creating duplicate wallet raises ConflictError."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    wallet = f"3TestWallet{timestamp:010d}"
    
    try:
        await repo.create(wallet_address=wallet)
        with pytest.raises(ConflictError, match="already exists"):
            await repo.create(wallet_address=wallet)
    finally:
        await real_pg_db.execute("DELETE FROM users WHERE wallet = $1", wallet)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_id(real_pg_db, test_user):
    """Test getting user by ID."""
    repo = UserRepository(real_pg_db)
    user = await repo.get_by_id(test_user["id"])
    assert user is not None
    assert user["id"] == test_user["id"]
    assert user["email"] == test_user["email"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_id_not_found(real_pg_db):
    """Test getting non-existent user returns None."""
    repo = UserRepository(real_pg_db)
    user = await repo.get_by_id(999999999)
    assert user is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_wallet(real_pg_db, test_user):
    """Test getting user by wallet."""
    repo = UserRepository(real_pg_db)
    user = await repo.get_by_wallet(test_user["wallet"])
    assert user is not None
    assert user["wallet"] == test_user["wallet"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_email(real_pg_db, test_user):
    """Test getting user by email."""
    repo = UserRepository(real_pg_db)
    user = await repo.get_by_email(test_user["email"])
    assert user is not None
    assert user["email"] == test_user["email"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_telegram_id(real_pg_db):
    """Test getting user by Telegram ID."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    telegram_id = 1000000000 + timestamp
    
    try:
        created = await repo.create(telegram_id=telegram_id)
        user = await repo.get_by_telegram_id(telegram_id)
        assert user is not None
        assert user["telegram_id"] == telegram_id
    finally:
        await real_pg_db.execute("DELETE FROM users WHERE telegram_id = $1", telegram_id)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_wallet(real_pg_db, test_user):
    """Test updating user wallet."""
    repo = UserRepository(real_pg_db)
    new_wallet = f"3NewWallet{int(datetime.now().timestamp()):010d}"
    
    updated = await repo.update_wallet(test_user["id"], new_wallet)
    assert updated["wallet"] == new_wallet
    
    # Verify in DB
    user = await repo.get_by_id(test_user["id"])
    assert user["wallet"] == new_wallet


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_wallet_not_found(real_pg_db):
    """Test updating wallet for non-existent user raises NotFoundError."""
    repo = UserRepository(real_pg_db)
    with pytest.raises(NotFoundError):
        await repo.update_wallet(999999999, "3TestWallet1234567890")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_wallet_duplicate(real_pg_db, test_user):
    """Test updating wallet to one already in use raises ConflictError."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    other_wallet = f"3OtherWallet{timestamp:010d}"
    
    try:
        # Create another user
        other_user = await repo.create(wallet_address=other_wallet)
        
        # Try to update test_user to use other_user's wallet
        with pytest.raises(ConflictError, match="already in use"):
            await repo.update_wallet(test_user["id"], other_wallet)
    finally:
        await real_pg_db.execute("DELETE FROM users WHERE wallet = $1", other_wallet)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_balance(real_pg_db, test_user):
    """Test updating user balance."""
    repo = UserRepository(real_pg_db)
    
    # Add 100 tokens (100 * 10^8 units)
    updated = await repo.update_balance(test_user["id"], 100.0, 10000000000)
    assert updated["accumulated_balance"] == 100.0
    assert updated["accumulated_units"] == 10000000000
    
    # Add more
    updated = await repo.update_balance(test_user["id"], 50.0, 5000000000)
    assert updated["accumulated_balance"] == 150.0
    assert updated["accumulated_units"] == 15000000000
    
    # Subtract (withdrawal)
    updated = await repo.update_balance(test_user["id"], -25.0, -2500000000)
    assert updated["accumulated_balance"] == 125.0
    assert updated["accumulated_units"] == 12500000000


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_balance_not_found(real_pg_db):
    """Test updating balance for non-existent user raises NotFoundError."""
    repo = UserRepository(real_pg_db)
    with pytest.raises(NotFoundError):
        await repo.update_balance(999999999, 100.0, 10000000000)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_payout_settings(real_pg_db, test_user):
    """Test updating payout settings."""
    repo = UserRepository(real_pg_db)
    
    # Set to auto with threshold
    updated = await repo.update_payout_settings(test_user["id"], "auto", 100.0)
    assert updated["payout_mode"] == "auto"
    assert updated["payout_threshold"] == 100.0
    
    # Set to manual
    updated = await repo.update_payout_settings(test_user["id"], "manual", None)
    assert updated["payout_mode"] == "manual"
    assert updated["payout_threshold"] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_language(real_pg_db, test_user):
    """Test updating user language."""
    repo = UserRepository(real_pg_db)
    
    updated = await repo.update_language(test_user["id"], "ru")
    assert updated["language"] == "ru"
    
    updated = await repo.update_language(test_user["id"], "ar")
    assert updated["language"] == "ar"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_widget_preferences(real_pg_db, test_user):
    """Test updating widget preferences."""
    repo = UserRepository(real_pg_db)
    prefs_json = '{"enabled_widgets": ["earnings", "domains", "stats"]}'
    
    updated = await repo.update_widget_preferences(test_user["id"], prefs_json)
    assert updated["widget_preferences"] == prefs_json
    
    # Verify in DB
    user = await repo.get_by_id(test_user["id"])
    assert user["widget_preferences"] == prefs_json


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_users_for_auto_payout(real_pg_db):
    """Test getting users eligible for auto-payout."""
    repo = UserRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    
    # Create users with different payout settings
    user1_wallet = f"3AutoUser1{timestamp:010d}"
    user2_wallet = f"3AutoUser2{timestamp:010d}"
    user3_wallet = f"3ManualUser{timestamp:010d}"
    
    try:
        user1 = await repo.create(wallet_address=user1_wallet)
        user2 = await repo.create(wallet_address=user2_wallet)
        user3 = await repo.create(wallet_address=user3_wallet)
        
        # Set user1 and user2 to auto mode WITHOUT a custom threshold
        # (payout_threshold = NULL means the passed threshold is used via COALESCE)
        await repo.update_payout_settings(user1["id"], "auto", None)
        await repo.update_payout_settings(user2["id"], "auto", None)
        await repo.update_payout_settings(user3["id"], "manual", None)
        
        await repo.update_balance(user1["id"], 150.0, 15000000000)  # Above 100
        await repo.update_balance(user2["id"], 200.0, 20000000000)  # Above 100
        await repo.update_balance(user3["id"], 150.0, 15000000000)  # Manual mode
        
        # Get eligible users (threshold = 100.0)
        # user1: balance=150 >= COALESCE(NULL, 100) = 100 -> eligible
        # user2: balance=200 >= COALESCE(NULL, 100) = 100 -> eligible
        # user3: payout_mode='manual' -> excluded
        eligible = await repo.get_users_for_auto_payout(100.0)
        eligible_wallets = {u["wallet"] for u in eligible}
        
        assert user1_wallet in eligible_wallets
        assert user2_wallet in eligible_wallets
        assert user3_wallet not in eligible_wallets
        
        # Test with higher threshold (180.0)
        # user1: balance=150 >= COALESCE(NULL, 180) = 180? NO -> not eligible
        # user2: balance=200 >= COALESCE(NULL, 180) = 180? YES -> eligible
        eligible = await repo.get_users_for_auto_payout(180.0)
        eligible_wallets = {u["wallet"] for u in eligible}
        assert user1_wallet not in eligible_wallets  # 150 < 180
        assert user2_wallet in eligible_wallets  # 200 >= 180
        
    finally:
        await real_pg_db.execute(
            "DELETE FROM users WHERE wallet IN ($1, $2, $3)",
            user1_wallet, user2_wallet, user3_wallet
        )
