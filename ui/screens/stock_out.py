import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from config.themes import COLORS, FONTS
from ui.components.modal import Modal, field_row
from ui.components.data_table import DataTable
from ui.components.toast import Toast
from database.engine import get_session
from database.models.stock_out import StockOut
from core.services.parts_service import PartsService
from core.services.stock_service import StockService
from core.validators.transaction_schema import StockOutCreate
from datetime import date

REASONS = ["Sale", "Job Use", "Damaged / Write-off",
           "Customer Return", "Adjustment", "Other"]


def open_stock_out_modal(parent, preselect_part_id: int = None, on_done=None):
    """Modal for issuing stock out"""
    db = get_session()
    try:
        parts = PartsService(db).get_all()
    finally:
        db.close()

    if not parts:
        messagebox.showinfo(
            "No Parts", "No active parts found.", parent=parent)
        return

    m = Modal(parent, "Issue Stock", width=560, height=660)

    part_names = [f"{p.sku}  —  {p.name}" for p in parts]
    presel_idx = 0
    if preselect_part_id:
        for i, p in enumerate(parts):
            if p.id == preselect_part_id:
                presel_idx = i
                break

    part_var = tk.StringVar(value=part_names[presel_idx])
    qty_var = tk.StringVar(value="1")
    price_var = tk.StringVar(
        value=f"{getattr(parts[presel_idx], 'selling_price', 0):.2f}")
    disc_pct_var = tk.StringVar(value="0")
    reason_var = tk.StringVar(value=REASONS[0])
    jobref_var = tk.StringVar()

    # Part selector
    field_row(m.body, "Part", lambda p: ctk.CTkOptionMenu(
        p, variable=part_var, values=part_names,
        fg_color=COLORS["bg"], button_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"],
        dropdown_fg_color=COLORS["card"], height=36,
        command=lambda _: _on_part_change()), required=True)

    # Quantity, Price, Discount
    trio = ctk.CTkFrame(m.body, fg_color="transparent")
    trio.pack(fill="x", padx=20, pady=(0, 12))
    trio.columnconfigure((0, 1, 2), weight=1)

    for col, (lbl, var, ph) in enumerate([
        ("Quantity", qty_var, "1"),
        ("Selling Price (₱)", price_var, "0.00"),
        ("Discount %", disc_pct_var, "0"),
    ]):
        f = ctk.CTkFrame(trio, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="ew")
        ctk.CTkLabel(f, text=lbl.upper(), font=FONTS["label"], text_color=COLORS["txt3"]).pack(
            anchor="w", pady=(0, 4))
        ctk.CTkEntry(f, textvariable=var, placeholder_text=ph,
                     fg_color=COLORS["bg"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"], height=36).pack(fill="x")

    # Pricing Breakdown Box
    pbox = ctk.CTkFrame(m.body, fg_color=COLORS["bg2"], corner_radius=10,
                        border_width=1, border_color=COLORS["border"])
    pbox.pack(fill="x", padx=20, pady=(0, 10))

    def _price_row(label, color=None):
        r = ctk.CTkFrame(pbox, fg_color="transparent")
        r.pack(fill="x", padx=14, pady=3)
        ctk.CTkLabel(r, text=label, font=FONTS["small"], text_color=COLORS["txt3"], anchor="w").pack(
            side="left")
        lbl = ctk.CTkLabel(
            r, text="₱0.00", font=FONTS["body"], text_color=color or COLORS["txt"], anchor="e")
        lbl.pack(side="right")
        return lbl

    lbl_avail = _price_row("Available Stock")
    lbl_subtotal = _price_row("Subtotal")
    lbl_discount = _price_row("Discount", COLORS["amber"])
    lbl_total = _price_row("Total Amount", COLORS["navy"])
    lbl_cost = _price_row("Cost (internal)", COLORS["txt3"])
    lbl_profit = _price_row("Gross Profit", COLORS["green"])
    lbl_margin = _price_row("Margin %", COLORS["green"])

    stock_preview = ctk.CTkLabel(
        pbox, text="", font=FONTS["small"], text_color=COLORS["txt2"])
    stock_preview.pack(anchor="w", padx=14, pady=(2, 8))

    # Reason
    field_row(m.body, "Reason", lambda p: ctk.CTkOptionMenu(
        p, variable=reason_var, values=REASONS,
        fg_color=COLORS["bg"], button_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"],
        dropdown_fg_color=COLORS["card"], height=36))

    # Job Reference
    field_row(m.body, "Job Reference", lambda p: ctk.CTkEntry(
        p, textvariable=jobref_var, placeholder_text="JOB-XXXX (optional)",
        fg_color=COLORS["bg"], border_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"], height=36))

    err_lbl = ctk.CTkLabel(
        m.body, text="", font=FONTS["small"], text_color=COLORS["red"])
    err_lbl.pack(padx=20, anchor="w", pady=(10, 0))

    # Helper functions
    def _get_part():
        try:
            idx = part_names.index(part_var.get())
            return parts[idx]
        except:
            return parts[0]

    def _on_part_change():
        p = _get_part()
        price_var.set(f"{getattr(p, 'selling_price', 0) or 0:.2f}")
        _update_preview()

    def _update_preview(*_):
        p = _get_part()
        db2 = get_session()
        try:
            current_stock = PartsService(db2).get_by_id(p.id).current_stock
        finally:
            db2.close()

        try:
            qty = max(int(qty_var.get() or 0), 0)
            price = max(float(price_var.get() or 0), 0)
            disc_pct = max(min(float(disc_pct_var.get() or 0), 100), 0)
        except:
            qty = price = disc_pct = 0

        subtotal = price * qty
        discount_amount = subtotal * disc_pct / 100
        total_amount = subtotal - discount_amount
        cost_total = p.unit_cost * qty
        profit = total_amount - cost_total
        margin = (profit / max(cost_total, 0.01)) * 100

        after = current_stock - qty
        stock_color = COLORS["red"] if after < 0 else (
            COLORS["amber"] if after <= getattr(p, 'min_stock', 5) else COLORS["green"])

        lbl_avail.configure(
            text=f"{current_stock} {getattr(p, 'unit', 'pcs')}")
        lbl_subtotal.configure(text=f"₱{subtotal:,.2f}")
        lbl_discount.configure(
            text=f"−₱{discount_amount:,.2f}" if discount_amount > 0 else "—")
        lbl_total.configure(text=f"₱{total_amount:,.2f}")
        lbl_cost.configure(text=f"₱{cost_total:,.2f}")
        lbl_profit.configure(
            text=f"₱{profit:,.2f}", text_color=COLORS["green"] if profit >= 0 else COLORS["red"])
        lbl_margin.configure(
            text=f"{margin:.1f}%", text_color=COLORS["green"] if profit >= 0 else COLORS["red"])

        stock_preview.configure(
            text=f"Stock after: {current_stock} → {max(after, 0)} {getattr(p, 'unit', 'pcs')}",
            text_color=stock_color
        )

    # Make the computation box responsive while typing.
    for _var in (qty_var, price_var, disc_pct_var):
        _var.trace_add("write", _update_preview)

    _update_preview()

    # Confirm button logic
    def confirm():
        err_lbl.configure(text="")
        p = _get_part()

        try:
            qty = int(qty_var.get())
            price = float(price_var.get())
            disc_pct = float(disc_pct_var.get())
        except ValueError:
            err_lbl.configure(
                text="Please enter valid numbers for all fields.")
            return

        if qty <= 0:
            err_lbl.configure(text="Quantity must be greater than 0.")
            return
        if price <= 0:
            err_lbl.configure(text="Selling price must be greater than 0.")
            return
        if not (0 <= disc_pct <= 100):
            err_lbl.configure(text="Discount must be between 0 and 100.")
            return

        schema = StockOutCreate(
            part_id=p.id,
            quantity=qty,
            reason=reason_var.get(),
            job_ref=jobref_var.get().strip() or None,
            selling_price=price,
            discount_pct=disc_pct,
        )

        db3 = get_session()
        try:
            StockService(db3).issue_stock(schema)
            m.destroy()
            if on_done:
                on_done()
            Toast(
                parent, f"Successfully issued {qty}× {p.name}", kind="success")
        except ValueError as e:
            err_lbl.configure(text=str(e))
        except Exception as e:
            err_lbl.configure(text="An unexpected error occurred.")
            print(f"Stock Out Error: {e}")
        finally:
            db3.close()

    m.add_footer_buttons("Cancel", "Confirm Issue", on_confirm=confirm)


def open_modify_stock_out_modal(parent, txn_id: int, on_done=None):
    """Modal for modifying an existing stock out transaction"""
    db = get_session()
    try:
        service = StockService(db)
        txn = db.get(StockOut, txn_id)
        if not txn:
            messagebox.showerror(
                "Error", "Transaction not found.", parent=parent)
            return
        part = txn.part
    finally:
        db.close()

    m = Modal(parent, f"Modify Transaction #{txn_id}", width=560, height=580)

    # Pre-fill variables with existing transaction data
    qty_var = tk.StringVar(value=str(txn.quantity))
    price_var = tk.StringVar(value=f"{txn.selling_price:.2f}")
    disc_pct_var = tk.StringVar(value=f"{txn.discount_pct:.0f}")
    reason_var = tk.StringVar(value=txn.reason or REASONS[0])
    jobref_var = tk.StringVar(value=txn.job_ref or "")

    # Display the Part (Read-only for modification)
    field_row(m.body, "Part", lambda p: ctk.CTkLabel(
        p, text=f"{part.sku} — {part.name}", font=FONTS["body"], text_color=COLORS["txt"], anchor="w"
    ))

    # Quantity, Price, Discount Inputs
    trio = ctk.CTkFrame(m.body, fg_color="transparent")
    trio.pack(fill="x", padx=20, pady=(0, 12))
    trio.columnconfigure((0, 1, 2), weight=1)

    for col, (lbl, var) in enumerate([
        ("Quantity", qty_var),
        ("Selling Price (₱)", price_var),
        ("Discount %", disc_pct_var),
    ]):
        f = ctk.CTkFrame(trio, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="ew")
        ctk.CTkLabel(f, text=lbl.upper(), font=FONTS["label"], text_color=COLORS["txt3"]).pack(
            anchor="w", pady=(0, 4))
        ctk.CTkEntry(f, textvariable=var, fg_color=COLORS["bg"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"], height=36).pack(fill="x")

    # Reason and Job Ref
    field_row(m.body, "Reason", lambda p: ctk.CTkOptionMenu(
        p, variable=reason_var, values=REASONS,
        fg_color=COLORS["bg"], button_color=COLORS["border"], text_color=COLORS["txt"], height=36))

    field_row(m.body, "Job Reference", lambda p: ctk.CTkEntry(
        p, textvariable=jobref_var, fg_color=COLORS["bg"], border_color=COLORS["border"], text_color=COLORS["txt"], height=36))

    err_lbl = ctk.CTkLabel(
        m.body, text="", font=FONTS["small"], text_color=COLORS["red"])
    err_lbl.pack(padx=20, anchor="w", pady=(10, 0))

    def confirm_modify():
        try:
            new_qty = int(qty_var.get())
            new_price = float(price_var.get())
            new_disc = float(disc_pct_var.get())

            if new_qty <= 0 or new_price <= 0 or not (0 <= new_disc <= 100):
                raise ValueError(
                    "Invalid numbers. Check quantity, price, and discount.")

            db3 = get_session()
            StockService(db3).update_stock_out(
                txn_id=txn_id,
                new_quantity=new_qty,
                new_price=new_price,
                new_disc_pct=new_disc,
                new_reason=reason_var.get(),
                new_job_ref=jobref_var.get().strip()
            )
            db3.commit()

            m.destroy()
            if on_done:
                on_done()
            Toast(parent, "Transaction modified successfully.", kind="success")

        except ValueError as e:
            err_lbl.configure(text=str(e))
        except Exception as e:
            err_lbl.configure(text="An error occurred while updating.")
            print(f"Update Error: {e}")
        finally:
            if 'db3' in locals():
                db3.close()

    m.add_footer_buttons("Cancel", "Save Changes", on_confirm=confirm_modify)


# ==================== Full Stock Out Screen ====================
class StockOutScreen(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(
            parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self.app = app
        self._build()

    def _build(self):
        # Top bar
        topbar = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0, height=60)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        ctk.CTkLabel(topbar, text="Stock Out", font=FONTS["title"], text_color=COLORS["txt"]).pack(
            side="left", padx=24, pady=16)

        # Action Buttons Container (Right aligned)
        btn_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        btn_frame.pack(side="right", padx=16, pady=13)

        # 1. Cancel Txn Button
        ctk.CTkButton(btn_frame, text="Cancel Txn",
                      fg_color=COLORS["red"], hover_color="#8B0000",
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=100, height=34,
                      command=self.handle_cancel
                      ).pack(side="left", padx=(0, 10))

        # 2. Modify Button
        ctk.CTkButton(btn_frame, text="Modify",
                      fg_color=COLORS["amber"], hover_color="#CC8400",
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=100, height=34,
                      command=self.handle_modify
                      ).pack(side="left", padx=(0, 10))

        # 3. Issue Stock Button
        ctk.CTkButton(btn_frame, text="↑ Issue Stock",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=130, height=34,
                      command=lambda: open_stock_out_modal(
                          self.app, on_done=self.refresh)
                      ).pack(side="left")

        # Summary
        self._summary_frame = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0, height=52)
        self._summary_frame.pack(fill="x")
        self._summary_frame.pack_propagate(False)
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1).pack(fill="x")

        self._summary_lbl = ctk.CTkLabel(
            self._summary_frame, text="", font=FONTS["body"], text_color=COLORS["txt2"])
        self._summary_lbl.pack(side="left", padx=24, pady=14)

        # Date filter (default = today), on the right of the summary bar.
        self._date_var = tk.StringVar(value=date.today().isoformat())
        date_box = ctk.CTkFrame(self._summary_frame, fg_color="transparent")
        date_box.pack(side="right", padx=20, pady=9)
        ctk.CTkLabel(date_box, text="Date", font=FONTS["small"],
                     text_color=COLORS["txt3"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(date_box, textvariable=self._date_var, placeholder_text="YYYY-MM-DD",
                     fg_color=COLORS["bg2"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["small"],
                     width=112, height=32).pack(side="left")
        for txt, cmd, w in (("All", self._set_all_dates, 45),
                            ("Today", self._set_today, 60),
                            ("Apply", self.refresh, 58)):
            ctk.CTkButton(date_box, text=txt, fg_color=COLORS["bg2"],
                          hover_color=COLORS["border"], text_color=COLORS["txt2"],
                          font=FONTS["small"], width=w, height=32,
                          command=cmd).pack(side="left", padx=(6, 0))

        # Table
        COLS = [
            {"id": "date", "label": "Date / Time", "width": 145, "stretch": False},
            {"id": "sku", "label": "SKU", "width": 120, "stretch": False},
            {"id": "part", "label": "Part Name", "width": 190},
            {"id": "qty", "label": "Qty", "width": 55,
                "stretch": False, "anchor": "center"},
            {"id": "returned", "label": "Returned", "width": 80,
                "stretch": False, "anchor": "center"},
            {"id": "price", "label": "Unit Price",
                "width": 95, "stretch": False, "anchor": "e"},
            {"id": "disc", "label": "Disc %", "width": 65,
                "stretch": False, "anchor": "center"},
            {"id": "disc_amt", "label": "Disc Amt",
                "width": 90, "stretch": False, "anchor": "e"},
            {"id": "subtotal", "label": "Subtotal",
                "width": 95, "stretch": False, "anchor": "e"},
            {"id": "total", "label": "Total", "width": 100,
                "stretch": False, "anchor": "e"},
            {"id": "profit", "label": "Profit", "width": 95,
                "stretch": False, "anchor": "e"},
            {"id": "reason", "label": "Reason", "width": 130, "stretch": False},
            {"id": "jobref", "label": "Job Ref", "width": 110, "stretch": False},
        ]

        tbl_frame = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0)
        tbl_frame.pack(fill="both", expand=True)

        self.table = DataTable(tbl_frame, COLS, height=26)
        self.table.pack(fill="both", expand=True)

        self.refresh()

    def _selected_date(self):
        v = self._date_var.get().strip()
        if not v:
            return None
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            Toast(self.app, "Use date format YYYY-MM-DD", kind="error")
            return None

    def _set_today(self):
        self._date_var.set(date.today().isoformat())
        self.refresh()

    def _set_all_dates(self):
        self._date_var.set("")
        self.refresh()

    def refresh(self):
        db = get_session()
        try:
            d = self._selected_date()
            kw = {"date_from": d, "date_to": d} if d else {}
            history = StockService(db).get_stock_out_history(limit=500, **kw)

            # Units of each sale that have been returned (for the Returned column).
            from database.models.customer_return import CustomerReturn
            from sqlalchemy import func
            ret_map = dict(
                db.query(CustomerReturn.stock_out_id,
                         func.sum(CustomerReturn.quantity))
                .filter(CustomerReturn.stock_out_id.isnot(None))
                .group_by(CustomerReturn.stock_out_id).all()
            )

            # Tax factor per POS-linked stock-out (grand_total / net) so the
            # Total can show the tax-inclusive amount the customer paid; the
            # per-line tax-inclusive totals sum exactly to each receipt.
            from database.models.sale_item import SaleItem
            from database.models.sale import Sale
            tax_factor = {}
            for so_id, gt, sub, disc in db.query(
                    SaleItem.stock_out_id, Sale.grand_total, Sale.subtotal,
                    Sale.discount_total).join(
                    Sale, SaleItem.sale_id == Sale.id).filter(
                    SaleItem.stock_out_id.isnot(None)).all():
                net = (sub or 0) - (disc or 0)
                if so_id and net > 0 and gt:
                    tax_factor[so_id] = gt / net

            rows = []
            total_sales = 0.0
            total_profit = 0.0

            for t in history:
                returned = int(ret_map.get(t.id, 0) or 0)
                qty = t.quantity or 0
                # Net the money columns by the units that were returned, so the
                # row reflects what was actually kept (e.g. 5 sold, 1 returned →
                # totals for 4).
                if returned > 0:
                    net_qty = max(qty - returned, 0)
                    sp = t.selling_price or 0
                    uc = t.unit_cost or 0
                    dpct = t.discount_pct or 0
                    net_subtotal = round(sp * net_qty, 2)
                    net_discount = round(net_subtotal * dpct / 100, 2)
                    net_total = round(net_subtotal - net_discount, 2)
                    net_profit = round(net_total - uc * net_qty, 2)
                else:
                    net_subtotal = t.subtotal or 0
                    net_discount = t.discount_amount or 0
                    net_total = t.total_amount or 0
                    net_profit = t.gross_profit or 0

                # Tax-inclusive total shown in the list (matches the receipt);
                # profit stays ex-tax (tax is not profit).
                disp_total = round(net_total * tax_factor.get(t.id, 1.0), 2)

                total_sales += disp_total
                total_profit += net_profit

                tag = "warn" if net_profit < 0 else ""
                if returned > 0 and returned >= qty:
                    tag = "low"   # fully returned — make it stand out
                rows.append({
                    "id": t.id,
                    "_tag": tag,
                    "values": (
                        t.issued_at[:19].replace(
                            "T", "  ") if t.issued_at else "—",
                        t.part.sku if t.part else "—",
                        t.part.name if t.part else "—",
                        str(t.quantity),
                        str(returned) if returned else "—",
                        f"₱{t.selling_price:,.2f}" if t.selling_price is not None else "—",
                        f"{t.discount_pct:.0f}%" if t.discount_pct is not None else "—",
                        f"₱{net_discount:,.2f}",
                        f"₱{net_subtotal:,.2f}",
                        f"₱{disp_total:,.2f}",
                        f"₱{net_profit:,.2f}",
                        t.reason,
                        t.job_ref or "—",
                    )
                })
        finally:
            db.close()

        self.table.load(rows)
        n = len(rows)
        self._summary_lbl.configure(
            text=f"{n} transactions  ·  Total Sales: ₱{total_sales:,.2f}  ·  Total Profit: ₱{total_profit:,.2f}"
        )

    def _get_selected_txn_id(self):
        """Helper to safely get the selected ID from the DataTable"""
        # We now use the exact method from your data_table.py
        selected_iid = self.table.get_selected_iid()

        if not selected_iid:
            messagebox.showwarning(
                "No Selection", "Please select a transaction from the table first.", parent=self)
            return None

        # The Treeview uses strings for IDs, so we convert it back to an integer
        return int(selected_iid)

    def handle_modify(self):
        txn_id = self._get_selected_txn_id()
        if txn_id:
            open_modify_stock_out_modal(
                self.app, txn_id=txn_id, on_done=self.refresh)

    def handle_cancel(self):
        txn_id = self._get_selected_txn_id()
        if not txn_id:
            return

        confirm = messagebox.askyesno(
            "Confirm Cancel",
            f"Are you sure you want to completely cancel transaction #{txn_id}?\n\nThis will restore the stock to inventory.",
            parent=self
        )

        if confirm:
            db = get_session()
            try:
                StockService(db).cancel_stock_out(txn_id=txn_id)
                self.refresh()
                Toast(
                    self.app, "Transaction cancelled and stock restored.", kind="success")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to cancel: {e}", parent=self)
            finally:
                db.close()
