from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from database.models.audit_log import AuditLog


class AuditService:

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, part_id: int = None, action: str = None,
                date_from: str = None, date_to: str = None, limit: int = 500):
        # Eager-load the related Part so callers can read l.part.* after the
        # session is closed (the UI builds rows after closing the session).
        q = self.db.query(AuditLog).options(joinedload(AuditLog.part))
        if part_id:
            q = q.filter(AuditLog.part_id == part_id)
        if action:
            q = q.filter(AuditLog.action == action)
        if date_from:
            q = q.filter(AuditLog.created_at >= date_from)
        if date_to:
            q = q.filter(AuditLog.created_at <= date_to + "T23:59:59")
        return q.order_by(AuditLog.created_at.desc()).limit(limit).all()

    def get_recent(self, limit: int = 20):
        return self.db.query(AuditLog)\
            .options(joinedload(AuditLog.part))\
            .order_by(AuditLog.created_at.desc())\
            .limit(limit).all()
