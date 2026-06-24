from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime


class StockAdjustment(Base):
    __tablename__ = "stock_adjustments"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    part_id        = Column(Integer, ForeignKey("parts.id"), nullable=False)
    delta          = Column(Integer, nullable=False)   # signed: + increase, - decrease
    previous_count = Column(Integer, nullable=False)   # on-hand before
    new_count      = Column(Integer, nullable=False)   # on-hand after
    reason_code    = Column(String, nullable=False)
    note           = Column(Text)
    unit_cost      = Column(Float, default=0.0)         # snapshot at time of change
    value_delta    = Column(Float, default=0.0)         # delta * unit_cost (neg = loss)
    user           = Column(String, nullable=False, default="system")
    created_at     = Column(String, nullable=False,
                            default=lambda: datetime.now().isoformat())

    part = relationship("Part", back_populates="stock_adjustments")

    __table_args__ = (
        Index("idx_adj_part", "part_id"),
        Index("idx_adj_time", "created_at"),
    )
