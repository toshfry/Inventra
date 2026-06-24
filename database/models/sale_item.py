from sqlalchemy import Column, Integer, String, Float, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base import Base


class SaleItem(Base):
    """
    A single line on a POS sale.

    ``sku`` and ``name`` are snapshots so the receipt stays accurate even if
    the part is later renamed or deactivated. ``stock_out_id`` links to the
    StockOut record this line created, keeping stock history / reports
    consistent with the existing inventory mechanism.
    """
    __tablename__ = "sale_items"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    sale_id      = Column(Integer, ForeignKey("sales.id"), nullable=False)
    part_id      = Column(Integer, ForeignKey("parts.id"))
    sku          = Column(String)      # snapshot
    name         = Column(String)      # snapshot
    quantity     = Column(Integer, nullable=False)
    unit_price   = Column(Float, default=0.0)
    discount     = Column(Float, default=0.0)   # discount amount for the line
    line_total   = Column(Float, default=0.0)   # unit_price*qty - discount
    unit_cost    = Column(Float, default=0.0)   # snapshot for profit reports
    stock_out_id = Column(Integer, ForeignKey("stock_out.id"))

    sale = relationship("Sale", back_populates="items")

    __table_args__ = (
        Index("idx_sale_items_sale", "sale_id"),
        Index("idx_sale_items_part", "part_id"),
    )
