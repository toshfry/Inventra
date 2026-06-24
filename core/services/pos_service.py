from sqlalchemy.orm import Session
from sqlalchemy import text, func
from database.models.part import Part
from database.models.stock_out import StockOut
from database.models.audit_log import AuditLog
from database.models.sale import Sale
from database.models.sale_item import SaleItem
from core.validators.pos_schema import SaleCreate
from core.services.settings_service import SettingsService
from datetime import datetime
import json


class PosService:
    """
    Point-of-sale checkout.

    A sale reduces inventory through the existing stock-out mechanism: every
    cart line creates a StockOut record (with an audit-log entry) exactly like
    Stock Out does, so reports and stock history stay accurate. The whole
    checkout runs in a single transaction — the Sale header, its SaleItems and
    all StockOut rows either commit together or not at all.
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Part search (for the POS picker) ─────────────────────────────
    def search_parts(self, query: str = "", category: str = "", limit: int = 50):
        sql = "SELECT * FROM part_stock WHERE 1=1"
        params = {}
        if query:
            sql += " AND (name LIKE :s OR sku LIKE :s)"
            params["s"] = f"%{query}%"
        if category:
            sql += " AND category = :cat"
            params["cat"] = category
        sql += " ORDER BY name LIMIT :lim"
        params["lim"] = limit
        rows = self.db.execute(text(sql), params).fetchall()
        return [dict(r._mapping) for r in rows]

    # ── Checkout ──────────────────────────────────────────────────────
    def create_sale(self, data: SaleCreate, cashier: str = "system") -> Sale:
        cashier = (data.cashier or cashier or "system")
        cfg = SettingsService(self.db).get_pos_settings()

        # ── 1. Validate lines & re-check stock against live inventory ──
        lines = []
        subtotal = 0.0
        for item in data.items:
            part = self.db.get(Part, item.part_id)
            if not part or not part.is_active:
                raise ValueError(f"Part ID {item.part_id} not found")

            available = part.current_stock
            if item.quantity > available:
                raise ValueError(
                    f"Insufficient stock for {part.sku} — {part.name}. "
                    f"Available: {available}, Requested: {item.quantity}")

            unit_price = item.unit_price if item.unit_price and item.unit_price > 0 \
                else (part.selling_price or 0.0)
            line_subtotal = round(unit_price * item.quantity, 2)

            subtotal += line_subtotal
            lines.append({
                "part": part, "qty": item.quantity, "unit_price": unit_price,
                "line_subtotal": line_subtotal,
            })

        subtotal = round(subtotal, 2)

        # ── 1b. Sale-level discount (amount or percent) ───────────────
        disc_type = (data.discount_type or "amount")
        disc_value = max(data.discount_value or 0.0, 0.0)
        if disc_type == "percent":
            disc_value = min(disc_value, 100.0)
            discount_total = round(subtotal * disc_value / 100.0, 2)
        else:
            if disc_value > subtotal:
                raise ValueError(
                    f"Discount (₱{disc_value:,.2f}) cannot exceed the "
                    f"subtotal (₱{subtotal:,.2f}).")
            discount_total = round(disc_value, 2)
        net = round(subtotal - discount_total, 2)

        # Spread the sale-level discount across lines proportionally so the
        # per-line StockOut records (which feed reports/dashboard) stay net of
        # discount. The last line absorbs any rounding remainder.
        allocated = 0.0
        for i, ln in enumerate(lines):
            if discount_total <= 0 or subtotal <= 0:
                ln["alloc_disc"] = 0.0
            elif i == len(lines) - 1:
                ln["alloc_disc"] = round(discount_total - allocated, 2)
            else:
                a = round(discount_total * ln["line_subtotal"] / subtotal, 2)
                ln["alloc_disc"] = a
                allocated += a

        # ── 2. Tax (snapshot of current settings) ─────────────────────
        tax_enabled = bool(cfg.get("tax_enabled"))
        tax_name = cfg.get("tax_name") or "VAT"
        tax_rate = float(cfg.get("tax_rate") or 0.0)
        tax_apply = cfg.get("tax_apply") or "after_discount"
        if tax_enabled and tax_rate > 0:
            taxable = subtotal if tax_apply == "before_discount" else net
        else:
            taxable = net
        tax_amount = round(taxable * tax_rate / 100, 2) if (tax_enabled and tax_rate > 0) else 0.0
        # Service / other fees — flat, untaxed, extra revenue. Accept the new
        # itemized `fees`; fall back to a single legacy "Labor" fee if only
        # labor_amount was sent.
        fee_lines = [{"name": (f.name or "Fee").strip() or "Fee",
                      "amount": round(f.amount or 0.0, 2)}
                     for f in (getattr(data, "fees", None) or [])
                     if (f.amount or 0) > 0]
        if not fee_lines and (getattr(data, "labor_amount", 0.0) or 0) > 0:
            fee_lines = [{"name": "Labor",
                          "amount": round(data.labor_amount, 2)}]
        labor_amount = round(sum(f["amount"] for f in fee_lines), 2)

        if not data.items and labor_amount <= 0:
            raise ValueError("Nothing to sell — add a product or a fee.")

        grand_total = round(net + tax_amount + labor_amount, 2)

        # ── 3. Payment validation ─────────────────────────────────────
        amount_received = round(data.amount_received or 0.0, 2)
        if grand_total < 0:
            raise ValueError("Sale total cannot be negative.")
        if data.payment_method == "Cash":
            if amount_received < grand_total:
                raise ValueError(
                    f"Amount received (₱{amount_received:,.2f}) is less than the "
                    f"total due (₱{grand_total:,.2f}).")
            change_due = round(amount_received - grand_total, 2)
        else:
            # Non-cash: assume exact settlement if nothing entered.
            if amount_received <= 0:
                amount_received = grand_total
            change_due = round(max(amount_received - grand_total, 0.0), 2)

        # ── 4. Persist atomically ─────────────────────────────────────
        try:
            now = datetime.now().isoformat()
            receipt_no = self._next_receipt_no()

            sale = Sale(
                receipt_no=receipt_no, sale_date=now, cashier=cashier,
                payment_method=data.payment_method,
                subtotal=subtotal,
                discount_type=disc_type, discount_value=round(disc_value, 2),
                discount_total=discount_total,
                taxable_amount=round(taxable, 2),
                tax_enabled=1 if tax_enabled else 0,
                tax_name=tax_name, tax_rate=tax_rate, tax_amount=tax_amount,
                labor_amount=labor_amount,
                grand_total=grand_total, amount_received=amount_received,
                change_due=change_due, notes=data.notes,
                receipt_snapshot=json.dumps(self._receipt_snapshot(cfg)),
                created_at=now,
            )
            self.db.add(sale)
            self.db.flush()   # assign sale.id

            from database.models.sale_fee import SaleFee
            for f in fee_lines:
                self.db.add(SaleFee(sale_id=sale.id, name=f["name"],
                                    amount=f["amount"]))

            # Record service/other fees in the audit log (one entry per sale).
            # This is the only audit trail for fee-only sales (no stock-out rows).
            if fee_lines:
                fee_desc = ", ".join(f"{f['name']} ₱{f['amount']:,.2f}"
                                     for f in fee_lines)
                self.db.add(AuditLog(
                    part_id=None, action="POS_FEE", delta=None, user=cashier,
                    reason=f"POS Sale {receipt_no}: fees ₱{labor_amount:,.2f} "
                           f"({fee_desc})",
                    reference_id=sale.id,
                    snapshot=json.dumps({"fees": fee_lines,
                                         "fees_total": labor_amount}),
                    created_at=now,
                ))

            for ln in lines:
                part = ln["part"]
                alloc = ln.get("alloc_disc", 0.0)
                line_net = round(ln["line_subtotal"] - alloc, 2)
                # Mirror StockService.issue_stock: create the stock-out + audit.
                # The allocated share of the sale discount keeps stock_out (and
                # therefore dashboard sales/profit) net of discount.
                disc_pct = round(alloc / ln["line_subtotal"] * 100, 4) \
                    if ln["line_subtotal"] > 0 else 0.0
                gross_profit = round(
                    line_net - (part.unit_cost or 0.0) * ln["qty"], 2)
                so = StockOut(
                    part_id=part.id, quantity=ln["qty"],
                    reason="POS Sale", job_ref=receipt_no,
                    selling_price=ln["unit_price"], discount_pct=disc_pct,
                    discount_amount=alloc, subtotal=ln["line_subtotal"],
                    total_amount=line_net, unit_cost=part.unit_cost or 0.0,
                    gross_profit=gross_profit, issued_by=cashier, issued_at=now,
                )
                self.db.add(so)
                self.db.flush()   # assign so.id

                self.db.add(AuditLog(
                    part_id=part.id, action="STOCK_OUT", delta=-ln["qty"],
                    user=cashier,
                    reason=f"POS Sale {receipt_no}: ₱{line_net:,.2f}",
                    reference_id=so.id,
                    snapshot=json.dumps({
                        "sku": part.sku, "name": part.name,
                        "current_stock": part.current_stock - ln["qty"],
                    }),
                    created_at=now,
                ))

                # SaleItem.line_total is the GROSS line amount (price×qty); the
                # sale-level discount shows as a single line on the receipt.
                # Per-item discount is no longer used (stored 0).
                self.db.add(SaleItem(
                    sale_id=sale.id, part_id=part.id, sku=part.sku, name=part.name,
                    quantity=ln["qty"], unit_price=ln["unit_price"],
                    discount=0.0, line_total=ln["line_subtotal"],
                    unit_cost=part.unit_cost or 0.0, stock_out_id=so.id,
                ))

            self.db.commit()
            self.db.refresh(sale)
            return sale
        except Exception:
            self.db.rollback()
            raise

    # ── Reads (never mutate — safe to call when reprinting) ──────────
    def get_recent_sales(self, limit: int = 100, date_from: str = None,
                         date_to: str = None):
        q = self.db.query(Sale)
        if date_from:
            q = q.filter(Sale.sale_date >= date_from)
        if date_to:
            q = q.filter(Sale.sale_date <= date_to + "T23:59:59.999999")
        return q.order_by(Sale.sale_date.desc()).limit(limit).all()

    def get_sale(self, sale_id: int) -> Sale:
        return self.db.get(Sale, sale_id)

    # ── Void (reverse a mistaken sale) ────────────────────────────────
    def void_sale(self, sale_id: int, user: str = "system") -> str:
        """
        Permanently reverse a POS sale entered by mistake: restore the stock and
        delete the sale, its line items, and their stock-out records.

        Blocked if any customer return is linked to the sale (handle those
        first). This is NOT a refund — use Returns for genuine customer returns.
        Returns the voided receipt number.
        """
        from sqlalchemy import or_
        from database.models.customer_return import CustomerReturn

        sale = self.db.get(Sale, sale_id)
        if not sale:
            raise ValueError(f"Sale {sale_id} not found")

        so_ids = [si.stock_out_id for si in sale.items if si.stock_out_id]

        conds = [CustomerReturn.sale_id == sale_id]
        if so_ids:
            conds.append(CustomerReturn.stock_out_id.in_(so_ids))
        if self.db.query(CustomerReturn).filter(or_(*conds)).first():
            raise ValueError(
                "This sale has customer returns linked to it. Handle those "
                "returns first before voiding the sale.")

        receipt_no = sale.receipt_no

        # Audit each line (stock returns to inventory) and collect the
        # stock-outs to delete.
        stock_outs = []
        for si in sale.items:
            so = self.db.get(StockOut, si.stock_out_id) if si.stock_out_id else None
            if so:
                stock_outs.append(so)
            part = self.db.get(Part, si.part_id)
            if part:
                self.db.add(AuditLog(
                    part_id=part.id, action="VOID_SALE",
                    delta=(si.quantity or 0), user=user,
                    reason=f"Voided sale {receipt_no}",
                    reference_id=sale_id,
                    snapshot=json.dumps({"sku": part.sku, "name": part.name}),
                    created_at=datetime.now().isoformat(),
                ))

        # Audit the reversal of any service/other fees on the sale (mirrors the
        # POS_FEE entry created at checkout). Captured before the cascade delete.
        fee_lines = [{"name": f.name, "amount": f.amount} for f in sale.fees]
        if fee_lines:
            fees_total = round(sum(f["amount"] for f in fee_lines), 2)
            fee_desc = ", ".join(f"{f['name']} ₱{f['amount']:,.2f}"
                                 for f in fee_lines)
            self.db.add(AuditLog(
                part_id=None, action="VOID_SALE", delta=None, user=user,
                reason=f"Voided sale {receipt_no}: fees ₱{fees_total:,.2f} "
                       f"reversed ({fee_desc})",
                reference_id=sale_id,
                snapshot=json.dumps({"fees": fee_lines, "fees_total": fees_total}),
                created_at=datetime.now().isoformat(),
            ))

        # Delete the sale (cascade removes its line items), then the now
        # unreferenced stock-outs so SUM(stock_out) drops and stock is restored.
        self.db.delete(sale)
        self.db.flush()
        for so in stock_outs:
            self.db.delete(so)
        self.db.commit()
        return receipt_no

    def get_sale_detail(self, sale_id: int) -> dict:
        sale = self.db.get(Sale, sale_id)
        if not sale:
            return None
        return self.serialize_sale(sale)

    @staticmethod
    def serialize_sale(sale: Sale) -> dict:
        return {
            "id": sale.id, "receipt_no": sale.receipt_no,
            "sale_date": sale.sale_date, "cashier": sale.cashier,
            "payment_method": sale.payment_method,
            "subtotal": sale.subtotal,
            "discount_type": sale.discount_type or "amount",
            "discount_value": sale.discount_value or 0.0,
            "discount_total": sale.discount_total,
            "taxable_amount": sale.taxable_amount,
            "tax_enabled": bool(sale.tax_enabled), "tax_name": sale.tax_name,
            "tax_rate": sale.tax_rate, "tax_amount": sale.tax_amount,
            "labor_amount": sale.labor_amount or 0.0,
            "fees": [{"name": f.name, "amount": f.amount} for f in sale.fees],
            "grand_total": sale.grand_total, "amount_received": sale.amount_received,
            "change_due": sale.change_due, "notes": sale.notes,
            "receipt_snapshot": sale.receipt_snapshot,
            "items": [{
                "id": it.id, "part_id": it.part_id, "sku": it.sku, "name": it.name,
                "quantity": it.quantity, "unit_price": it.unit_price,
                "discount": it.discount, "line_total": it.line_total,
                "unit_cost": it.unit_cost, "stock_out_id": it.stock_out_id,
            } for it in sale.items],
        }

    # ── Internal ──────────────────────────────────────────────────────
    def _next_receipt_no(self) -> str:
        """Unique, human-readable receipt number: R-YYYYMMDD-#### (per day)."""
        date = datetime.now().strftime("%Y%m%d")
        prefix = f"R-{date}-"
        count = (self.db.query(func.count(Sale.id))
                 .filter(Sale.receipt_no.like(prefix + "%")).scalar()) or 0
        seq = count + 1
        # Guard against collisions (e.g. a deleted/edited row) by bumping seq.
        while self.db.query(Sale.id).filter(
                Sale.receipt_no == f"{prefix}{seq:04d}").first():
            seq += 1
        return f"{prefix}{seq:04d}"

    @staticmethod
    def _receipt_snapshot(cfg: dict) -> dict:
        keys = ("store_name", "store_address", "store_phone", "receipt_footer",
                "show_cashier", "show_sku", "show_tax_breakdown", "paper_size")
        return {k: cfg.get(k) for k in keys}
