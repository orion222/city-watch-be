from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from db.db import get_session
from db.models import Address
from schemas.address import AddressCreate, AddressUpdate
from utils.rate_limit import limiter

router = APIRouter()

@router.get("/address")
@limiter.limit("60/minute")
def get_addresses(
    request: Request,
    session: Session = Depends(get_session)
):
    """Get all addresses"""
    addresses = session.exec(select(Address)).all()
    return {"addresses": addresses}

@router.get("/address/{address_id}")
@limiter.limit("60/minute")
def get_address(
    request: Request,
    address_id: int,
    session: Session = Depends(get_session)
):
    """Get a specific address by ID"""
    address = session.get(Address, address_id)
    if not address:
        raise HTTPException(status_code=404, detail=f"Address {address_id} not found")
    return {"address": address}

@router.post("/address")
@limiter.limit("20/minute")
def create_address(
    request: Request,
    address: AddressCreate,
    session: Session = Depends(get_session)
):
    """Create a new address"""
    new_address = Address(
        street=address.street,
        city=address.city,
        state=address.state,
        postal_code=address.postal_code,
        country=address.country
    )
    session.add(new_address)
    session.commit()
    session.refresh(new_address)
    return {"message": "Address created successfully", "address": new_address}

@router.put("/address/{address_id}")
@limiter.limit("20/minute")
def update_address(
    request: Request,
    address_id: int, 
    address: AddressUpdate, 
    session: Session = Depends(get_session)
):
    """Update an existing address"""
    existing_address = session.get(Address, address_id)
    if not existing_address:
        raise HTTPException(status_code=404, detail=f"Address {address_id} not found")
    
    # Update only provided fields
    address_data = address.model_dump(exclude_unset=True)
    for key, value in address_data.items():
        if hasattr(existing_address, key):
            setattr(existing_address, key, value)
    
    session.add(existing_address)
    session.commit()
    session.refresh(existing_address)
    return {"message": f"Address {address_id} updated", "address": existing_address}

@router.delete("/address/{address_id}")
@limiter.limit("20/minute")
def delete_address(
    request: Request,
    address_id: int, 
    session: Session = Depends(get_session)
):
    """Delete an address"""
    address = session.get(Address, address_id)
    if not address:
        raise HTTPException(status_code=404, detail=f"Address {address_id} not found")
    
    session.delete(address)
    session.commit()
    return {"message": f"Address {address_id} deleted successfully"}