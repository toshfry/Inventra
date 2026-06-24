import tkinter as tk
import customtkinter as ctk
from config.themes import COLORS, FONTS
from database.engine import get_session
from core.services.return_service import (
    ReturnService, REASONS, CONDITIONS, REFUND_METHODS)
from core.services.parts_service import PartsService
from core.services.dashboard_service import DashboardService
from core.validators.return_schema import ReturnCreate
from core.services.auth_service import get_current_user
from ui.components.data_table import DataTable
from ui.components.toast import Toast


def _current_user():
    try:
        u = get_current_user()
        return u.username if u else "system"
    except Exception:
        return "system"


class ReturnsScreen(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self.app = app
        self._build()

    def _build(self):
        topbar = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=60)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        wrap = ctk.CTkFrame(topbar, fg_color="transparent")
        wrap.pack(side="left", padx=24, pady=10)
        ctk.CTkLabel(wrap, text="Returns", font=FONTS["title"],
                     text_color=COLORS["txt"]).pack(anchor="w")
        ctk.CTkLabel(wrap, text="Process customer returns & refunds",
                     font=FONTS["small"], text_color=COLORS["txt3"]).pack(anchor="w")

        ctk.CTkButton(topbar, text="↩  Return from Sale",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"], width=170, height=36,
                      command=self._return_from_sale).pack(side="right", padx=(0, 16), pady=12)
        ctk.CTkButton(topbar, text="+  New Return (no receipt)",
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"], font=FONTS["body"], width=200, height=36,
                      command=self._new_blind).pack(side="right", padx=(0, 8), pady=12)

        body = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        body.pack(fill="both", expand=True)
        ctk.CTkLabel(body, text="RECENT RETURNS", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", padx=20, pady=(14, 6))

        COLS = [
            {"id": "ts",     "label": "Date / Time", "width": 140, "stretch": False},
            {"id": "sku",    "label": "SKU",         "width": 120, "stretch": False},
            {"id": "name",   "label": "Part",        "width": 190},
            {"id": "qty",    "label": "Qty",         "width": 50,  "stretch": False, "anchor": "center"},
            {"id": "cond",   "label": "Condition",   "width": 95,  "stretch": False},
            {"id": "reason", "label": "Reason",      "width": 130, "stretch": False},
            {"id": "refund", "label": "Refund",      "width": 100, "stretch": False, "anchor": "e"},
            {"id": "method", "label": "Method",      "width": 90,  "stretch": False},
            {"id": "user",   "label": "By",          "width": 90,  "stretch": False},
        ]
        self._table = DataTable(body, COLS, height=18)
        self._table.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self.refresh()

    def refresh(self):
        db = get_session()
        try:
            rows = ReturnService(db).get_history(limit=200)
            data = [{
                "id": r.id,
                "ts": (r.created_at or "")[:19].replace("T", "  "),
                "sku": r.part.sku if r.part else "—",
                "name": r.part.name if r.part else "—",
                "qty": r.quantity, "cond": CONDITIONS.get(r.condition, r.condition),
                "reason": REASONS.get(r.reason_code, r.reason_code),
                "refund": f"₱{r.refund_amount:,.2f}", "method": r.refund_method,
                "user": r.user,
            } for r in rows]
        finally:
            db.close()
        self._table.load([{"id": d["id"], "values": (
            d["ts"], d["sku"], d["name"], d["qty"], d["cond"], d["reason"],
            d["refund"], d["method"], d["user"])} for d in data])

    def _new_blind(self):
        def load(search):
            db = get_session()
            try:
                rows = PartsService(db).get_stock_view(search=search)
            finally:
                db.close()
            return [{
                "id": r["id"],
                "values": (r["sku"], r["name"], r.get("current_stock", 0),
                           f"₱{r.get('selling_price', 0):,.2f}"),
                "_row": {"part_id": r["id"], "sku": r["sku"], "name": r["name"],
                         "unit_price": r.get("selling_price", 0) or 0,
                         "unit_cost": r.get("unit_cost", 0) or 0,
                         "stock_out_id": None, "sale_id": None,
                         "receipt_no": None, "remaining": None},
            } for r in rows]

        _PickerDialog(
            self, title="Pick a part to return",
            columns=[
                {"id": "sku", "label": "SKU", "width": 140, "stretch": False},
                {"id": "name", "label": "Part Name", "width": 240},
                {"id": "stock", "label": "Stock", "width": 70, "stretch": False, "anchor": "center"},
                {"id": "price", "label": "Price", "width": 100, "stretch": False, "anchor": "e"},
            ],
            load_fn=load,
            on_select=lambda row: _ReturnFormDialog(
                self, self.app, row["_row"], on_done=self.refresh))

    def _return_from_sale(self):
        def load(search):
            db = get_session()
            try:
                issues = ReturnService(db).get_returnable_issues(search=search, limit=200)
            finally:
                db.close()
            return [{
                "id": it["stock_out_id"],
                "values": ((it["issued_at"] or "")[:19].replace("T", "  "),
                           it["receipt_no"] or "—", it["sku"], it["name"],
                           f"{it['remaining']}/{it['sold_qty']}",
                           f"₱{it['unit_price']:,.2f}"),
                "_row": {"part_id": it["part_id"], "sku": it["sku"], "name": it["name"],
                         "unit_price": it["unit_price"], "unit_cost": it["unit_cost"],
                         "stock_out_id": it["stock_out_id"], "sale_id": it["sale_id"],
                         "receipt_no": it["receipt_no"], "remaining": it["remaining"]},
            } for it in issues]

        _PickerDialog(
            self, title="Pick a sale / issue to return",
            columns=[
                {"id": "ts", "label": "Date", "width": 140, "stretch": False},
                {"id": "rcpt", "label": "Receipt", "width": 110, "stretch": False},
                {"id": "sku", "label": "SKU", "width": 120, "stretch": False},
                {"id": "name", "label": "Part", "width": 200},
                {"id": "rem", "label": "Returnable", "width": 90, "stretch": False, "anchor": "center"},
                {"id": "price", "label": "Price", "width": 100, "stretch": False, "anchor": "e"},
            ],
            load_fn=load,
            on_select=lambda row: _ReturnFormDialog(
                self, self.app, row["_row"], on_done=self.refresh))


class _PickerDialog(ctk.CTkToplevel):
    """Generic search + table picker. load_fn(search) -> list of {id, values, _row}."""

    def __init__(self, parent, title, columns, load_fn, on_select):
        super().__init__(parent)
        self._load_fn = load_fn
        self._on_select = on_select
        self._rows_by_id = {}
        self.title(title)
        self.geometry("720x520")
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.lift()
        self.focus_force()
        self._centre(parent)

        hdr = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=title, font=FONTS["heading"],
                     text_color=COLORS["txt"]).pack(side="left", padx=20, pady=15)
        # Native title-bar close only (no redundant custom ✕).

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=16, pady=10)
        self._search = tk.StringVar()
        ent = ctk.CTkEntry(bar, textvariable=self._search,
                           placeholder_text="🔍  Search by name or SKU…",
                           fg_color=COLORS["card"], border_color=COLORS["border"],
                           text_color=COLORS["txt"], font=FONTS["body"], height=34)
        ent.pack(fill="x")
        self._search.trace_add("write", lambda *_: self._reload())

        self._table = DataTable(self, columns, height=14,
                                on_double_click=self._choose)
        self._table.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        ctk.CTkButton(self, text="Select", width=120, height=36,
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF",
                      command=lambda: self._choose(self._table.get_selected_iid())
                      ).pack(side="bottom", anchor="e", padx=16, pady=(0, 14))
        self._reload()

    def _centre(self, parent):
        self.update_idletasks()
        w, h = 720, 520
        try:
            px = parent.winfo_rootx() + parent.winfo_width() // 2
            py = parent.winfo_rooty() + parent.winfo_height() // 2
        except Exception:
            px, py = 700, 450
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    def _reload(self):
        rows = self._load_fn(self._search.get().strip())
        self._rows_by_id = {str(r["id"]): r for r in rows}
        self._table.load([{"id": r["id"], "values": r["values"]} for r in rows])

    def _choose(self, iid):
        if iid is None:
            return
        row = self._rows_by_id.get(str(iid))
        if not row:
            return
        self.destroy()
        self._on_select(row)


