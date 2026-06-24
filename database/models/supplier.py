from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime

class Supplier(Base):
    __tablename__ = "suppliers"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String, nullable=False)
    contact_name = Column(String)
    phone        = Column(String)
    email        = Column(String)
    address      = Column(Text)
    notes        = Column(Text)
    is_active    = Column(Integer, nullable=False, default=1)
    created_at   = Column(String, default=lambda: datetime.now().isoformat())
    updated_at   = Column(String, default=lambda: datetime.now().isoformat())

    stock_in = relationship("StockIn", back_populates="supplier")

    def __repr__(self):
        return f"<Supplier {self.name}>"
