from typing import Annotated, Optional

from pydantic import BaseModel, Field, field_validator

from db.enums import MarkerCategory, MarkerStatus, MarkerUrgency
from schemas.address import AddressCreate


class Marker(BaseModel):
    position: Annotated[list[float], Field(min_length=2, max_length=2)]
    description: str
    title: str
    urgency: MarkerUrgency = MarkerUrgency.LOW  # Use enum with default
    category: MarkerCategory = MarkerCategory.OTHER  # Use enum with default
    status: MarkerStatus = MarkerStatus.PENDING  # Default value
    address_id: Optional[int] = None  # Optional foreign key to address
    address: Optional[AddressCreate] = None  # Nested address object

    @field_validator("position")
    @classmethod
    def _valid_coords(cls, v: list[float]) -> list[float]:
        lat, lng = v
        if not -90 <= lat <= 90:
            raise ValueError(f"latitude {lat} outside [-90, 90]")
        if not -180 <= lng <= 180:
            raise ValueError(f"longitude {lng} outside [-180, 180]")
        return v

    @property
    def latitude(self) -> float:
        return self.position[0]

    @property
    def longitude(self) -> float:
        return self.position[1]