class _ReturnFormDialog(ctk.CTkToplevel):
    """The actual return form. row carries part + optional linked-sale info."""

    def __init__(self, parent, app, row, on_done=None):
        super().__init__(parent)
        self.app = app
        self.row = row
        self.on_done = on_done
        self.title("Process Return")
        self.geometry("460x560")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.lift()
        self.focus_force()
        self._centre(parent)

        self._qty = tk.StringVar(value="1")
        self._condition = tk.StringVar(value="RESELLABLE")
        self._reason = tk.StringVar(value=list(REASONS.values())[0])
        self._refund = tk.StringVar(value="")
        self._method = tk.StringVar(value=REFUND_METHODS[0])
        self._note = tk.StringVar(value="")
        self._build()
        self._prefill_refund()

    def _centre(self, parent):
        self.update_idletasks()
        w, h = 460, 560
        try:
            px = parent.winfo_rootx() + parent.winfo_width() // 2
            py = parent.winfo_rooty() + parent.winfo_height() // 2
        except Exception:
            px, py = 640, 400
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Process Return", font=FONTS["heading"],
                     text_color=COLORS["txt"]).pack(side="left", padx=20, pady=15)
        # Native title-bar close only (no redundant custom ✕).

        footer = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=58)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkButton(footer, text="Cancel", width=100, fg_color=COLORS["bg2"],
                      text_color=COLORS["txt"], hover_color=COLORS["border"],
                      command=self.destroy).pack(side="right", padx=10, pady=11)
        ctk.CTkButton(footer, text="Process Return", width=160,
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", command=self._submit).pack(
            side="right", padx=(0, 4), pady=11)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=14)

        ctk.CTkLabel(body, text=f"{self.row['name']}   ·   {self.row['sku']}",
                     font=FONTS["body"], text_color=COLORS["txt"], anchor="w").pack(fill="x")
        if self.row.get("remaining") is not None:
            sub = f"Linked sale — up to {self.row['remaining']} returnable"
            if self.row.get("receipt_no"):
                sub += f"  ·  Receipt {self.row['receipt_no']}"
        else:
            sub = "No receipt (blind return)"
        ctk.CTkLabel(body, text=sub, font=FONTS["small"],
                     text_color=COLORS["txt3"], anchor="w").pack(fill="x", pady=(2, 12))

        def label(t):
            ctk.CTkLabel(body, text=t, font=FONTS["label"],
                         text_color=COLORS["txt3"]).pack(anchor="w", pady=(6, 2))

        label("QUANTITY")
        qe = ctk.CTkEntry(body, textvariable=self._qty, height=34,
                          fg_color=COLORS["bg2"], border_color=COLORS["border"],
                          text_color=COLORS["txt"], font=FONTS["body"])
        qe.pack(fill="x")
        self._qty.trace_add("write", lambda *_: self._prefill_refund())

        label("CONDITION")
        crow = ctk.CTkFrame(body, fg_color="transparent")
        crow.pack(fill="x")
        ctk.CTkRadioButton(crow, text="Resellable (restock)", variable=self._condition,
                           value="RESELLABLE", fg_color=COLORS["navy"],
                           text_color=COLORS["txt"], font=FONTS["body"]).pack(side="left", padx=(0, 14))
        ctk.CTkRadioButton(crow, text="Damaged (scrap)", variable=self._condition,
                           value="DAMAGED", fg_color=COLORS["navy"],
                           text_color=COLORS["txt"], font=FONTS["body"]).pack(side="left")

        label("REASON")
        ctk.CTkOptionMenu(body, variable=self._reason, values=list(REASONS.values()),
                          fg_color=COLORS["bg2"], button_color=COLORS["border"],
                          text_color=COLORS["txt"], font=FONTS["body"],
                          dropdown_fg_color=COLORS["card"], height=34).pack(fill="x")

        label("REFUND AMOUNT (₱)")
        ctk.CTkEntry(body, textvariable=self._refund, height=34,
                     fg_color=COLORS["bg2"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"]).pack(fill="x")

        label("REFUND METHOD")
        ctk.CTkOptionMenu(body, variable=self._method, values=REFUND_METHODS,
                          fg_color=COLORS["bg2"], button_color=COLORS["border"],
                          text_color=COLORS["txt"], font=FONTS["body"],
                          dropdown_fg_color=COLORS["card"], height=34).pack(fill="x")

        label("NOTE (optional)")
        ctk.CTkEntry(body, textvariable=self._note, height=34,
                     fg_color=COLORS["bg2"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"]).pack(fill="x")

    def _qty_int(self):
        try:
            return int(self._qty.get().strip())
        except (TypeError, ValueError):
            return None

    def _prefill_refund(self):
        q = self._qty_int()
        if q is None or q <= 0:
            return
        self._refund.set(f"{round(self.row['unit_price'] * q, 2)}")

    def _reason_code(self):
        label = self._reason.get()
        for code, lbl in REASONS.items():
            if lbl == label:
                return code
        return "OTHER"

    def _submit(self):
        from tkinter import messagebox
        q = self._qty_int()
        if q is None or q <= 0:
            messagebox.showerror("Invalid", "Enter a valid quantity.", parent=self)
            return
        try:
            refund = float(self._refund.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Invalid", "Enter a valid refund amount.", parent=self)
            return

        try:
            data = ReturnCreate(
                part_id=self.row["part_id"],
                stock_out_id=self.row.get("stock_out_id"),
                sale_id=self.row.get("sale_id"),
                quantity=q, condition=self._condition.get(),
                reason_code=self._reason_code(), refund_amount=refund,
                refund_method=self._method.get(),
                note=self._note.get().strip() or None)
        except Exception as e:
            messagebox.showerror("Invalid", str(e), parent=self)
            return

        db = get_session()
        try:
            ReturnService(db).process_return(data, user=_current_user())
            DashboardService(db).invalidate()
        except Exception as e:
            messagebox.showerror("Cannot Process Return", str(e), parent=self)
            return
        finally:
            db.close()

        Toast(self.app, "Return processed.", kind="success")
        if self.on_done:
            self.on_done()
        self.destroy()
