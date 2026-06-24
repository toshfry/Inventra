from sqlalchemy.orm import Session, joinedload
from database.models.part import Part
from database.models.stock_adjustment import StockAdjustment
from database.models.audit_log import AuditLog
from core.validators.adjustment_schema import AdjustmentCreate
from datetime import datetime
import json

REASONS = {
    "COUNT_CORRECTION": "Count correction",
    "DAMAGED":          "Damaged",
    "LOST":             "Lost / Stolen",
    "FOUND":            "Found",
    "EXPIRED":          "Expired",
    "OTHER":            "Other",
}


class AdjustmentService:

    def __init__(self, db: Session):
        self.db = db

    def adjust(self, data: AdjustmentCreate, user: str = "system") -> StockAdjustment:
        part_id = data.part_id
        mode = data.mode
        value = data.value
        reason_code = data.reason_code
        note = data.note

        # Defense-in-depth guards (schema already validates these, but keep for safety)
        if reason_code not in REASONS:
            raise ValueError(f"Unknown reason: {reason_code}")

        part = self.db.get(Part, part_id)
        if not part or not part.is_active:
            raise ValueError(f"Part ID {part_id} not found")

        current = part.current_stock
        if mode == "set":
            new_count = int(value)
            delta = new_count - current
        elif mode == "delta":
            delta = int(value)
            new_count = current + delta
        else:
            raise ValueError(f"Invalid mode: {mode}")

        if delta == 0:
            raise ValueError("No change to apply.")
        if new_count < 0:
            raise ValueError(
                f"Adjustment would make stock negative (result {new_count}).")

        unit_cost = part.unit_cost or 0.0
        value_delta = round(delta * unit_cost, 2)

        adj = StockAdjustment(
            part_id=part.id, delta=delta,
            previous_count=current, new_count=new_count,
            reason_code=reason_code, note=note,
            unit_cost=unit_cost, value_delta=value_delta,
            user=user, created_at=datetime.now().isoformat(),
        )
        self.db.add(adj)
        self.db.flush()

        self._write_audit(part, adj)
        self.db.commit()
        self.db.refresh(adj)
        return adj

    def _write_audit(self, part, adj):
        sign = "+" if adj.delta > 0 else ""
        reason = f"{REASONS[adj.reason_code]}: {adj.previous_count} → {adj.new_count} ({sign}{adj.delta})"
        if adj.note:
            reason += f" — {adj.note}"
        self.db.add(AuditLog(
            part_id=part.id, action="STOCK_ADJUST", delta=adj.delta,
            user=adj.user, reason=reason, reference_id=adj.id,
            snapshot=json.dumps({"sku": part.sku, "name": part.name,
                                 "current_stock": adj.new_count}),
            created_at=datetime.now().isoformat(),
        ))

    def get_history(self, part_id: int = None, date_from: str = None,
                    date_to: str = None, limit: int = 500):
        q = self.db.query(StockAdjustment).options(
            joinedload(StockAdjustment.part))
        if part_id:
            q = q.filter(StockAdjustment.part_id == part_id)
        if date_from:
            q = q.filter(StockAdjustment.created_at >= date_from)
        if date_to:
            q = q.filter(StockAdjustment.created_at <= date_to + "T23:59:59.999999")
        return q.order_by(StockAdjustment.created_at.desc()).limit(limit).all()
