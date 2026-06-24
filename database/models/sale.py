from sqlalchemy import Column, Integer, String, Float, Text, Index
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime


class Sale(Base):
    """
    POS sale receipt header.

    Tax fields (enabled/name/rate/taxable/amount) are stored as SNAPSHOTS at
    the moment of sale so that reprinting an old receipt stays accurate even
    if the POS tax settings are later changed. ``receipt_snapshot`` holds a
    JSON copy of the receipt-print settings (store name, footer, etc.) for the
    same reason.
    """
    __tablename__ = "sales"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    receipt_no      = Column(String, nullable=False, unique=True)
    sale_date       = Column(String, nullable=False,
                             default=lambda: datetime.now().isoformat())
    cashier         = Column(String, nullable=False, default="system")
    payment_method  = Column(String, nullable=False, default="Cash")

    # ── Money totals (all snapshots) ─────────────────────────────────
    subtotal        = Column(Float, default=0.0)   # Σ line subtotals (price×qty)
    # Sale-level discount: ``discount_value`` is the raw input (an amount or a
    # percentage depending on ``discount_type``); ``discount_total`` is the
    # resolved peso amount actually deducted. (Older rows store the summed
    # per-item discount in discount_total with type 'amount'.)
    discount_type   = Column(String, default="amount")  # 'amount' | 'percent'
    discount_value  = Column(Float, default=0.0)
    discount_total  = Column(Float, default=0.0)   # resolved discount in pesos
    taxable_amount  = Column(Float, default=0.0)   # base the tax was applied to
    tax_enabled     = Column(Integer, default=0)   # 0/1 snapshot
    tax_name        = Column(String, default="VAT")
    tax_rate        = Column(Float, default=0.0)   # percentage snapshot
    tax_amount      = Column(Float, default=0.0)
    labor_amount    = Column(Float, default=0.0)   # service/labor fee (extra revenue)
    grand_total     = Column(Float, default=0.0)
    amount_received = Column(Float, default=0.0)
    change_due      = Column(Float, default=0.0)

    notes            = Column(Text)
    receipt_snapshot = Column(Text)   # JSON of receipt-print settings at sale time
    created_at       = Column(String, nullable=False,
                              default=lambda: datetime.now().isoformat())

    items = relationship("SaleItem", back_populates="sale",
                         cascade="all, delete-orphan", lazy="selectin")
    fees = relationship("SaleFee", back_populates="sale",
                        cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        Index("idx_sales_receipt", "receipt_no"),
        Index("idx_sales_date",    "sale_date"),
    )

    def __repr__(self):
        return f"<Sale {self.receipt_no} ₱{self.grand_total:,.2f}>"
