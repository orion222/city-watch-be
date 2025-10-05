from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from db.db import get_session
from db.models import Marker, Address
from schemas.marker import Marker as MarkerSchema
import datetime

router = APIRouter()

@router.get("/marker")
def get_markers(session: Session = Depends(get_session)):

    statement = select(Marker).options(selectinload(Marker.address)).order_by(Marker.timestamp.desc())
    markers = session.exec(statement).all()
    # Load address relationships
    markers_data = []
    for marker in markers:
        marker_dict = marker.model_dump()
        if marker.address:
            marker_dict["address"] = marker.address.model_dump()
        markers_data.append(marker_dict)
    
    return {"markers": markers_data}

@router.get("/marker/{marker_id}")
def get_marker(marker_id: int, session: Session = Depends(get_session)):
    # Use selectinload to eagerly load the address relationship
    statement = select(Marker).options(selectinload(Marker.address)).where(Marker.id == marker_id)
    marker = session.exec(statement).first()
    
    if not marker:
        return {"message": f"Marker {marker_id} not found"}
    
    # Convert to dict format for proper serialization
    marker_dict = marker.model_dump()
    if marker.address:
        marker_dict["address"] = marker.address.model_dump()
    
    return {"marker": marker_dict}

@router.post("/marker")
def create_marker(marker: MarkerSchema, session: Session = Depends(get_session)):
    # Create address first if provided
    address_id = None
    if marker.address:
        new_address = Address(
            street=marker.address.street,
            city=marker.address.city,
            state=marker.address.state,
            postal_code=marker.address.postal_code,
            country=marker.address.country,
        )
        session.add(new_address)
        session.commit()
        session.refresh(new_address)
        address_id = new_address.id
    elif marker.address_id:
        address_id = marker.address_id
    
    # Create marker with address relationship
    new_marker = Marker(
        position=marker.position,
        description=marker.description,
        title=marker.title,
        urgency=marker.urgency,
        category=marker.category,
        status=marker.status,
        address_id=address_id
    )
    session.add(new_marker)
    session.commit()
    session.refresh(new_marker)
    return {"message": f"Marker created successfully", "marker": new_marker}

@router.put("/marker/{marker_id}")
def update_marker(marker_id: int, marker: MarkerSchema, session: Session = Depends(get_session)):
    existing_marker = session.get(Marker, marker_id)
    if not existing_marker:
        return {"message": f"Marker {marker_id} not found"}
    
    # Handle address update/creation
    address_id = existing_marker.address_id
    if marker.address:
        if existing_marker.address_id:
            # Update existing address
            existing_address = session.get(Address, existing_marker.address_id)
            if existing_address:
                existing_address.street = marker.address.street
                existing_address.city = marker.address.city
                existing_address.state = marker.address.state
                existing_address.postal_code = marker.address.postal_code
                existing_address.country = marker.address.country
                session.add(existing_address)
        else:
            # Create new address
            new_address = Address(
                street=marker.address.street,
                city=marker.address.city,
                state=marker.address.state,
                postal_code=marker.address.postal_code,
                country=marker.address.country,
            )
            session.add(new_address)
            session.commit()
            session.refresh(new_address)
            address_id = new_address.id
    elif marker.address_id:
        address_id = marker.address_id
    
    # Update marker fields (excluding address object)
    marker_data = marker.model_dump(exclude={"address"})
    marker_data["address_id"] = address_id
    
    for key, value in marker_data.items():
        if hasattr(existing_marker, key):
            setattr(existing_marker, key, value)
    
    session.add(existing_marker)
    session.commit()
    session.refresh(existing_marker)
    
    # Load the updated address for response
    if existing_marker.address_id:
        existing_marker.address = session.get(Address, existing_marker.address_id)
    
    return {"message": f"Marker {marker_id} updated", "marker": existing_marker}