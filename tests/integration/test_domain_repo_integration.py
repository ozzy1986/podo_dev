"""
Integration tests for DomainRepository against real PostgreSQL database.

Tests all 15 methods with real database operations.
"""

import pytest
import pytest_asyncio
from datetime import datetime
from app.repositories.domain_repo import DomainRepository
from app.core.exceptions import NotFoundError, ConflictError


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_domain(real_pg_db, test_user):
    """Test creating a domain."""
    repo = DomainRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    domain_name = f"test-create-{timestamp}.test.d.onl"
    nonce = f"test_nonce_{timestamp}"
    
    try:
        domain = await repo.create(
            user_id=test_user["id"],
            domain=domain_name,
            sld=f"test-create-{timestamp}",
            tld="onl",
            sld_length=len(f"test-create-{timestamp}"),
            nonce=nonce
        )
        assert domain["domain"] == domain_name
        assert domain["user_id"] == test_user["id"]
        assert domain["nonce"] == nonce
        assert domain["verified"] is False
        assert domain["is_mining"] is False
        assert domain["failed_checks"] == 0
    finally:
        await real_pg_db.execute("DELETE FROM domains WHERE domain = $1", domain_name)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_create_domain_duplicate(real_pg_db, test_user):
    """Test that creating duplicate domain raises ConflictError."""
    repo = DomainRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    domain_name = f"test-duplicate-{timestamp}.test.d.onl"
    nonce1 = f"nonce1_{timestamp}"
    nonce2 = f"nonce2_{timestamp}"
    
    try:
        await repo.create(
            user_id=test_user["id"],
            domain=domain_name,
            sld=f"test-duplicate-{timestamp}",
            tld="onl",
            sld_length=len(f"test-duplicate-{timestamp}"),
            nonce=nonce1
        )
        with pytest.raises(ConflictError, match="already exists"):
            await repo.create(
                user_id=test_user["id"],
                domain=domain_name,
                sld=f"test-duplicate-{timestamp}",
                tld="onl",
                sld_length=len(f"test-duplicate-{timestamp}"),
                nonce=nonce2
            )
    finally:
        await real_pg_db.execute("DELETE FROM domains WHERE domain = $1", domain_name)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_id(real_pg_db, test_domain):
    """Test getting domain by ID."""
    repo = DomainRepository(real_pg_db)
    domain = await repo.get_by_id(test_domain["id"])
    assert domain is not None
    assert domain["id"] == test_domain["id"]
    assert domain["domain"] == test_domain["domain"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_by_domain(real_pg_db, test_domain):
    """Test getting domain by name."""
    repo = DomainRepository(real_pg_db)
    domain = await repo.get_by_domain(test_domain["domain"])
    assert domain is not None
    assert domain["domain"] == test_domain["domain"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_user_domains(real_pg_db, test_user):
    """Test getting domains owned by user."""
    repo = DomainRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    
    domain1_name = f"test-user-domains-1-{timestamp}.test.d.onl"
    domain2_name = f"test-user-domains-2-{timestamp}.test.d.onl"
    
    try:
        domain1 = await repo.create(
            user_id=test_user["id"],
            domain=domain1_name,
            sld=f"test-user-domains-1-{timestamp}",
            tld="onl",
            sld_length=len(f"test-user-domains-1-{timestamp}"),
            nonce=f"nonce1_{timestamp}"
        )
        domain2 = await repo.create(
            user_id=test_user["id"],
            domain=domain2_name,
            sld=f"test-user-domains-2-{timestamp}",
            tld="onl",
            sld_length=len(f"test-user-domains-2-{timestamp}"),
            nonce=f"nonce2_{timestamp}"
        )
        
        domains = await repo.get_user_domains(test_user["id"], limit=10)
        domain_names = {d["domain"] for d in domains}
        assert domain1_name in domain_names
        assert domain2_name in domain_names
        
        # Test pagination
        domains_page1 = await repo.get_user_domains(test_user["id"], limit=1, offset=0)
        assert len(domains_page1) == 1
        
    finally:
        await real_pg_db.execute(
            "DELETE FROM domains WHERE domain IN ($1, $2)",
            domain1_name, domain2_name
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_count_user_domains(real_pg_db, test_user):
    """Test counting domains owned by user."""
    repo = DomainRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    
    domain1_name = f"test-count-1-{timestamp}.test.d.onl"
    domain2_name = f"test-count-2-{timestamp}.test.d.onl"
    
    try:
        initial_count = await repo.count_user_domains(test_user["id"])
        
        await repo.create(
            user_id=test_user["id"],
            domain=domain1_name,
            sld=f"test-count-1-{timestamp}",
            tld="onl",
            sld_length=len(f"test-count-1-{timestamp}"),
            nonce=f"nonce1_{timestamp}"
        )
        assert await repo.count_user_domains(test_user["id"]) == initial_count + 1
        
        await repo.create(
            user_id=test_user["id"],
            domain=domain2_name,
            sld=f"test-count-2-{timestamp}",
            tld="onl",
            sld_length=len(f"test-count-2-{timestamp}"),
            nonce=f"nonce2_{timestamp}"
        )
        assert await repo.count_user_domains(test_user["id"]) == initial_count + 2
        
    finally:
        await real_pg_db.execute(
            "DELETE FROM domains WHERE domain IN ($1, $2)",
            domain1_name, domain2_name
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_verify_domain(real_pg_db, test_domain):
    """Test verifying a domain."""
    repo = DomainRepository(real_pg_db)
    
    updated = await repo.verify_domain(test_domain["id"])
    assert updated["verified"] is True
    assert updated["verification_time"] is not None
    assert updated["failed_checks"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_start_mining(real_pg_db, test_domain):
    """Test starting mining for a domain."""
    repo = DomainRepository(real_pg_db)
    
    updated = await repo.start_mining(test_domain["id"])
    assert updated["is_mining"] is True
    assert updated["failed_checks"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_stop_mining(real_pg_db, test_domain):
    """Test stopping mining for a domain."""
    repo = DomainRepository(real_pg_db)
    
    # Start mining first
    await repo.start_mining(test_domain["id"])
    
    # Stop mining
    updated = await repo.stop_mining(test_domain["id"], reason="test")
    assert updated["is_mining"] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_check_status(real_pg_db, test_domain):
    """Test updating domain check status."""
    repo = DomainRepository(real_pg_db)
    
    updated = await repo.update_check_status(test_domain["id"], verified=True, failed_checks=0)
    assert updated["verified"] is True
    assert updated["failed_checks"] == 0
    assert updated["last_check"] is not None
    
    updated = await repo.update_check_status(test_domain["id"], verified=False, failed_checks=2)
    assert updated["verified"] is False
    assert updated["failed_checks"] == 2


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_a_record_status(real_pg_db, test_domain):
    """Test updating A-record status."""
    repo = DomainRepository(real_pg_db)
    
    updated = await repo.update_a_record_status(test_domain["id"], points_to_us=True)
    assert updated["a_record_points_to_us"] is True
    assert updated["updated_at"] is not None
    
    updated = await repo.update_a_record_status(test_domain["id"], points_to_us=False)
    assert updated["a_record_points_to_us"] is False


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_description(real_pg_db, test_domain):
    """Test updating domain description."""
    repo = DomainRepository(real_pg_db)
    
    description = "Test domain description"
    updated = await repo.update_description(test_domain["id"], description)
    assert updated["description"] == description
    
    # Clear description
    updated = await repo.update_description(test_domain["id"], None)
    assert updated["description"] is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_update_parking_content(real_pg_db, test_domain):
    """Test updating parking content."""
    repo = DomainRepository(real_pg_db)
    
    parking_html = "<html><body>Parking page</body></html>"
    updated = await repo.update_parking_content(
        test_domain["id"],
        parking_html,
        parking_mode="non_redirect"
    )
    assert updated["parking_content"] == parking_html
    assert updated["parking_mode"] == "non_redirect"
    
    # Change mode
    updated = await repo.update_parking_content(
        test_domain["id"],
        parking_html,
        parking_mode="redirect"
    )
    assert updated["parking_mode"] == "redirect"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_delete_domain(real_pg_db, test_user):
    """Test deleting a domain."""
    repo = DomainRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    domain_name = f"test-delete-{timestamp}.test.d.onl"
    
    domain = await repo.create(
        user_id=test_user["id"],
        domain=domain_name,
        sld=f"test-delete-{timestamp}",
        tld="onl",
        sld_length=len(f"test-delete-{timestamp}"),
        nonce=f"nonce_{timestamp}"
    )
    
    deleted = await repo.delete(domain["id"])
    assert deleted is True
    
    # Verify deleted
    domain_check = await repo.get_by_id(domain["id"])
    assert domain_check is None


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_mining_domains(real_pg_db, test_user):
    """Test getting all mining domains."""
    repo = DomainRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    
    domain1_name = f"test-mining-1-{timestamp}.test.d.onl"
    domain2_name = f"test-mining-2-{timestamp}.test.d.onl"
    
    try:
        domain1 = await repo.create(
            user_id=test_user["id"],
            domain=domain1_name,
            sld=f"test-mining-1-{timestamp}",
            tld="onl",
            sld_length=len(f"test-mining-1-{timestamp}"),
            nonce=f"nonce1_{timestamp}"
        )
        domain2 = await repo.create(
            user_id=test_user["id"],
            domain=domain2_name,
            sld=f"test-mining-2-{timestamp}",
            tld="onl",
            sld_length=len(f"test-mining-2-{timestamp}"),
            nonce=f"nonce2_{timestamp}"
        )
        
        # Start mining for both
        await repo.start_mining(domain1["id"])
        await repo.start_mining(domain2["id"])
        
        mining_domains = await repo.get_mining_domains(limit=100)
        mining_names = {d["domain"] for d in mining_domains}
        assert domain1_name in mining_names
        assert domain2_name in mining_names
        
        # Test with limit
        limited = await repo.get_mining_domains(limit=1)
        assert len(limited) == 1
        
    finally:
        await real_pg_db.execute(
            "DELETE FROM domains WHERE domain IN ($1, $2)",
            domain1_name, domain2_name
        )


@pytest.mark.asyncio
@pytest.mark.integration
async def test_get_domains_needing_check(real_pg_db, test_user):
    """Test getting domains needing check."""
    repo = DomainRepository(real_pg_db)
    timestamp = int(datetime.now().timestamp())
    
    domain_name = f"test-needs-check-{timestamp}.test.d.onl"
    
    try:
        domain = await repo.create(
            user_id=test_user["id"],
            domain=domain_name,
            sld=f"test-needs-check-{timestamp}",
            tld="onl",
            sld_length=len(f"test-needs-check-{timestamp}"),
            nonce=f"nonce_{timestamp}"
        )
        
        # Start mining (last_check is NULL initially)
        await repo.start_mining(domain["id"])
        
        # Should appear in domains needing check
        needing_check = await repo.get_domains_needing_check(hours_since_check=12)
        needing_names = {d["domain"] for d in needing_check}
        assert domain_name in needing_names
        
    finally:
        await real_pg_db.execute("DELETE FROM domains WHERE domain = $1", domain_name)


@pytest.mark.asyncio
@pytest.mark.integration
async def test_not_found_errors(real_pg_db):
    """Test NotFoundError for non-existent domain."""
    repo = DomainRepository(real_pg_db)
    fake_id = 999999999
    
    with pytest.raises(NotFoundError):
        await repo.verify_domain(fake_id)
    
    with pytest.raises(NotFoundError):
        await repo.start_mining(fake_id)
    
    with pytest.raises(NotFoundError):
        await repo.stop_mining(fake_id)
    
    with pytest.raises(NotFoundError):
        await repo.update_check_status(fake_id, True, 0)
    
    with pytest.raises(NotFoundError):
        await repo.update_a_record_status(fake_id, True)
    
    with pytest.raises(NotFoundError):
        await repo.update_description(fake_id, "test")
    
    with pytest.raises(NotFoundError):
        await repo.update_parking_content(fake_id, "test", "redirect")
