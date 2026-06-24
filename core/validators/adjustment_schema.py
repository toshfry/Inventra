from pydantic import BaseModel
from typing import Optional, Literal


class AdjustmentCreate(BaseModel):
    part_id: int
    mode: Literal["set", "delta"]
    value: int
    reason_code: Literal[
        "COUNT_CORRECTION", "DAMAGED", "LOST", "FOUND", "EXPIRED", "OTHER"
    ]
    note: Optional[str] = None
