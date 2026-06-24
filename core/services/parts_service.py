from sqlalchemy.orm import Session
from sqlalchemy import text
from database.models.part import Part
from database.models.stock_in import StockIn
from database.models.stock_out import StockOut
from database.models.audit_log import AuditLog
from core.validators.part_schema import PartCreate, PartUpdate
from datetime import datetime
import json


def _gen_sku(session: Session) -> str:
    count = session.query(Part).count() + 1
    date = datetime.now().strftime("%Y%m%d")
    return f"INV-{date}-{count:04d}"


class PartsService:

    def __init__(self, db: Session):
        self.db = db

    def get_all(self, search: str = "", category_id: int = None):
        q = self.db.query(Part).filter(Part.is_active == 1)
        if search:
            term = f"%{search}%"
            q = q.filter(
                Part.name.ilike(term) |
                Part.sku.ilike(term) |
                Part.bin_location.ilike(term)
            )
        if category_id:
            q = q.filter(Part.category_id == category_id)
        return q.order_by(Part.name).all()

    def get_inactive(self, search: str = ""):
        """Return all deactivated parts."""
        q = self.db.query(Part).filter(Part.is_active == 0)
        if search:
            term = f"%{search}%"
            q = q.filter(
                Part.name.ilike(term) |
                Part.sku.ilike(term)
            )
        return q.order_by(Part.name).all()

    def get_by_id(self, part_id: int) -> Part:
        # Fetch regardless of active status so reactivate/delete can find it
        return self.db.query(Part).filter(Part.id == part_id).first()

    def create(self, data: PartCreate, user: str = "system") -> Part:
        part = Part(
            sku=_gen_sku(self.db),
            name=data.name,
            description=data.description,
            category_id=data.category_id,
            unit_cost=data.unit_cost,
            selling_price=data.selling_price,
            unit=data.unit,
            min_stock=data.min_stock,
            bin_location=data.bin_location,
            vehicle_makes=data.vehicle_makes,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )
        self.db.add(part)
        self.db.flush()
        self._audit(part, "PART_CREATED", user=user,
                    reason="Part added to library")
        self.db.commit()
        self.db.refresh(part)
        return part

    # Human-friendly labels for audit messages.
    _FIELD_LABELS = {
        "name": "Name",
        "description": "Description",
        "category_id": "Category",
        "unit_cost": "Unit cost",
        "selling_price": "Selling price",
        "unit": "Unit",
        "min_stock": "Min stock",
        "bin_location": "Bin location",
        "vehicle_makes": "Vehicle makes",
    }
    # Fields whose before/after values are shown as money in the audit log.
    _PRICE_FIELDS = ("unit_cost", "selling_price")

    def update(self, part_id: int, data: PartUpdate, user: str = "system") -> Part:
        part = self.get_by_id(part_id)
        if not part:
            raise ValueError(f"Part {part_id} not found")
        updates = data.model_dump(exclude_none=True)

        price_changes = []   # e.g. "Selling price: ₱150.00 → ₱180.00"
        other_fields = []    # e.g. "Bin location"

        for k, new_val in updates.items():
            old_val = getattr(part, k, None)
            setattr(part, k, new_val)
            if old_val == new_val:
                continue  # skip fields that were submitted but did not actually change

            label = self._FIELD_LABELS.get(k, k.replace("_", " ").capitalize())
            if k in self._PRICE_FIELDS:
                price_changes.append(
                    f"{label}: ₱{float(old_val or 0):,.2f} → ₱{float(new_val or 0):,.2f}"
                )
            else:
                other_fields.append(label)

        part.updated_at = datetime.now().isoformat()

        # Only write an audit entry when something actually changed.
        if price_changes or other_fields:
            reason_parts = []
            if price_changes:
                reason_parts.append("; ".join(price_changes))
            if other_fields:
                reason_parts.append("Fields updated: " + ", ".join(other_fields))
            self._audit(part, "PART_EDITED", user=user,
                        reason=" | ".join(reason_parts))

        self.db.commit()
        self.db.refresh(part)
        return part

    def deactivate(self, part_id: int, user: str = "system"):
        """Soft-delete: hide from all views but keep all history."""
        part = self.get_by_id(part_id)
        if not part:
            raise ValueError(f"Part {part_id} not found")
        if part.is_active == 0:
            raise ValueError("Part is already deactivated")
        part.is_active = 0
        part.updated_at = datetime.now().isoformat()
        self._audit(part, "PART_DEACTIVATED", user=user,
                    reason="Part deactivated")
        self.db.commit()

    def reactivate(self, part_id: int, user: str = "system"):
        """Restore a deactivated part back to active status."""
        part = self.get_by_id(part_id)
        if not part:
            raise ValueError(f"Part {part_id} not found")
        if part.is_active == 1:
            raise ValueError("Part is already active")
        part.is_active = 1
        part.updated_at = datetime.now().isoformat()
        self._audit(part, "PART_REACTIVATED", user=user,
                    reason="Part reactivated")
        self.db.commit()

    def delete(self, part_id: int, user: str = "system"):
        """
        Delete from the user's point of view.

        This is intentionally a soft-delete/deactivate so the item disappears
        from the active Parts Library while stock-in/stock-out history remains
        safe and reports do not break.
        """
        return self.deactivate(part_id, user=user)

    def remove(self, part_id: int, user: str = "system"):
        """Alias used by some UI code paths."""
        return self.deactivate(part_id, user=user)

    def hard_delete(self, part_id: int, user: str = "system"):
        """
        Permanent hard delete.
        Blocked if the part has any stock movements to preserve history integrity.
        Only parts with zero movements (never used) can be permanently deleted.
        """
        part = self.get_by_id(part_id)
        if not part:
            raise ValueError(f"Part {part_id} not found")

        has_in = self.db.query(StockIn).filter(
            StockIn.part_id == part_id).first()
        has_out = self.db.query(StockOut).filter(
            StockOut.part_id == part_id).first()

        if has_in or has_out:
            raise ValueError(
                "This part has stock movement history and cannot be permanently deleted.\n"
                "Use deactivate instead to hide it from all views while keeping the history."
            )

        # Safe to hard-delete: remove audit logs and the part itself
        self.db.query(AuditLog).filter(AuditLog.part_id == part_id).delete()
        self.db.delete(part)
        self.db.commit()

    def get_stock_view(self, search: str = "", category: str = "",
                       include_inactive: bool = False):
        if include_inactive:
            # Query parts table directly for inactive parts
            q = self.db.query(Part).filter(Part.is_active == 0)
            if search:
                term = f"%{search}%"
                q = q.filter(
                    Part.name.ilike(term) |
                    Part.sku.ilike(term)
                )
            parts = q.order_by(Part.name).all()
            return [
                {
                    "id":            p.id,
                    "sku":           p.sku,
                    "name":          p.name,
                    "category":      p.category.name if p.category else "—",
                    "category_id":   p.category_id,
                    "current_stock": p.current_stock,
                    "min_stock":     p.min_stock,
                    "unit":          p.unit,
                    "unit_cost":     p.unit_cost,
                    "selling_price": p.selling_price,
                    "bin_location":  p.bin_location or "—",
                    "is_low_stock":  0,
                    "is_active":     0,
                }
                for p in parts
            ]

        sql = "SELECT * FROM part_stock WHERE 1=1"
        params = {}
        if search:
            sql += " AND (name LIKE :s OR sku LIKE :s OR bin_location LIKE :s)"
            params["s"] = f"%{search}%"
        if category:
            sql += " AND category = :cat"
            params["cat"] = category
        sql += " ORDER BY name"
        rows = self.db.execute(text(sql), params).fetchall()
        result = [dict(r._mapping) for r in rows]

        # Older part_stock views may not include category_id.
        # The web category filter needs category_id, so add it by matching category name.
        try:
            cat_rows = self.db.execute(
                text("SELECT id, name FROM categories")).fetchall()
            cat_map = {str(name).strip().lower()
                           : cid for cid, name in cat_rows}
        except Exception:
            cat_map = {}

        for item in result:
            if "category_id" not in item or item.get("category_id") is None:
                item["category_id"] = cat_map.get(
                    str(item.get("category", "")).strip().lower())

            # Keep safe defaults for web display.
            item.setdefault("selling_price", 0)
            item.setdefault("unit_cost", 0)
            item.setdefault("bin_location", "—")

        return result

    def _audit(self, part: Part, action: str, user: str, reason: str):
        log = AuditLog(
            part_id=part.id,
            action=action,
            delta=None,
            user=user,
            reason=reason,
            snapshot=json.dumps({"sku": part.sku, "name": part.name}),
            created_at=datetime.now().isoformat(),
        )
        self.db.add(log)
