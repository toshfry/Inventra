from sqlalchemy import Column, Integer, String, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from database.base import Base
from datetime import datetime

class AuditLog(Base):
    __tablename__ = "audit_log"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    part_id      = Column(Integer, ForeignKey("parts.id"))
    action       = Column(String, nullable=False)
    delta        = Column(Integer)
    user         = Column(String, nullable=False, default="system")
    reason       = Column(Text)
    reference_id = Column(Integer)
    snapshot     = Column(Text)
    created_at   = Column(String, nullable=False, default=lambda: datetime.now().isoformat())

    part = relationship("Part", back_populates="audit_logs")

    __table_args__ = (
        Index("idx_audit_part", "part_id"),
        Index("idx_audit_time", "created_at"),
    )

    # No update() or delete() — immutability enforced at service layer
