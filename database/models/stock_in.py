from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime

class StockIn(Base):
    __tablename__ = "stock_in"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    part_id      = Column(Integer, ForeignKey("parts.id"), nullable=False)
    supplier_id  = Column(Integer, ForeignKey("suppliers.id"))
    quantity     = Column(Integer, nullable=False)
    unit_cost    = Column(Float, default=0.0)
    reference_no = Column(String)
    notes        = Column(Text)
    received_by  = Column(String, nullable=False, default="system")
    received_at  = Column(String, nullable=False, default=lambda: datetime.now().isoformat())

    part     = relationship("Part",     back_populates="stock_in")
    supplier = relationship("Supplier", back_populates="stock_in")

    __table_args__ = (
        Index("idx_stock_in_part",     "part_id"),
        Index("idx_stock_in_received", "received_at"),
    )
