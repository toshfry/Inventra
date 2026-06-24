from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime

class StockOut(Base):
    __tablename__ = "stock_out"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    part_id         = Column(Integer, ForeignKey("parts.id"), nullable=False)
    quantity        = Column(Integer, nullable=False)
    reason          = Column(String, nullable=False)
    job_ref         = Column(String)
    # ── Pricing fields ──────────────────────────────────────────────
    selling_price   = Column(Float, default=0.0)   # price per unit at time of issue
    discount_pct    = Column(Float, default=0.0)   # percentage 0–100
    discount_amount = Column(Float, default=0.0)   # computed: subtotal * discount_pct / 100
    subtotal        = Column(Float, default=0.0)   # selling_price * quantity
    total_amount    = Column(Float, default=0.0)   # subtotal - discount_amount
    unit_cost       = Column(Float, default=0.0)   # cost at time of issue (for margin calc)
    gross_profit    = Column(Float, default=0.0)   # total_amount - (unit_cost * quantity)
    # ────────────────────────────────────────────────────────────────
    issued_by       = Column(String, nullable=False, default="system")
    issued_at       = Column(String, nullable=False, default=lambda: datetime.now().isoformat())

    part = relationship("Part", back_populates="stock_out")

    __table_args__ = (
        Index("idx_stock_out_part",   "part_id"),
        Index("idx_stock_out_issued", "issued_at"),
    )
