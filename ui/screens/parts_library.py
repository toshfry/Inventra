import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from config.themes import COLORS, FONTS
from ui.components.data_table import DataTable
from ui.components.modal import Modal
from ui.components.responsive import Debouncer
from ui.components.toast import Toast
from database.engine import get_session
from core.services.parts_service import PartsService
from core.services.auth_service import is_admin, current_username
from core.validators.part_schema import PartCreate, PartUpdate
from database.models.category import Category


def _lbl(parent, text, required=False):
    t = text.upper() + (" *" if required else "")
    ctk.CTkLabel(parent, text=t, font=FONTS["label"],
                 text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))


def _entry(parent, var, placeholder="", height=36):
    return ctk.CTkEntry(parent, textvariable=var,
                        placeholder_text=placeholder,
                        fg_color=COLORS["bg"],
                        border_color=COLORS["border"],
                        text_color=COLORS["txt"],
                        font=FONTS["body"], height=height)


def _field(parent, label, var, placeholder="", required=False, pady=(0, 12)):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill="x", padx=24, pady=pady)
    _lbl(f, label, required)
    e = _entry(f, var, placeholder)
    e.pack(fill="x")
    return e


def _option(parent, label, var, values, pady=(0, 12)):
    f = ctk.CTkFrame(parent, fg_color="transparent")
    f.pack(fill="x", padx=24, pady=pady)
    _lbl(f, label)
    m = ctk.CTkOptionMenu(f, variable=var, values=values,
                          fg_color=COLORS["bg"],
                          button_color=COLORS["border"],
                          button_hover_color=COLORS["bg2"],
                          text_color=COLORS["txt"],
                          dropdown_fg_color=COLORS["card"],
                          font=FONTS["body"], height=36)
    m.pack(fill="x")
    return m


