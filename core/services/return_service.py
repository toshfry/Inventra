from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from database.models.part import Part
from database.models.stock_out import StockOut
from database.models.sale import Sale
from database.models.sale_item import SaleItem
from database.models.customer_return import CustomerReturn
from database.models.audit_log import AuditLog
from core.validators.return_schema import ReturnCreate
from datetime import datetime
import json

REASONS = {
    "WRONG_SIZE":   "Wrong size",
    "WRONG_COMPAT": "Wrong compatibility",
    "DAMAGED":      "Damaged",
    "DEFECTIVE":    "Defective",
    "CHANGED_MIND": "Changed mind",
    "WARRANTY":     "Warranty",
    "OTHER":        "Other",
}
CONDITIONS = {"RESELLABLE": "Resellable", "DAMAGED": "Damaged"}
REFUND_METHODS = ["Cash", "GCash", "Bank"]


class ReturnService:

    def __init__(self, db: Session):
        self.db = db

    def returned_qty(self, stock_out_id: int) -> int:
        if not stock_out_id:
            return 0
        total = self.db.query(func.coalesce(func.sum(CustomerReturn.quantity), 0))\
            .filter(CustomerReturn.stock_out_id == stock_out_id).scalar()
        return int(total or 0)

    def process_return(self, data: ReturnCreate, user: str = "system") -> CustomerReturn:
        if data.quantity <= 0:
            raise ValueError("Quantity must be greater than 0.")
        if data.reason_code not in REASONS:
            raise ValueError(f"Unknown reason: {data.reason_code}")
        if data.condition not in CONDITIONS:
            raise ValueError(f"Unknown condition: {data.condition}")
        if data.refund_method not in REFUND_METHODS:
            raise ValueError(f"Unknown refund method: {data.refund_method}")
        if data.refund_amount < 0:
            raise ValueError("Refund amount cannot be negative.")

        part = self.db.get(Part, data.part_id)
        if not part:
            raise ValueError(f"Part ID {data.part_id} not found")

        unit_price = part.selling_price or 0.0
        unit_cost = part.unit_cost or 0.0
        sale_id = data.sale_id

        if data.stock_out_id:
            so = self.db.get(StockOut, data.stock_out_id)
            if not so:
                raise ValueError(f"Sale/issue {data.stock_out_id} not found")
            already = self.returned_qty(data.stock_out_id)
            remaining = so.quantity - already
            if data.quantity > remaining:
                raise ValueError(
                    f"Cannot return {data.quantity}; only {remaining} of {so.quantity} "
                    "remain returnable on this sale.")
            unit_price = so.selling_price if so.selling_price is not None else unit_price
            unit_cost = so.unit_cost if so.unit_cost is not None else unit_cost
            if sale_id is None:
                si = self.db.query(SaleItem).filter(
                    SaleItem.stock_out_id == so.id).first()
                if si:
                    sale_id = si.sale_id

        restock_qty = data.quantity if data.condition == "RESELLABLE" else 0
        if data.condition == "RESELLABLE":
            profit_delta = -(data.refund_amount - unit_cost * data.quantity)
        else:  # DAMAGED — cash out, no sellable asset recovered
            profit_delta = -data.refund_amount
        profit_delta = round(profit_delta, 2)

        ret = CustomerReturn(
            part_id=part.id, stock_out_id=data.stock_out_id, sale_id=sale_id,
            quantity=data.quantity, condition=data.condition,
            restock_qty=restock_qty, reason_code=data.reason_code,
            note=data.note, unit_price=unit_price, unit_cost=unit_cost,
            refund_amount=round(data.refund_amount, 2),
            refund_method=data.refund_method, profit_delta=profit_delta,
            user=user, created_at=datetime.now().isoformat(),
        )
        self.db.add(ret)
        self.db.flush()
        self._write_audit(part, ret)
        self.db.commit()
        self.db.refresh(ret)
        return ret

    def _write_audit(self, part, ret):
        reason = (f"Return ×{ret.quantity} ({CONDITIONS[ret.condition]}, "
                  f"{REASONS[ret.reason_code]}) — refund ₱{ret.refund_amount:,.2f} "
                  f"via {ret.refund_method}")
        if ret.note:
            reason += f" — {ret.note}"
        self.db.add(AuditLog(
            part_id=part.id, action="RETURN", delta=ret.restock_qty,
            user=ret.user, reason=reason, reference_id=ret.id,
            snapshot=json.dumps({"sku": part.sku, "name": part.name,
                                 "current_stock": part.current_stock}),
            created_at=datetime.now().isoformat(),
        ))

    def get_history(self, part_id: int = None, date_from: str = None,
                    date_to: str = None, limit: int = 500):
        q = self.db.query(CustomerReturn).options(joinedload(CustomerReturn.part))
        if part_id:
            q = q.filter(CustomerReturn.part_id == part_id)
        if date_from:
            q = q.filter(CustomerReturn.created_at >= date_from)
        if date_to:
            q = q.filter(CustomerReturn.created_at <= date_to + "T23:59:59.999999")
        return q.order_by(CustomerReturn.created_at.desc()).limit(limit).all()

    def returns_financials(self, date_from: str = None, date_to: str = None) -> dict:
        rows = self.get_history(date_from=date_from, date_to=date_to, limit=100000)
        return {
            "refund_total":     round(sum(r.refund_amount for r in rows), 2),
            "profit_delta_total": round(sum(r.profit_delta for r in rows), 2),
            "units_restocked":  sum(r.restock_qty for r in rows),
            "units_scrapped":   sum(r.quantity - r.restock_qty for r in rows),
            "count":            len(rows),
        }

    def get_returnable_issues(self, search: str = "", limit: int = 100) -> list:
        """Recent Stock Out issues that still have units left to return."""
        rows = self.db.query(StockOut).options(joinedload(StockOut.part))\
            .order_by(StockOut.issued_at.desc()).limit(500).all()
        out = []
        term = (search or "").strip().lower()
        for so in rows:
            if not so.part:
                continue
            name, sku = so.part.name, (so.part.sku or "")
            if term and term not in name.lower() and term not in sku.lower():
                continue
            remaining = so.quantity - self.returned_qty(so.id)
            if remaining <= 0:
                continue
            receipt_no, sale_id = None, None
            si = self.db.query(SaleItem).filter(
                SaleItem.stock_out_id == so.id).first()
            if si:
                sale_id = si.sale_id
                sale = self.db.get(Sale, si.sale_id)
                receipt_no = sale.receipt_no if sale else None
            out.append({
                "stock_out_id": so.id, "sale_id": sale_id, "receipt_no": receipt_no,
                "part_id": so.part_id, "sku": sku, "name": name,
                "sold_qty": so.quantity, "remaining": remaining,
                "unit_price": so.selling_price or 0.0, "unit_cost": so.unit_cost or 0.0,
                "issued_at": so.issued_at,
            })
            if len(out) >= limit:
                break
        return out
