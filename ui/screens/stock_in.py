import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from config.themes import COLORS, FONTS
from ui.components.modal import Modal, field_row
from ui.components.data_table import DataTable
from ui.components.toast import Toast
from database.engine import get_session
from database.models.stock_in import StockIn
from core.services.parts_service import PartsService
from core.services.stock_service import StockService
from core.services.supplier_service import SupplierService
from core.validators.transaction_schema import StockInCreate
from datetime import date


def open_stock_in_modal(parent, preselect_part_id: int = None, on_done=None):
    """Open the receive-stock modal. Can be called from anywhere."""
    db = get_session()
    try:
        parts = PartsService(db).get_all()
        suppliers = SupplierService(db).get_all()
    finally:
        db.close()

    if not parts:
        messagebox.showinfo(
            "No Parts", "Add at least one part before receiving stock.", parent=parent)
        return

    m = Modal(parent, "Receive Stock", width=520, height=520)

    part_names = [f"{p.sku}  —  {p.name}" for p in parts]
    sup_names = ["(None)"] + [s.name for s in suppliers]

    presel_idx = 0
    if preselect_part_id:
        for i, p in enumerate(parts):
            if p.id == preselect_part_id:
                presel_idx = i
                break

    part_var = tk.StringVar(value=part_names[presel_idx])
    sup_var = tk.StringVar(value="(None)")
    qty_var = tk.StringVar(value="1")
    cost_var = tk.StringVar(
        value=f"{(getattr(parts[presel_idx], 'unit_cost', 0) or 0):.2f}")
    ref_var = tk.StringVar()
    notes_var = tk.StringVar()

    # --- DEFINE PREVIEW LOGIC FIRST ---
    def _get_selected_part():
        idx = part_names.index(
            part_var.get()) if part_var.get() in part_names else 0
        return parts[idx]

    def _set_default_cost_from_part():
        p = _get_selected_part()
        cost_var.set(f"{(getattr(p, 'unit_cost', 0) or 0):.2f}")

    def _update_preview(*_):
        p = _get_selected_part()
        try:
            qty = int(qty_var.get())
        except ValueError:
            qty = 0

        cur = p.current_stock
        after = cur + qty
        unit = getattr(p, 'unit', 'pcs')
        default_cost = getattr(p, 'unit_cost', 0) or 0

        preview_lbl.configure(
            text=f"Current stock:  {cur} {unit}    →    After receipt:  {after} {unit}    |    Default cost: ₱{default_cost:,.2f}"
        )

    # --- BUILD UI ---
    field_row(m.body, "Part", lambda p: ctk.CTkOptionMenu(
        p, variable=part_var, values=part_names,
        fg_color=COLORS["bg"], button_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"],
        dropdown_fg_color=COLORS["card"],
        height=36, command=lambda _: (_set_default_cost_from_part(), _update_preview())), required=True)

    field_row(m.body, "Supplier", lambda p: ctk.CTkOptionMenu(
        p, variable=sup_var, values=sup_names,
        fg_color=COLORS["bg"], button_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"],
        dropdown_fg_color=COLORS["card"], height=36))

    row2 = ctk.CTkFrame(m.body, fg_color="transparent")
    row2.pack(fill="x", padx=20, pady=(0, 12))
    row2.columnconfigure(0, weight=1)
    row2.columnconfigure(1, weight=1)

    for col, (lbl, var, ph) in enumerate([("Quantity *", qty_var, "1"), ("Unit Cost (₱)", cost_var, "0.00")]):
        f = ctk.CTkFrame(row2, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="ew")
        ctk.CTkLabel(f, text=lbl.upper(), font=FONTS["label"], text_color=COLORS["txt3"]).pack(
            anchor="w", pady=(0, 4))
        e = ctk.CTkEntry(f, textvariable=var, fg_color=COLORS["bg"],
                         border_color=COLORS["border"], text_color=COLORS["txt"],
                         font=FONTS["body"], height=36)
        e.pack(fill="x")

        if var == qty_var:
            var.trace_add("write", _update_preview)

    field_row(m.body, "Reference No.", lambda p: ctk.CTkEntry(
        p, textvariable=ref_var, placeholder_text="PO / delivery note",
        fg_color=COLORS["bg"], border_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"], height=36))

    # Preview box
    preview = ctk.CTkFrame(m.body, fg_color=COLORS["bg2"],
                           corner_radius=8, border_width=1,
                           border_color=COLORS["border"])
    preview.pack(fill="x", padx=20, pady=(0, 8))
    preview_lbl = ctk.CTkLabel(preview, text="",
                               font=FONTS["body"],
                               text_color=COLORS["txt2"])
    preview_lbl.pack(padx=14, pady=10, anchor="w")

    err_lbl = ctk.CTkLabel(m.body, text="", font=FONTS["small"],
                           text_color=COLORS["red"])
    err_lbl.pack(padx=20, anchor="w")

    _update_preview()  # Initial call to set text

    def confirm():
        err_lbl.configure(text="")
        p = _get_selected_part()
        try:
            qty = int(qty_var.get())
            cost = float(cost_var.get())
        except ValueError:
            err_lbl.configure(
                text="Quantity must be a whole number; cost must be a number.")
            return
        if qty <= 0:
            err_lbl.configure(text="Quantity must be greater than 0.")
            return

        sup_obj = next((s for s in suppliers if s.name == sup_var.get()), None)
        schema = StockInCreate(
            part_id=p.id,
            supplier_id=sup_obj.id if sup_obj else None,
            quantity=qty,
            unit_cost=cost,
            reference_no=ref_var.get().strip() or None,
            notes=notes_var.get().strip() or None,
        )
        db3 = get_session()
        try:
            StockService(db3).receive_stock(schema)
        except ValueError as e:
            err_lbl.configure(text=str(e))
            return
        finally:
            db3.close()

        m.destroy()
        if on_done:
            on_done()
        Toast(parent, f"Received {qty}× {p.name}.", kind="success")

    m.add_footer_buttons("Cancel", "Confirm Receipt", on_confirm=confirm)


def open_modify_stock_in_modal(parent, txn_id: int, on_done=None):
    """Modal for modifying an existing stock in transaction"""
    db = get_session()
    try:
        service = StockService(db)
        txn = db.get(StockIn, txn_id)
        if not txn:
            messagebox.showerror(
                "Error", "Transaction not found.", parent=parent)
            return

        part = txn.part
        suppliers = SupplierService(db).get_all()

        # --- EXTRACT ALL DATA HERE BEFORE CLOSING DB ---
        # This prevents DetachedInstanceErrors!
        base_stock = part.current_stock
        part_sku = part.sku
        part_name = part.name
        part_unit = getattr(part, 'unit', 'pcs')

        old_qty = txn.quantity
        old_cost = txn.unit_cost
        old_ref = txn.reference_no or ""
        current_sup_name = txn.supplier.name if txn.supplier else "(None)"

        # Create a safe dictionary mapping supplier names to IDs
        supplier_map = {s.name: s.id for s in suppliers}
        sup_names = ["(None)"] + list(supplier_map.keys())

    except Exception as e:
        messagebox.showerror(
            "Error", f"Failed to load transaction details.\n{e}", parent=parent)
        return
    finally:
        db.close()

    m = Modal(parent, f"Modify Receive Stock #{txn_id}", width=520, height=520)

    # Pre-fill variables
    sup_var = tk.StringVar(value=current_sup_name)
    qty_var = tk.StringVar(value=str(old_qty))
    cost_var = tk.StringVar(value=f"{old_cost:.2f}")
    ref_var = tk.StringVar(value=old_ref)

    # --- DEFINE PREVIEW LOGIC FIRST ---
    def _update_preview(*_):
        try:
            new_qty = int(qty_var.get())
        except ValueError:
            new_qty = 0

        after = base_stock - old_qty + new_qty

        preview_lbl.configure(
            text=f"Current stock:  {base_stock} {part_unit}    →    After adjust:  {after} {part_unit}"
        )

    # --- BUILD UI ---
    # Display Part (Read-only)
    field_row(m.body, "Part", lambda p: ctk.CTkLabel(
        p, text=f"{part_sku} — {part_name}", font=FONTS["body"], text_color=COLORS["txt"], anchor="w"
    ))

    # Supplier Options
    field_row(m.body, "Supplier", lambda p: ctk.CTkOptionMenu(
        p, variable=sup_var, values=sup_names,
        fg_color=COLORS["bg"], button_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"],
        dropdown_fg_color=COLORS["card"], height=36))

    # Quantity & Unit Cost Inputs
    row2 = ctk.CTkFrame(m.body, fg_color="transparent")
    row2.pack(fill="x", padx=20, pady=(0, 12))
    row2.columnconfigure(0, weight=1)
    row2.columnconfigure(1, weight=1)

    for col, (lbl, var) in enumerate([("Quantity *", qty_var), ("Unit Cost (₱)", cost_var)]):
        f = ctk.CTkFrame(row2, fg_color="transparent")
        f.grid(row=0, column=col, padx=(0 if col == 0 else 8, 0), sticky="ew")
        ctk.CTkLabel(f, text=lbl.upper(), font=FONTS["label"], text_color=COLORS["txt3"]).pack(
            anchor="w", pady=(0, 4))

        e = ctk.CTkEntry(f, textvariable=var, fg_color=COLORS["bg"],
                         border_color=COLORS["border"], text_color=COLORS["txt"],
                         font=FONTS["body"], height=36)
        e.pack(fill="x")

        if var == qty_var:
            var.trace_add("write", _update_preview)

    # Reference No.
    field_row(m.body, "Reference No.", lambda p: ctk.CTkEntry(
        p, textvariable=ref_var, fg_color=COLORS["bg"], border_color=COLORS["border"],
        text_color=COLORS["txt"], font=FONTS["body"], height=36))

    # Responsive Real-Time Preview Box
    preview = ctk.CTkFrame(m.body, fg_color=COLORS["bg2"],
                           corner_radius=8, border_width=1,
                           border_color=COLORS["border"])
    preview.pack(fill="x", padx=20, pady=(0, 8))
    preview_lbl = ctk.CTkLabel(preview, text="",
                               font=FONTS["body"],
                               text_color=COLORS["txt2"])
    preview_lbl.pack(padx=14, pady=10, anchor="w")

    _update_preview()  # Initial call

    err_lbl = ctk.CTkLabel(
        m.body, text="", font=FONTS["small"], text_color=COLORS["red"])
    err_lbl.pack(padx=20, anchor="w", pady=(10, 0))

    def confirm_modify():
        try:
            new_qty = int(qty_var.get())
            new_cost = float(cost_var.get())

            if new_qty <= 0 or new_cost < 0:
                raise ValueError(
                    "Quantity must be greater than 0 and cost cannot be negative.")

            # Retrieve the correct ID safely from the dictionary map
            sup_id = supplier_map.get(sup_var.get())

            db3 = get_session()
            StockService(db3).update_stock_in(
                txn_id=txn_id,
                new_quantity=new_qty,
                new_unit_cost=new_cost,
                new_supplier_id=sup_id,
                new_reference_no=ref_var.get().strip() or None
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


# ==================== Full Stock In Screen ====================
class StockInScreen(ctk.CTkFrame):
    """Full screen for Stock In — wraps the history table and actions."""

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

        ctk.CTkLabel(topbar, text="Stock In", font=FONTS["title"], text_color=COLORS["txt"]).pack(
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

        # 3. Receive Stock Button
        ctk.CTkButton(btn_frame, text="↓ Receive Stock",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=140, height=34,
                      command=lambda: open_stock_in_modal(
                          self.app, on_done=self.refresh)
                      ).pack(side="left")

        # Date filter bar (default = today)
        self._date_var = tk.StringVar(value=date.today().isoformat())
        self._build_date_bar()

        # Table Configuration
        COLS = [
            {"id": "date",     "label": "Date / Time",
                "width": 160, "stretch": False},
            {"id": "part",     "label": "Part",          "width": 220},
            {"id": "supplier", "label": "Supplier",
                "width": 160, "stretch": False},
            {"id": "qty",      "label": "Qty",           "width": 70,
                "stretch": False, "anchor": "center"},
            {"id": "cost",     "label": "Unit Cost",
                "width": 100, "stretch": False, "anchor": "e"},
            {"id": "ref",      "label": "Reference",
                "width": 140, "stretch": False},
            {"id": "by",       "label": "Received By",
                "width": 120, "stretch": False},
        ]

        tbl_frame = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0)
        tbl_frame.pack(fill="both", expand=True)

        self.table = DataTable(tbl_frame, COLS, height=28)
        self.table.pack(fill="both", expand=True)

        self.refresh()

    def _build_date_bar(self):
        bar = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=46)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1).pack(fill="x")
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(side="left", padx=24, pady=7)
        ctk.CTkLabel(inner, text="Date", font=FONTS["small"],
                     text_color=COLORS["txt3"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(inner, textvariable=self._date_var, placeholder_text="YYYY-MM-DD",
                     fg_color=COLORS["bg2"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["small"],
                     width=112, height=32).pack(side="left")
        for txt, cmd, w in (("All", self._set_all_dates, 45),
                            ("Today", self._set_today, 60),
                            ("Apply", self.refresh, 58)):
            ctk.CTkButton(inner, text=txt, fg_color=COLORS["bg2"],
                          hover_color=COLORS["border"], text_color=COLORS["txt2"],
                          font=FONTS["small"], width=w, height=32,
                          command=cmd).pack(side="left", padx=(6, 0))

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
            history = StockService(db).get_stock_in_history(limit=200, **kw)
            rows = []
            for t in history:
                rows.append({"id": t.id, "values": (
                    t.received_at[:19].replace(
                        "T", "  ") if t.received_at else "—",
                    t.part.name if t.part else "—",
                    t.supplier.name if t.supplier else "—",
                    str(t.quantity),
                    f"₱{t.unit_cost:,.2f}",
                    t.reference_no or "—",
                    t.received_by or "—",
                )})
        finally:
            db.close()
        self.table.load(rows)

    def _get_selected_txn_id(self):
        """Helper to safely get the selected ID from the DataTable"""
        selected_iid = self.table.get_selected_iid()

        if not selected_iid:
            messagebox.showwarning(
                "No Selection", "Please select a transaction from the table first.", parent=self)
            return None

        # Return it as an integer matching the database ID
        return int(selected_iid)

    def handle_modify(self):
        """Trigger the modal to adjust existing stock-in entry"""
        txn_id = self._get_selected_txn_id()
        if txn_id:
            open_modify_stock_in_modal(
                self.app, txn_id=txn_id, on_done=self.refresh)

    def handle_cancel(self):
        """Trigger cancellation of the stock-in entry"""
        txn_id = self._get_selected_txn_id()
        if not txn_id:
            return

        confirm = messagebox.askyesno(
            "Confirm Cancel",
            f"Are you sure you want to completely cancel Stock In transaction #{txn_id}?\n\nThis will remove the received quantity from inventory.",
            parent=self
        )

        if confirm:
            db = get_session()
            try:
                StockService(db).cancel_stock_in(txn_id=txn_id)
                self.refresh()
                Toast(
                    self.app, "Transaction cancelled and inventory reversed.", kind="success")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to cancel: {e}", parent=self)
            finally:
                db.close()
