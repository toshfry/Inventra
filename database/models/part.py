from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime

class Part(Base):
    __tablename__ = "parts"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    sku           = Column(String, nullable=False, unique=True)
    name          = Column(String, nullable=False)
    description   = Column(Text)
    category_id   = Column(Integer, ForeignKey("categories.id"))
    unit_cost     = Column(Float, default=0.0)   # purchase / cost price
    selling_price = Column(Float, default=0.0)   # default selling price
    unit          = Column(String, default="pcs")
    min_stock     = Column(Integer, default=5)
    bin_location  = Column(String)
    vehicle_makes = Column(Text)
    is_active     = Column(Integer, default=1)
    created_at    = Column(String, default=lambda: datetime.now().isoformat())
    updated_at    = Column(String, default=lambda: datetime.now().isoformat())

    category   = relationship("Category", back_populates="parts")
    stock_in   = relationship("StockIn",  back_populates="part", lazy="dynamic")
    stock_out  = relationship("StockOut", back_populates="part", lazy="dynamic")
    audit_logs = relationship("AuditLog", back_populates="part")
    stock_adjustments = relationship("StockAdjustment", back_populates="part",
                                     lazy="dynamic")
    returns = relationship("CustomerReturn", back_populates="part",
                           lazy="dynamic")

    __table_args__ = (
        Index("idx_parts_sku",      "sku"),
        Index("idx_parts_name",     "name"),
        Index("idx_parts_category", "category_id"),
    )

    @property
    def current_stock(self) -> int:
        """
        On-hand = stock_in − stock_out + adjustments + restocked returns.

        Computed with scalar SQL rather than by iterating the (lazy="dynamic")
        relationships, so it returns a correct result even when the Part is
        detached from its session — using the object's own session when it has
        one, otherwise a short-lived session.
        """
        from sqlalchemy import func
        from sqlalchemy.orm import object_session
        from database.models.stock_in import StockIn
        from database.models.stock_out import StockOut
        from database.models.stock_adjustment import StockAdjustment
        from database.models.customer_return import CustomerReturn

        if self.id is None:
            return 0

        sess = object_session(self)
        own = sess is None
        if own:
            from database.engine import get_session
            sess = get_session()
        try:
            def _sum(model, col):
                return int(sess.query(func.coalesce(func.sum(col), 0))
                           .filter(model.part_id == self.id).scalar() or 0)
            return (_sum(StockIn, StockIn.quantity)
                    - _sum(StockOut, StockOut.quantity)
                    + _sum(StockAdjustment, StockAdjustment.delta)
                    + _sum(CustomerReturn, CustomerReturn.restock_qty))
        finally:
            if own:
                sess.close()

    @property
    def margin(self) -> float:
        if self.unit_cost and self.unit_cost > 0:
            return ((self.selling_price or 0) - self.unit_cost) / self.unit_cost * 100
        return 0.0

    def __repr__(self):
        return f"<Part {self.sku} {self.name}>"
