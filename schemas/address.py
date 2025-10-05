from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class AddressCreate(BaseModel):
    street: str
    city: str
    state: str
    postal_code: str = None
    country: str

class AddressUpdate(BaseModel):
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None

class Address(BaseModel):
    id: Optional[int] = None
    street: str
    city: str
    state: str
    postal_code: str = None
    country: str
    created_at: Optional[datetime] = None