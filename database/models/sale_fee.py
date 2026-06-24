from sqlalchemy import Column, Integer, String, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base import Base


class SaleFee(Base):
    __tablename__ = "sale_fees"

    id      = Column(Integer, primary_key=True, autoincrement=True)
    sale_id = Column(Integer, ForeignKey("sales.id"), nullable=False)
    name    = Column(String, nullable=False)
    amount  = Column(Float, default=0.0)

    sale = relationship("Sale", back_populates="fees")

    __table_args__ = (Index("idx_sale_fees_sale", "sale_id"),)
