"""
Domain management API routes.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.api.deps import (
    get_domain_service,
    get_dns_service,
    get_current_user
)
from app.services.domain_service import DomainService
from app.services.dns_service import DNSService
from app.models.domain import (
    AddDomainRequest,
    UpdateDescriptionRequest,
    UpdateParkingRequest,
    DomainResponse,
    VerificationInfoResponse
)
from app.models.common import PaginationParams
from app.core.exceptions import (
    NotFoundError,
    ValidationError,
    ConflictError,
    PermissionError as AppPermissionError
)

router = APIRouter(prefix="/domains", tags=["Domains"])


@router.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def add_domain(
    request: AddDomainRequest,
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service)
):
    """
    Add a new domain for mining.
    
    - **domain**: Domain name (e.g., example.com)
    
    Requires authentication.
    """
    try:
        domain = await domain_service.add_domain(
            user_id=current_user['id'],
            domain=request.domain
        )
        
        return DomainResponse(**domain)
    
    except (ValidationError, ConflictError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("", response_model=List[DomainResponse])
async def get_user_domains(
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100)
):
    """
    Get all domains owned by current user.
    
    Supports pagination with `page` and `per_page` query parameters.
    
    Requires authentication.
    """
    pagination = PaginationParams(page=page, per_page=per_page)
    
    domains = await domain_service.get_user_domains(
        user_id=current_user['id'],
        limit=pagination.limit,
        offset=pagination.offset
    )
    
    return [DomainResponse(**d) for d in domains]


@router.get("/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: int,
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service)
):
    """
    Get domain by ID.
    
    Requires authentication and domain ownership.
    """
    try:
        domain = await domain_service.get_domain(domain_id, current_user['id'])
        return DomainResponse(**domain)
    
    except (NotFoundError, AppPermissionError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: int,
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service)
):
    """
    Delete a domain.
    
    Requires authentication and domain ownership.
    """
    try:
        await domain_service.delete_domain(domain_id, current_user['id'])
    
    except (NotFoundError, AppPermissionError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{domain_id}/verification", response_model=VerificationInfoResponse)
async def get_verification_info(
    domain_id: int,
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service)
):
    """
    Get DNS TXT record verification information for a domain.
    
    Returns the TXT record value that needs to be added to DNS.
    
    Requires authentication and domain ownership.
    """
    try:
        # Check ownership
        domain = await domain_service.get_domain(domain_id, current_user['id'])
        
        # Get TXT record value
        txt_record = await domain_service.get_verification_txt_record(domain_id)
        
        return VerificationInfoResponse(
            domain=domain['domain'],
            txt_record=txt_record,
            instructions=(
                f"Add a TXT record to your domain's DNS with the value: {txt_record}\n"
                f"You can add it to either _mining.{domain['domain']} or {domain['domain']}"
            )
        )
    
    except (NotFoundError, AppPermissionError, ValidationError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/{domain_id}/verify", response_model=DomainResponse)
async def verify_domain(
    domain_id: int,
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service),
    dns_service: DNSService = Depends(get_dns_service)
):
    """
    Verify domain ownership via DNS TXT record.
    
    Checks if the required TXT record is present in DNS.
    
    Requires authentication and domain ownership.
    """
    try:
        # Check ownership
        domain = await domain_service.get_domain(domain_id, current_user['id'])
        
        # Get expected TXT record
        txt_record = await domain_service.get_verification_txt_record(domain_id)
        
        # Verify DNS TXT record
        verified = await dns_service.verify_txt_record(domain['domain'], txt_record)
        
        if not verified:
            raise ValidationError(
                "TXT record not found. Please add the TXT record to your DNS and try again."
            )
        
        # Update domain verified status in database
        updated_domain = await domain_service.verify_domain(domain_id, current_user['id'])
        return DomainResponse(**updated_domain)
    
    except (NotFoundError, AppPermissionError, ValidationError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/{domain_id}/description", response_model=DomainResponse)
async def update_description(
    domain_id: int,
    request: UpdateDescriptionRequest,
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service)
):
    """
    Update domain description.
    
    Requires authentication and domain ownership.
    """
    try:
        domain = await domain_service.update_description(
            domain_id,
            current_user['id'],
            request.description
        )
        
        return DomainResponse(**domain)
    
    except (NotFoundError, AppPermissionError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.put("/{domain_id}/parking", response_model=DomainResponse)
async def update_parking(
    domain_id: int,
    request: UpdateParkingRequest,
    current_user: dict = Depends(get_current_user),
    domain_service: DomainService = Depends(get_domain_service)
):
    """
    Update domain parking content and mode.
    
    - **parking_content**: HTML content for parking page
    - **parking_mode**: 'redirect' (302 to d.onl) or 'non_redirect' (serve custom content)
    
    Requires authentication and domain ownership.
    """
    try:
        domain = await domain_service.update_parking_content(
            domain_id,
            current_user['id'],
            request.parking_content,
            request.parking_mode
        )
        
        return DomainResponse(**domain)
    
    except (NotFoundError, AppPermissionError, ValidationError) as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