class PartsLibraryScreen(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(
            parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self.app = app
        self._search_var = tk.StringVar()
        self._cat_var = tk.StringVar(value="All Categories")
        self._categories = []
        self._low_only = False
        self._search_debounce = Debouncer(self, delay_ms=180)
        self._build()

    def _build(self):
        # Top bar
        topbar = ctk.CTkFrame(self, fg_color=COLORS["card"],
                              corner_radius=0, height=60)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Parts Library",
                     font=FONTS["title"],
                     text_color=COLORS["txt"]).pack(side="left", padx=24, pady=16)

        if is_admin():
            ctk.CTkButton(topbar, text="+ Add Part",
                          fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                          text_color="#FFFFFF", font=FONTS["body"],
                          width=110, height=34,
                          command=self._open_add_modal).pack(side="right", padx=16, pady=13)

        # Filter bar
        fbar = ctk.CTkFrame(self, fg_color=COLORS["card"],
                            corner_radius=0, height=52)
        fbar.pack(fill="x")
        ctk.CTkFrame(self, fg_color=COLORS["border"], height=1).pack(fill="x")

        fi = ctk.CTkFrame(fbar, fg_color="transparent")
        fi.pack(fill="x", padx=20, pady=8)

        ctk.CTkEntry(fi, textvariable=self._search_var,
                     placeholder_text="🔍  Search by name, SKU, location…",
                     fg_color=COLORS["bg"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"],
                     height=34, width=320).pack(side="left", padx=(0, 12))
        self._search_var.trace_add(
            "write", lambda *_: self._search_debounce.call(self.refresh))

        self._cat_menu = ctk.CTkOptionMenu(
            fi, variable=self._cat_var, values=["All Categories"],
            fg_color=COLORS["bg"], button_color=COLORS["border"],
            button_hover_color=COLORS["bg2"], text_color=COLORS["txt"],
            dropdown_fg_color=COLORS["card"], font=FONTS["body"],
            width=160, height=34,
            command=lambda _: self.refresh())
        self._cat_menu.pack(side="left")

        # One-click filter: show only parts at or below their minimum stock.
        self._low_btn = ctk.CTkButton(
            fi, text="⚠  Low Stock", font=FONTS["body"],
            fg_color=COLORS["bg2"], hover_color=COLORS["border"],
            text_color=COLORS["txt2"], width=120, height=34,
            command=self._toggle_low)
        self._low_btn.pack(side="left", padx=(10, 0))

        self._count_lbl = ctk.CTkLabel(fi, text="", font=FONTS["small"],
                                       text_color=COLORS["txt3"])
        self._count_lbl.pack(side="right")

        # Table
        COLS = [
            {"id": "sku",      "label": "SKU",
                "width": 130, "stretch": False},
            {"id": "name",     "label": "Part Name",     "width": 200},
            {"id": "category", "label": "Category",
                "width": 110, "stretch": False},
            {"id": "stock",    "label": "Stock",         "width": 80,
                "stretch": False, "anchor": "center"},
            {"id": "min",      "label": "Min",           "width": 55,
                "stretch": False, "anchor": "center"},
            {"id": "location", "label": "Bin",
                "width": 80,  "stretch": False},
            {"id": "cost",     "label": "Cost",
                "width": 95,  "stretch": False, "anchor": "e"},
            {"id": "sell",     "label": "Sell Price",
                "width": 95,  "stretch": False, "anchor": "e"},
        ]
        tbl_frame = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0)
        tbl_frame.pack(fill="both", expand=True)
        self.table = DataTable(tbl_frame, COLS,
                               on_double_click=self._on_double, height=25)
        self.table.pack(fill="both", expand=True)
        tbl_frame.bind("<Configure>", self._resize_table)

        # Context menu
        self._ctx = tk.Menu(self, tearoff=0, bg=COLORS["card"], fg=COLORS["txt"],
                            activebackground=COLORS["blue_bg"],
                            activeforeground=COLORS["blue"],
                            font=("Helvetica", 12))
        if is_admin():
            self._ctx.add_command(label="✎  Edit Part",
                                  command=self._open_edit_modal)
            self._ctx.add_separator()
        self._ctx.add_command(label="↓  Stock In",
                              command=self._open_stock_in)
        self._ctx.add_command(label="↑  Stock Out",
                              command=self._open_stock_out)
        if is_admin():
            self._ctx.add_separator()
            self._ctx.add_command(label="⚖  Adjust Stock",
                                  command=self._open_adjust_stock)
            self._ctx.add_command(label="🗑  Delete Part",
                                  command=self._delete_part)

        self.table.tree.bind("<Button-3>", self._show_ctx)
        self._load_categories()
        self.refresh()

    def _resize_table(self, event):
        if hasattr(self, "table"):
            self.table.set_visible_rows((event.height - 16) // 40)

    def _load_categories(self):
        db = get_session()
        try:
            cats = db.query(Category).order_by(Category.name).all()
            self._categories = cats
            self._cat_menu.configure(
                values=["All Categories"] + [c.name for c in cats])
        finally:
            db.close()

    def refresh(self):
        db = get_session()
        try:
            search = self._search_var.get().strip()
            cat = self._cat_var.get()
            rows_raw = PartsService(db).get_stock_view(
                search=search,
                category=cat if cat != "All Categories" else "")
        finally:
            db.close()

        if self._low_only:
            rows_raw = [p for p in rows_raw if p.get("is_low_stock")]

        rows = []
        for p in rows_raw:
            tag = "low" if p["is_low_stock"] else ""
            rows.append({"id": p["id"], "_tag": tag, "values": (
                p["sku"], p["name"], p["category"] or "—",
                f"{p['current_stock']} {p['unit']}",
                str(p["min_stock"]),
                p["bin_location"] or "—",
                f"₱{p['unit_cost']:,.2f}",
                f"₱{p['selling_price']:,.2f}" if p.get(
                    "selling_price") else "—",
            )})
        self.table.load(rows)
        n = len(rows)
        suffix = " · low stock" if self._low_only else ""
        self._count_lbl.configure(text=f"{n} part{'s' if n != 1 else ''}{suffix}")

    def set_low_stock_filter(self, on: bool = True):
        """Turn the low-stock-only filter on/off and restyle the button.
        Public so the Dashboard's 'View all' links can open Parts pre-filtered."""
        self._low_only = bool(on)
        if self._low_only:
            self._low_btn.configure(fg_color=COLORS["red"], hover_color=COLORS["red"],
                                    text_color="#FFFFFF")
        else:
            self._low_btn.configure(fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                                    text_color=COLORS["txt2"])
        self.refresh()

    def _toggle_low(self):
        self.set_low_stock_filter(not self._low_only)

    def _selected_id(self):
        iid = self.table.get_selected_iid()
        return int(iid) if iid else None

    def _show_ctx(self, event):
        iid = self.table.tree.identify_row(event.y)
        if iid:
            self.table.tree.selection_set(iid)
            self._ctx.tk_popup(event.x_root, event.y_root)

    def _on_double(self, _):
        if is_admin():
            self._open_edit_modal()

    # ── Add Part Modal (scrollable, responsive) ───────────────────────
    def _open_add_modal(self):
        if not is_admin():
            return
        db = get_session()
        cats = db.query(Category).order_by(Category.name).all()
        db.close()
        cat_names = [c.name for c in cats]

        m = Modal(self, "Add New Part", width=520, height=580)

        # vars
        name_var = tk.StringVar()
        desc_var = tk.StringVar()
        cat_var = tk.StringVar(value=cat_names[0] if cat_names else "")
        unit_var = tk.StringVar(value="pcs")
        cost_var = tk.StringVar(value="0.00")
        sell_var = tk.StringVar(value="0.00")
        min_var = tk.StringVar(value="5")
        bin_var = tk.StringVar()
        makes_var = tk.StringVar()

        _field(m.body, "Part Name",    name_var,
               "e.g. Brake Pad Front", required=True)
        _field(m.body, "Description",  desc_var,  "Optional")
        _option(m.body, "Category",    cat_var,
                cat_names if cat_names else ["(none)"])

        # 3-col row: Unit | Cost | Selling Price
        trio = ctk.CTkFrame(m.body, fg_color="transparent")
        trio.pack(fill="x", padx=24, pady=(0, 12))
        for i in range(3):
            trio.columnconfigure(i, weight=1, uniform="trio")
        for col, (lbl, var, ph) in enumerate([
            ("Unit",             unit_var, "pcs"),
            ("Cost Price (₱)",   cost_var, "0.00"),
            ("Selling Price (₱)", sell_var, "0.00"),
        ]):
            f = ctk.CTkFrame(trio, fg_color="transparent")
            f.grid(row=0, column=col, padx=(
                0 if col == 0 else 8, 0), sticky="ew")
            _lbl(f, lbl)
            _entry(f, var, ph).pack(fill="x")

        # 2-col row: Min Stock | Bin Location
        duo = ctk.CTkFrame(m.body, fg_color="transparent")
        duo.pack(fill="x", padx=24, pady=(0, 12))
        duo.columnconfigure(0, weight=1, uniform="duo")
        duo.columnconfigure(1, weight=1, uniform="duo")
        for col, (lbl, var, ph) in enumerate([
            ("Min Stock",    min_var, "5"),
            ("Bin Location", bin_var, "e.g. A2-S3"),
        ]):
            f = ctk.CTkFrame(duo, fg_color="transparent")
            f.grid(row=0, column=col, padx=(
                0 if col == 0 else 8, 0), sticky="ew")
            _lbl(f, lbl)
            _entry(f, var, ph).pack(fill="x")

        _field(m.body, "Vehicle Makes", makes_var, "e.g. Toyota, Honda")

        err = ctk.CTkLabel(m.body, text="", font=FONTS["small"],
                           text_color=COLORS["red"])
        err.pack(padx=24, anchor="w")

        def confirm():
            if not name_var.get().strip():
                err.configure(text="Part name is required.")
                return
            try:
                cost = float(cost_var.get())
                sell = float(sell_var.get())
                minn = int(min_var.get())
            except ValueError:
                err.configure(
                    text="Cost, selling price, and min stock must be numbers.")
                return
            cat_id = next(
                (c.id for c in cats if c.name == cat_var.get()), None)
            db2 = get_session()
            try:
                PartsService(db2).create(PartCreate(
                    name=name_var.get().strip(), description=desc_var.get().strip() or None,
                    category_id=cat_id, unit_cost=cost, selling_price=sell,
                    unit=unit_var.get().strip() or "pcs", min_stock=minn,
                    bin_location=bin_var.get().strip() or None,
                    vehicle_makes=makes_var.get().strip() or None,
                ))
            finally:
                db2.close()
            m.destroy()
            self.refresh()
            Toast(self.app, "Part added successfully.", kind="success")

        m.add_footer_buttons("Cancel", "Add Part", on_confirm=confirm)

    # ── Edit Part Modal ───────────────────────────────────────────────
    def _open_edit_modal(self):
        if not is_admin():
            return
        part_id = self._selected_id()
        if not part_id:
            return
        db = get_session()
        part = PartsService(db).get_by_id(part_id)
        cats = db.query(Category).order_by(Category.name).all()
        db.close()
        if not part:
            return

        cat_names = [c.name for c in cats]
        cur_cat = next((c.name for c in cats if c.id == part.category_id), "")

        m = Modal(self, f"Edit — {part.name}", width=520, height=540)

        name_var = tk.StringVar(value=part.name)
        cat_var = tk.StringVar(value=cur_cat)
        unit_var = tk.StringVar(value=part.unit)
        cost_var = tk.StringVar(value=str(part.unit_cost))
        sell_var = tk.StringVar(value=str(part.selling_price or 0))
        min_var = tk.StringVar(value=str(part.min_stock))
        bin_var = tk.StringVar(value=part.bin_location or "")

        _field(m.body, "Part Name",  name_var, required=True)
        _option(m.body, "Category",  cat_var,
                cat_names if cat_names else ["(none)"])

        trio = ctk.CTkFrame(m.body, fg_color="transparent")
        trio.pack(fill="x", padx=24, pady=(0, 12))
        for i in range(3):
            trio.columnconfigure(i, weight=1, uniform="trio")
        for col, (lbl, var) in enumerate([
            ("Unit",              unit_var),
            ("Cost Price (₱)",    cost_var),
            ("Selling Price (₱)", sell_var),
        ]):
            f = ctk.CTkFrame(trio, fg_color="transparent")
            f.grid(row=0, column=col, padx=(
                0 if col == 0 else 8, 0), sticky="ew")
            _lbl(f, lbl)
            _entry(f, var).pack(fill="x")

        duo = ctk.CTkFrame(m.body, fg_color="transparent")
        duo.pack(fill="x", padx=24, pady=(0, 12))
        duo.columnconfigure(0, weight=1, uniform="duo")
        duo.columnconfigure(1, weight=1, uniform="duo")
        for col, (lbl, var, ph) in enumerate([
            ("Min Stock",    min_var, "5"),
            ("Bin Location", bin_var, "e.g. A2-S3"),
        ]):
            f = ctk.CTkFrame(duo, fg_color="transparent")
            f.grid(row=0, column=col, padx=(
                0 if col == 0 else 8, 0), sticky="ew")
            _lbl(f, lbl)
            _entry(f, var, ph).pack(fill="x")

        err = ctk.CTkLabel(m.body, text="", font=FONTS["small"],
                           text_color=COLORS["red"])
        err.pack(padx=24, anchor="w")

        def confirm():
            if not name_var.get().strip():
                err.configure(text="Part name is required.")
                return
            try:
                cost = float(cost_var.get())
                sell = float(sell_var.get())
                minn = int(min_var.get())
            except ValueError:
                err.configure(
                    text="Numbers required for cost, sell price, min stock.")
                return
            cat_id = next(
                (c.id for c in cats if c.name == cat_var.get()), None)
            db2 = get_session()
            try:
                PartsService(db2).update(part_id, PartUpdate(
                    name=name_var.get().strip(), category_id=cat_id,
                    unit_cost=cost, selling_price=sell,
                    unit=unit_var.get().strip(),
                    min_stock=minn, bin_location=bin_var.get().strip() or None,
                ))
            finally:
                db2.close()
            m.destroy()
            self.refresh()
            Toast(self.app, "Part updated.", kind="success")

        m.add_footer_buttons("Cancel", "Save Changes", on_confirm=confirm)

    def _open_stock_in(self):
        pid = self._selected_id()
        if not pid:
            return
        from ui.screens.stock_in import open_stock_in_modal
        open_stock_in_modal(self.app, pid, on_done=self.refresh)

    def _open_stock_out(self):
        pid = self._selected_id()
        if not pid:
            return
        from ui.screens.stock_out import open_stock_out_modal
        open_stock_out_modal(self.app, pid, on_done=self.refresh)

    def _open_adjust_stock(self):
        if not is_admin():
            return
        pid = self._selected_id()
        if not pid:
            return
        from ui.screens.adjust_stock_dialog import AdjustStockDialog
        AdjustStockDialog(self, self.app, pid, on_done=self.refresh)

    def _delete_part(self):
        """Delete the selected part from the desktop app.

        Supports projects where PartsService has a real delete/remove method.
        If the service only has deactivate(), it falls back to soft-delete so the
        option still works with the current backend.
        """
        if not is_admin():
            return

        pid = self._selected_id()
        if not pid:
            return

        part_name = "this part"
        db = get_session()
        try:
            part = PartsService(db).get_by_id(pid)
            if part and getattr(part, "name", None):
                part_name = part.name
        except Exception:
            pass
        finally:
            db.close()

        confirm_msg = (
            f'Delete "{part_name}"?\n\n'
            "This will hide it from the active Parts Library while keeping stock history safe."
        )
        if not messagebox.askyesno("Delete Part", confirm_msg, icon="warning", parent=self):
            return

        db = get_session()
        try:
            service = PartsService(db)

            # Use soft-delete first. This works even when the part already has
            # stock movement history, because it only hides the part from the
            # active Parts Library and preserves reports/transactions.
            if hasattr(service, "deactivate"):
                service.deactivate(pid, user=current_username())
            elif hasattr(service, "delete"):
                service.delete(pid, user=current_username())
            elif hasattr(service, "remove"):
                service.remove(pid, user=current_username())
            else:
                raise AttributeError(
                    "PartsService has no deactivate(), delete(), or remove() method."
                )

            if hasattr(db, "commit"):
                db.commit()

        except Exception as exc:
            try:
                db.rollback()
            except Exception:
                pass
            messagebox.showerror("Delete Failed", str(exc), parent=self)
            return
        finally:
            db.close()

        self.refresh()
        Toast(self.app, "Part deleted.", kind="warning")

    # Backward compatibility for older code paths that may still call _deactivate.
    def _deactivate(self):
        self._delete_part()
