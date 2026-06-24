from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List

# Payment methods supported by the POS checkout.
PAYMENT_METHODS = ["Cash", "GCash", "Card", "Bank Transfer", "Other"]

# Sale-level discount types.
DISCOUNT_TYPES = ["amount", "percent"]


class CartItemCreate(BaseModel):
    """A single line submitted from the POS cart."""
    part_id:    int
    quantity:   int   = Field(..., gt=0)            # no zero / negative qty
    unit_price: float = Field(0.0, ge=0)            # no negative price
    # Per-item discount is deprecated — discount is now applied at the sale
    # level (see SaleCreate.discount_*). Kept (default 0, ignored by the
    # service) only so older API payloads do not break.
    discount:   float = Field(0.0, ge=0)


class FeeLine(BaseModel):
    name: str
    amount: float = Field(0.0, ge=0)


class SaleCreate(BaseModel):
    """Payload for completing a POS sale."""
    items:           List[CartItemCreate] = Field(default_factory=list)
    payment_method:  str   = "Cash"
    amount_received: float = Field(0.0, ge=0)
    # ── Sale-level discount (applied to the whole sale, after subtotal) ──
    discount_type:   str   = "amount"               # 'amount' | 'percent'
    discount_value:  float = Field(0.0, ge=0)       # never negative
    labor_amount:    float = Field(0.0, ge=0)       # legacy single fee (back-compat)
    fees:            List[FeeLine] = Field(default_factory=list)
    cashier:         Optional[str] = None
    notes:           Optional[str] = None

    @field_validator("payment_method")
    @classmethod
    def valid_method(cls, v):
        v = (v or "").strip()
        if v not in PAYMENT_METHODS:
            raise ValueError(
                f"Payment method must be one of: {', '.join(PAYMENT_METHODS)}")
        return v

    @field_validator("discount_type")
    @classmethod
    def valid_disc_type(cls, v):
        v = (v or "amount").strip().lower()
        if v not in DISCOUNT_TYPES:
            raise ValueError("Discount type must be 'amount' or 'percent'")
        return v

    @model_validator(mode="after")
    def check_percent_range(self):
        # Percentage discount cannot exceed 100%. (Amount-exceeds-subtotal is
        # clamped in the service, where the subtotal is known.)
        if self.discount_type == "percent" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100%.")
        return self


class PosSettingsUpdate(BaseModel):
    """
    POS tax + receipt settings. Every field is optional so callers can send
    partial updates; the service merges them over the persisted values.

    Tax is applied AFTER discounts by default (tax_apply='after_discount'),
    which matches typical retail VAT behaviour. 'before_discount' taxes the
    full pre-discount subtotal.
    """
    # ── Tax ──────────────────────────────────────────────────────────
    tax_enabled: Optional[bool]  = None
    tax_name:    Optional[str]   = None
    tax_rate:    Optional[float] = Field(None, ge=0, le=100)
    tax_apply:   Optional[str]   = None   # 'after_discount' | 'before_discount'

    # ── Receipt print ────────────────────────────────────────────────
    store_name:         Optional[str]  = None
    store_address:      Optional[str]  = None
    store_phone:        Optional[str]  = None
    receipt_footer:     Optional[str]  = None
    show_cashier:       Optional[bool] = None
    show_sku:           Optional[bool] = None
    show_tax_breakdown: Optional[bool] = None
    paper_size:         Optional[str]  = None   # '58mm' | '80mm' | 'Letter' | 'A4'

    @field_validator("tax_apply")
    @classmethod
    def valid_apply(cls, v):
        if v is not None and v not in ("after_discount", "before_discount"):
            raise ValueError(
                "tax_apply must be 'after_discount' or 'before_discount'")
        return v

    @field_validator("paper_size")
    @classmethod
    def valid_paper(cls, v):
        if v is not None and v not in ("58mm", "80mm", "Letter", "A4"):
            raise ValueError("paper_size must be 58mm, 80mm, Letter, or A4")
        return v
