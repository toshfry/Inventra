from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime


class CustomerReturn(Base):
    __tablename__ = "customer_returns"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    part_id       = Column(Integer, ForeignKey("parts.id"), nullable=False)
    stock_out_id  = Column(Integer, ForeignKey("stock_out.id"))   # null = blind return
    sale_id       = Column(Integer, ForeignKey("sales.id"))       # for receipt display
    quantity      = Column(Integer, nullable=False)
    condition     = Column(String, nullable=False)                # RESELLABLE | DAMAGED
    restock_qty   = Column(Integer, nullable=False, default=0)    # quantity if resellable else 0
    reason_code   = Column(String, nullable=False)
    note          = Column(Text)
    unit_price    = Column(Float, default=0.0)                    # snapshot
    unit_cost     = Column(Float, default=0.0)                    # snapshot
    refund_amount = Column(Float, default=0.0)
    refund_method = Column(String, default="Cash")
    profit_delta  = Column(Float, default=0.0)                    # snapshot (negative)
    user          = Column(String, nullable=False, default="system")
    created_at    = Column(String, nullable=False,
                           default=lambda: datetime.now().isoformat())

    part = relationship("Part", back_populates="returns")

    __table_args__ = (
        Index("idx_ret_part", "part_id"),
        Index("idx_ret_stockout", "stock_out_id"),
        Index("idx_ret_time", "created_at"),
    )
