from sqlalchemy.orm import Session
from database.models.part import Part
from database.models.stock_in import StockIn
from database.models.stock_out import StockOut
from database.models.audit_log import AuditLog
from core.validators.transaction_schema import StockInCreate, StockOutCreate
from datetime import datetime
import json


class StockService:

    def __init__(self, db: Session):
        self.db = db

    # ── Stock In ──────────────────────────────────────────────────────
    def receive_stock(self, data: StockInCreate) -> StockIn:
        part = self.db.get(Part, data.part_id)
        if not part or not part.is_active:
            raise ValueError(f"Part ID {data.part_id} not found")

        # If unit cost is not entered in Stock In, use the default cost
        # already saved in the Parts Library.
        actual_unit_cost = data.unit_cost
        if actual_unit_cost is None or actual_unit_cost <= 0:
            actual_unit_cost = part.unit_cost or 0.0

        txn = StockIn(
            part_id=data.part_id,
            supplier_id=data.supplier_id,
            quantity=data.quantity,
            unit_cost=actual_unit_cost,
            reference_no=data.reference_no,
            notes=data.notes,
            received_by=data.received_by,
            received_at=datetime.now().isoformat(),
        )
        self.db.add(txn)
        self.db.flush()
        self._write_audit(part=part, action="STOCK_IN", delta=+data.quantity,
                          user=data.received_by, reason=data.notes or "Stock received",
                          ref_id=txn.id)
        self.db.commit()
        return txn

    # ── Stock Out ─────────────────────────────────────────────────────
    def issue_stock(self, data: StockOutCreate) -> StockOut:
        part = self.db.get(Part, data.part_id)
        if not part or not part.is_active:
            raise ValueError(f"Part ID {data.part_id} not found")

        available = part.current_stock
        if data.quantity > available:
            raise ValueError(
                f"Insufficient stock. Available: {available}, Requested: {data.quantity}"
            )

        # Compute pricing.
        # If selling price is not entered, use the default selling price
        # already saved in the Parts Library.
        actual_selling_price = data.selling_price
        if actual_selling_price is None or actual_selling_price <= 0:
            actual_selling_price = part.selling_price or 0.0

        subtotal = round(actual_selling_price * data.quantity, 2)
        discount_amount = round(subtotal * data.discount_pct / 100, 2)
        total_amount = round(subtotal - discount_amount, 2)
        gross_profit = round(
            total_amount - (part.unit_cost * data.quantity), 2)

        txn = StockOut(
            part_id=data.part_id,
            quantity=data.quantity,
            reason=data.reason,
            job_ref=data.job_ref,
            selling_price=actual_selling_price,
            discount_pct=data.discount_pct,
            discount_amount=discount_amount,
            subtotal=subtotal,
            total_amount=total_amount,
            unit_cost=part.unit_cost,
            gross_profit=gross_profit,
            issued_by=data.issued_by,
            issued_at=datetime.now().isoformat(),
        )
        self.db.add(txn)
        self.db.flush()
        self._write_audit(
            part=part, action="STOCK_OUT", delta=-data.quantity,
            user=data.issued_by,
            reason=f"{data.reason} | Sale: ₱{total_amount:,.2f}" + (
                f" (disc {data.discount_pct}%)" if data.discount_pct else ""
            ),
            ref_id=txn.id,
        )
        self.db.commit()
        return txn

    # ── Modify & Cancel ───────────────────────────────────────────────
    def update_stock_out(self, txn_id: int, new_quantity: int, new_price: float,
                         new_disc_pct: float, new_reason: str, new_job_ref: str,
                         user: str = "System") -> StockOut:
        """Updates an existing stock-out transaction and adjusts inventory via audit."""
        txn = self.db.get(StockOut, txn_id)
        if not txn:
            raise ValueError(f"Transaction ID {txn_id} not found.")

        part = self.db.get(Part, txn.part_id)

        # Calculate the difference to adjust stock properly
        qty_diff = txn.quantity - new_quantity

        if qty_diff != 0:
            self._write_audit(
                part=part, action="MODIFY_OUT", delta=qty_diff,
                user=user,
                reason=f"Modified txn #{txn_id}: Qty changed from {txn.quantity} to {new_quantity}",
                ref_id=txn.id
            )

        # Update the transaction record
        txn.quantity = new_quantity
        txn.selling_price = new_price
        txn.discount_pct = new_disc_pct
        txn.reason = new_reason
        txn.job_ref = new_job_ref

        # Recompute financial totals
        txn.subtotal = round(new_price * new_quantity, 2)
        txn.discount_amount = round(txn.subtotal * new_disc_pct / 100, 2)
        txn.total_amount = round(txn.subtotal - txn.discount_amount, 2)
        txn.gross_profit = round(
            txn.total_amount - (txn.unit_cost * new_quantity), 2)

        self.db.commit()
        return txn

    def cancel_stock_out(self, txn_id: int, user: str = "System"):
        """Cancels a transaction entirely and restores the stock."""
        txn = self.db.get(StockOut, txn_id)
        if not txn:
            raise ValueError(f"Transaction ID {txn_id} not found.")

        # Don't orphan dependent records (FK-protected): a POS sale line and any
        # linked customer return point at this stock-out. Deleting it would either
        # corrupt the receipt or break the return history.
        from database.models.sale_item import SaleItem
        from database.models.customer_return import CustomerReturn
        if self.db.query(SaleItem).filter(SaleItem.stock_out_id == txn_id).first():
            raise ValueError(
                "This sale was made through the POS and belongs to a receipt, so it "
                "can't be cancelled here. To reverse it, process a Return for the "
                "item (Returns screen) — that refunds the customer and restocks it.")
        if self.db.query(CustomerReturn).filter(
                CustomerReturn.stock_out_id == txn_id).first():
            raise ValueError(
                "This sale has a linked customer return, so it's kept for the "
                "record. Remove the return first if you really must cancel the sale.")

        part = self.db.get(Part, txn.part_id)

        # Revert the stock (positive delta puts it back in inventory)
        self._write_audit(
            part=part, action="CANCEL_OUT", delta=+txn.quantity,
            user=user,
            reason=f"Cancelled transaction #{txn_id}",
            ref_id=txn.id
        )

        self.db.delete(txn)
        self.db.commit()

    def update_stock_in(self, txn_id: int, new_quantity: int, new_unit_cost: float,
                        new_supplier_id: int = None, new_reference_no: str = None,
                        user: str = "System") -> StockIn:
        """Updates an existing stock-in transaction and adjusts inventory via audit."""
        txn = self.db.get(StockIn, txn_id)
        if not txn:
            raise ValueError(f"Transaction ID {txn_id} not found.")

        part = self.db.get(Part, txn.part_id)

        # Calculate the difference to adjust stock properly
        qty_diff = new_quantity - txn.quantity

        if qty_diff != 0:
            self._write_audit(
                part=part, action="MODIFY_IN", delta=qty_diff,
                user=user,
                reason=f"Modified txn #{txn_id}: Qty changed from {txn.quantity} to {new_quantity}",
                ref_id=txn.id
            )

        # Update the transaction record
        txn.quantity = new_quantity
        txn.unit_cost = new_unit_cost
        txn.supplier_id = new_supplier_id
        txn.reference_no = new_reference_no

        self.db.commit()
        return txn

    def cancel_stock_in(self, txn_id: int, user: str = "System"):
        """Cancels a stock-in transaction entirely and reverts the stock."""
        txn = self.db.get(StockIn, txn_id)
        if not txn:
            raise ValueError(f"Transaction ID {txn_id} not found.")

        part = self.db.get(Part, txn.part_id)

        # Revert the stock (negative delta removes it from inventory)
        self._write_audit(
            part=part, action="CANCEL_IN", delta=-txn.quantity,
            user=user,
            reason=f"Cancelled transaction #{txn_id}",
            ref_id=txn.id
        )

        self.db.delete(txn)
        self.db.commit()

    # ── History ───────────────────────────────────────────────────────
    def get_stock_in_history(self, part_id: int = None, limit: int = 200,
                             date_from: str = None, date_to: str = None):
        q = self.db.query(StockIn)
        if part_id:
            q = q.filter(StockIn.part_id == part_id)
        if date_from:
            q = q.filter(StockIn.received_at >= date_from)
        if date_to:
            q = q.filter(StockIn.received_at <= date_to + "T23:59:59.999999")
        return q.order_by(StockIn.received_at.desc()).limit(limit).all()

    def get_stock_out_history(self, part_id: int = None, limit: int = 200,
                              date_from: str = None, date_to: str = None):
        q = self.db.query(StockOut)
        if part_id:
            q = q.filter(StockOut.part_id == part_id)
        if date_from:
            q = q.filter(StockOut.issued_at >= date_from)
        if date_to:
            q = q.filter(StockOut.issued_at <= date_to + "T23:59:59.999999")
        return q.order_by(StockOut.issued_at.desc()).limit(limit).all()

    # ── Internal ──────────────────────────────────────────────────────
    def _write_audit(self, part, action, delta, user, reason, ref_id=None):
        log = AuditLog(
            part_id=part.id,
            action=action,
            delta=delta,
            user=user,
            reason=reason,
            reference_id=ref_id,
            snapshot=json.dumps({
                "sku":           part.sku,
                "name":          part.name,
                "current_stock": part.current_stock,
            }),
            created_at=datetime.now().isoformat(),
        )
        self.db.add(log)
