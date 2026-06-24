from pydantic import BaseModel, Field
from typing import Optional, Literal


class ReturnCreate(BaseModel):
    part_id: int
    stock_out_id: Optional[int] = None
    sale_id: Optional[int] = None
    quantity: int = Field(gt=0)
    condition: Literal["RESELLABLE", "DAMAGED"]
    reason_code: Literal[
        "WRONG_SIZE", "WRONG_COMPAT", "DAMAGED", "DEFECTIVE",
        "CHANGED_MIND", "WARRANTY", "OTHER"
    ]
    refund_amount: float = Field(default=0.0, ge=0)
    refund_method: Literal["Cash", "GCash", "Bank"] = "Cash"
    note: Optional[str] = None
