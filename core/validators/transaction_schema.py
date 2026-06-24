from pydantic import BaseModel, Field, field_validator
from typing import Optional

class StockInCreate(BaseModel):
    part_id:      int
    supplier_id:  Optional[int] = None
    quantity:     int   = Field(..., gt=0)
    unit_cost:    float = Field(0.0, ge=0)
    reference_no: Optional[str] = None
    notes:        Optional[str] = None
    received_by:  str   = "system"

class StockOutCreate(BaseModel):
    part_id:        int
    quantity:       int   = Field(..., gt=0)
    reason:         str   = Field(..., min_length=1)
    job_ref:        Optional[str]  = None
    selling_price:  float = Field(0.0, ge=0)
    discount_pct:   float = Field(0.0, ge=0, le=100)
    issued_by:      str   = "system"

    @field_validator("reason")
    @classmethod
    def reason_not_blank(cls, v):
        if not v.strip():
            raise ValueError("Reason cannot be blank")
        return v.strip()

    @property
    def subtotal(self) -> float:
        return round(self.selling_price * self.quantity, 2)

    @property
    def discount_amount(self) -> float:
        return round(self.subtotal * self.discount_pct / 100, 2)

    @property
    def total_amount(self) -> float:
        return round(self.subtotal - self.discount_amount, 2)
