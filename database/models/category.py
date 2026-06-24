from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from database.base import Base

class Category(Base):
    __tablename__ = "categories"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    name      = Column(String, nullable=False, unique=True)
    color_hex = Column(String, nullable=False, default="#888888")

    parts = relationship("Part", back_populates="category")

    def __repr__(self):
        return f"<Category {self.name}>"
