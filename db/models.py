from datetime import datetime
from typing import List
import sqlalchemy as sa
from sqlmodel import Field, SQLModel, Relationship
from db.enums import MarkerCategory, MarkerUrgency, MarkerStatus


def enum_column(enum_cls, **kw) -> sa.Column:
    """VARCHAR storing the enum's value, coerced back to the member on read."""
    return sa.Column(
        sa.Enum(
            enum_cls,
            native_enum=False,
            create_constraint=False,
            length=32,
            values_callable=lambda e: [m.value for m in e],
        ),
        **kw,
    )


class Address(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    street: str
    city: str
    state: str
    postal_code: str | None = Field(default=None)
    country: str
    created_at: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        )
    )
    markers: List["Marker"] = Relationship(back_populates="address")

class Marker(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    latitude: float = Field(sa_column=sa.Column(sa.Float, nullable=False))
    longitude: float = Field(sa_column=sa.Column(sa.Float, nullable=False))

    description: str
    title: str

    urgency: MarkerUrgency = Field(
        default=MarkerUrgency.LOW,
        sa_column=enum_column(MarkerUrgency, nullable=False),
    )
    category: MarkerCategory = Field(
        default=MarkerCategory.OTHER,
        sa_column=enum_column(MarkerCategory, nullable=False),
    )
    status: MarkerStatus = Field(
        default=MarkerStatus.PENDING,
        sa_column=enum_column(MarkerStatus, nullable=False),
    )

    timestamp: datetime = Field(
        sa_column=sa.Column(
            sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        )
    )

    address_id: int | None = Field(default=None, foreign_key="address.id")
    address: Address | None = Relationship(back_populates="markers")

    __table_args__ = (sa.Index("ix_marker_lat_lng", "latitude", "longitude"),)
