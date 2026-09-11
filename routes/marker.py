from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from db.db import get_session
from db.models import Address, Marker
from schemas.marker import Marker as MarkerSchema
from utils.rate_limit import limiter

router = APIRouter()


def _serialize(marker: Marker) -> dict:
    data = marker.model_dump(exclude={"latitude", "longitude"})
    data["position"] = [marker.latitude, marker.longitude]
    if marker.address:
        data["address"] = marker.address.model_dump()
    return data


@router.get("/marker")
@limiter.limit("60/minute")
def get_markers(request: Request, session: Session = Depends(get_session)):

    statement = select(Marker).options(selectinload(Marker.address)).order_by(Marker.timestamp.desc())
    markers = session.exec(statement).all()
    markers_data = [_serialize(marker) for marker in markers]

    return {"markers": markers_data}


@router.get("/marker/{marker_id}")
@limiter.limit("60/minute")
def get_marker(request: Request, marker_id: int, session: Session = Depends(get_session)):
    # Use selectinload to eagerly load the address relationship
    statement = select(Marker).options(selectinload(Marker.address)).where(Marker.id == marker_id)
    marker = session.exec(statement).first()

    if not marker:
        raise HTTPException(status_code=404, detail=f"Marker {marker_id} not found")

    return {"marker": _serialize(marker)}


@router.post("/marker")
@limiter.limit("20/minute")
def create_marker(
    request: Request,
    marker: MarkerSchema,
    session: Session = Depends(get_session),
):
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
        session.flush()
        address_id = new_address.id
    elif marker.address_id:
        if not session.get(Address, marker.address_id):
            raise HTTPException(status_code=404, detail=f"Address {marker.address_id} not found")
        address_id = marker.address_id

    # Create marker with address relationship
    new_marker = Marker(
        latitude=marker.latitude,
        longitude=marker.longitude,
        description=marker.description,
        title=marker.title,
        urgency=marker.urgency,
        category=marker.category,
        status=marker.status,
        address_id=address_id,
        image_url=marker.image_url,
    )
    session.add(new_marker)
    session.commit()
    session.refresh(new_marker)
    return {
        "message": "Marker created successfully",
        "marker": _serialize(new_marker),
    }


@router.put("/marker/{marker_id}")
@limiter.limit("20/minute")
def update_marker(
    request: Request,
    marker_id: int,
    marker: MarkerSchema,
    session: Session = Depends(get_session),
):
    existing_marker = session.get(Marker, marker_id)
    if not existing_marker:
        raise HTTPException(status_code=404, detail=f"Marker {marker_id} not found")

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
            session.flush()
            address_id = new_address.id
    elif marker.address_id:
        if not session.get(Address, marker.address_id):
            raise HTTPException(status_code=404, detail=f"Address {marker.address_id} not found")
        address_id = marker.address_id

    # Update marker fields (excluding address object and wire-only position)
    marker_data = marker.model_dump(exclude={"address", "position"})
    marker_data["address_id"] = address_id

    if marker.image_url is None:
        marker_data["image_url"] = existing_marker.image_url

    for key, value in marker_data.items():
        if hasattr(existing_marker, key):
            setattr(existing_marker, key, value)

    existing_marker.latitude = marker.latitude
    existing_marker.longitude = marker.longitude

    session.add(existing_marker)
    session.commit()
    session.refresh(existing_marker)

    # Load the updated address for response
    if existing_marker.address_id:
        existing_marker.address = session.get(Address, existing_marker.address_id)

    return {
        "message": f"Marker {marker_id} updated",
        "marker": _serialize(existing_marker),
    }
