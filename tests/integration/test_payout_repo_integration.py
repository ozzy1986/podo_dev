"""
Integration tests for PayoutRepository against real PostgreSQL database.

Tests all 6 methods with real database operations.
"""

import pytest
import pytest_asyncio
from app.repositories.payout_repo import PayoutRepository
from app.core.exceptions import NotFoundError


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_request(real_pg_db, test_user):
    """Test creating a payout request."""
    repo = PayoutRepository(real_pg_db)
    
    payout = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=100.0,
        amount_units=10000000000,
        triggered_by="manual"
    )
    
    assert payout["user_id"] == test_user["id"]
    assert payout["wallet"] == test_user["wallet"]
    assert payout["amount"] == 100.0
    assert payout["status"] == "pending"
    assert payout["triggered_by"] == "manual"
    
    # Cleanup
    await real_pg_db.execute("DELETE FROM payout_requests WHERE id = $1", payout["id"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_id(real_pg_db, test_user):
    """Test getting payout request by ID."""
    repo = PayoutRepository(real_pg_db)
    
    payout = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=50.0,
        amount_units=5000000000,
        triggered_by="auto_threshold"
    )
    
    try:
        found = await repo.get_by_id(payout["id"])
        assert found is not None
        assert found["id"] == payout["id"]
        assert found["amount"] == 50.0
        assert found["triggered_by"] == "auto_threshold"
    finally:
        await real_pg_db.execute("DELETE FROM payout_requests WHERE id = $1", payout["id"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_pending_requests(real_pg_db, test_user):
    """Test getting pending payout requests."""
    repo = PayoutRepository(real_pg_db)
    
    payout1 = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=25.0,
        amount_units=2500000000
    )
    payout2 = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=75.0,
        amount_units=7500000000
    )
    
    try:
        pending = await repo.get_pending_requests(limit=10)
        pending_ids = {p["id"] for p in pending}
        assert payout1["id"] in pending_ids
        assert payout2["id"] in pending_ids
        
        # Test limit
        limited = await repo.get_pending_requests(limit=1)
        assert len(limited) <= 1
        
    finally:
        await real_pg_db.execute(
            "DELETE FROM payout_requests WHERE id IN ($1, $2)",
            payout1["id"], payout2["id"]
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_status(real_pg_db, test_user):
    """Test updating payout request status."""
    repo = PayoutRepository(real_pg_db)
    
    payout = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=200.0,
        amount_units=20000000000
    )
    
    try:
        # Update to processing
        updated = await repo.update_status(payout["id"], "processing")
        assert updated["status"] == "processing"
        assert updated["processed_at"] is None
        
        # Update to completed
        tx_id = "3PTestTx1234567890"
        updated = await repo.update_status(payout["id"], "completed", tx_id=tx_id)
        assert updated["status"] == "completed"
        assert updated["tx_id"] == tx_id
        assert updated["processed_at"] is not None
        
    finally:
        await real_pg_db.execute("DELETE FROM payout_requests WHERE id = $1", payout["id"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_status_failed(real_pg_db, test_user):
    """Test updating payout status to failed."""
    repo = PayoutRepository(real_pg_db)
    
    payout = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=150.0,
        amount_units=15000000000
    )
    
    try:
        error_msg = "Insufficient balance"
        updated = await repo.update_status(payout["id"], "failed", error_message=error_msg)
        assert updated["status"] == "failed"
        assert updated["error_message"] == error_msg
        assert updated["processed_at"] is not None
        
    finally:
        await real_pg_db.execute("DELETE FROM payout_requests WHERE id = $1", payout["id"])


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_status_not_found(real_pg_db):
    """Test updating non-existent payout raises NotFoundError."""
    repo = PayoutRepository(real_pg_db)
    
    with pytest.raises(NotFoundError):
        await repo.update_status(999999999, "completed")


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_payout_history(real_pg_db, test_user):
    """Test getting user payout history."""
    repo = PayoutRepository(real_pg_db)
    
    payout1 = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=10.0,
        amount_units=1000000000
    )
    payout2 = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=20.0,
        amount_units=2000000000
    )
    
    try:
        history = await repo.get_user_payout_history(test_user["id"], limit=10)
        history_ids = {p["id"] for p in history}
        assert payout1["id"] in history_ids
        assert payout2["id"] in history_ids
        
        # Test pagination
        page1 = await repo.get_user_payout_history(test_user["id"], limit=1, offset=0)
        assert len(page1) == 1
        
    finally:
        await real_pg_db.execute(
            "DELETE FROM payout_requests WHERE id IN ($1, $2)",
            payout1["id"], payout2["id"]
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_total_paid_out(real_pg_db, test_user):
    """Test getting total paid out amount."""
    repo = PayoutRepository(real_pg_db)
    
    payout1 = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=30.0,
        amount_units=3000000000
    )
    payout2 = await repo.create_request(
        user_id=test_user["id"],
        wallet=test_user["wallet"],
        amount=40.0,
        amount_units=4000000000
    )
    
    try:
        # Complete both payouts
        await repo.update_status(payout1["id"], "completed", tx_id="tx1")
        await repo.update_status(payout2["id"], "completed", tx_id="tx2")
        
        # Get total for user
        user_total = await repo.get_total_paid_out(test_user["id"])
        assert user_total == 70.0  # 30 + 40
        
        # Get system total
        system_total = await repo.get_total_paid_out()
        assert system_total >= 70.0
        
    finally:
        await real_pg_db.execute(
            "DELETE FROM payout_requests WHERE id IN ($1, $2)",
            payout1["id"], payout2["id"]
        )
