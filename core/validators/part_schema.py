from pydantic import BaseModel, Field, field_validator
from typing import Optional

class PartCreate(BaseModel):
    name:          str   = Field(..., min_length=1)
    description:   Optional[str] = None
    category_id:   Optional[int] = None
    unit_cost:     float = Field(0.0, ge=0)
    selling_price: float = Field(0.0, ge=0)
    unit:          str   = "pcs"
    min_stock:     int   = Field(5, ge=0)
    bin_location:  Optional[str] = None
    vehicle_makes: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        if not v.strip():
            raise ValueError("Part name cannot be blank")
        return v.strip()

class PartUpdate(BaseModel):
    name:          Optional[str]   = None
    description:   Optional[str]   = None
    category_id:   Optional[int]   = None
    unit_cost:     Optional[float] = None
    selling_price: Optional[float] = None
    unit:          Optional[str]   = None
    min_stock:     Optional[int]   = None
    bin_location:  Optional[str]   = None
    vehicle_makes: Optional[str]   = None
