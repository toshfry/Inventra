from pydantic import BaseModel, Field
from typing import Optional

class SupplierCreate(BaseModel):
    name:         str = Field(..., min_length=1)
    contact_name: Optional[str] = None
    phone:        Optional[str] = None
    email:        Optional[str] = None
    address:      Optional[str] = None
    notes:        Optional[str] = None

class SupplierUpdate(BaseModel):
    name:         Optional[str] = None
    contact_name: Optional[str] = None
    phone:        Optional[str] = None
    email:        Optional[str] = None
    address:      Optional[str] = None
    notes:        Optional[str] = None
