import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from config.themes import COLORS, FONTS
from ui.components.data_table import DataTable
from ui.components.responsive import Debouncer
from ui.components.toast import Toast
from database.engine import get_session
from database.models.category import Category
from core.services.pos_service import PosService
from core.services.settings_service import SettingsService
from core.validators.pos_schema import SaleCreate, FeeLine, PAYMENT_METHODS
from core.services.auth_service import current_username
from utils.receipt_print import open_receipt

_ALL_CATS = "All Categories"


class PosScreen(ctk.CTkFrame):
    """
    Point of Sale — two-panel checkout.
    Left: search / product picker.  Right: cart + checkout summary.
    """

    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self.app = app
        self.cart = {}          # part_id -> dict(sku,name,qty,price,stock,unit)
        self._grand_total = 0.0
        self._search_debounce = Debouncer(self, delay_ms=160)
        self._build()

    # ── Layout ────────────────────────────────────────────────────────
    def _build(self):
        topbar = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=74)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        title_box = ctk.CTkFrame(topbar, fg_color="transparent")
        title_box.pack(side="left", padx=28, pady=14)
        ctk.CTkLabel(title_box, text="Point of Sale", font=("Helvetica", 22, "bold"),
                     text_color=COLORS["navy"]).pack(anchor="w")
        ctk.CTkLabel(title_box, text="Fast checkout for stocked parts",
                     font=FONTS["small"], text_color=COLORS["txt3"]).pack(anchor="w", pady=(1, 0))
        ctk.CTkLabel(topbar, text=datetime.now().strftime("%b %d, %Y"),
                     font=FONTS["small"], text_color=COLORS["txt3"]).pack(side="right", padx=(0, 24))
        ctk.CTkButton(topbar, text="🧾  Sales History",
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"], font=FONTS["body"],
                      width=150, height=34, command=self._open_recent_sales
                      ).pack(side="right", padx=12, pady=20)

        body = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        body.pack(fill="both", expand=True, padx=20, pady=18)
        body.columnconfigure(0, weight=11, uniform="p")
        body.columnconfigure(1, weight=9, uniform="p")
        body.rowconfigure(0, weight=1)
        body.bind("<Configure>", self._on_body_resize)

        self._build_left(body)
        self._build_right(body)
        self._refresh_results()
        self._recompute()

    def _section_label(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", padx=18, pady=(16, 8))

    def refresh(self):
        """Reload categories (e.g. created in Settings) and the product list, so
        the POS reflects new categories without a logout or restart. Called by the
        app router each time the POS screen is shown."""
        try:
            self._cat_menu.configure(values=self._category_options())
        except Exception:
            pass
        try:
            self._fee_menu.configure(values=self._fee_type_options())
        except Exception:
            pass
        if hasattr(self, "_results"):
            self._refresh_results()
        self._recompute()
        # Put the cursor in the search box so checkout can start typing/scanning
        # immediately (after the screen is actually shown).
        self.after(120, self._focus_search)

    # ── Left: product picker ──────────────────────────────────────────
    def _build_left(self, parent):
        left = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=16,
                            border_width=1, border_color=COLORS["border"])
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        head = ctk.CTkFrame(left, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(18, 10))
        ctk.CTkLabel(head, text="Products", font=("Helvetica", 16, "bold"),
                     text_color=COLORS["navy"]).pack(side="left")
        ctk.CTkLabel(head, text="Search SKU, name, or category",
                     font=FONTS["small"], text_color=COLORS["txt3"]).pack(side="right")

        filt = ctk.CTkFrame(left, fg_color=COLORS["bg2"], corner_radius=12)
        filt.pack(fill="x", padx=18, pady=(0, 14))
        filt.columnconfigure(0, weight=1)

        self._search_var = tk.StringVar()
        search_box = ctk.CTkFrame(filt, fg_color="transparent")
        search_box.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=10)
        search = ctk.CTkEntry(search_box, textvariable=self._search_var,
                              placeholder_text="Search by SKU or part name...",
                              fg_color=COLORS["card"], border_color=COLORS["border"],
                              text_color=COLORS["txt"], font=FONTS["body"],
                              height=42, corner_radius=10)
        search.pack(fill="x")
        self._search_entry = search
        # Enter / barcode scanner: add the best-matching product straight to the
        # cart and keep the cursor here, ready for the next scan — keyboard-only
        # checkout, no mouse needed.
        search.bind("<Return>", self._on_search_enter)
        self._search_var.trace_add(
            "write", lambda *_: self._search_debounce.call(self._refresh_results))

        self._cat_var = tk.StringVar(value=_ALL_CATS)
        cat_box = ctk.CTkFrame(filt, fg_color="transparent")
        cat_box.grid(row=0, column=1, sticky="ew", padx=(0, 12), pady=10)
        self._cat_menu = ctk.CTkOptionMenu(
            cat_box, variable=self._cat_var, values=self._category_options(),
            fg_color=COLORS["card"], button_color=COLORS["border"],
            button_hover_color=COLORS["bg2"],
            text_color=COLORS["txt"], font=FONTS["body"],
            dropdown_fg_color=COLORS["card"], width=188, height=42,
            corner_radius=10,
            command=lambda _: self._refresh_results())
        self._cat_menu.pack(fill="x")

        self._product_table_wrap = ctk.CTkFrame(
            left, fg_color=COLORS["card"], corner_radius=14,
            border_width=1, border_color=COLORS["border"])
        self._product_table_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        cols = [
            {"id": "sku", "label": "SKU", "width": 150, "stretch": False},
            {"id": "name", "label": "Part Name", "width": 300, "minwidth": 220},
            {"id": "cat", "label": "Category", "width": 120, "stretch": False},
            {"id": "stock", "label": "Stock", "width": 74, "stretch": False, "anchor": "center"},
            {"id": "price", "label": "Price", "width": 110, "stretch": False, "anchor": "e"},
            {"id": "add", "label": "Add", "width": 68, "stretch": False, "anchor": "center"},
        ]
        self._results = DataTable(self._product_table_wrap, cols, height=18,
                                  on_click=self._on_result_click,
                                  on_double_click=self._add_from_results)
        self._results.pack(fill="both", expand=True, padx=1, pady=1)

    # ── Right: cart + checkout ────────────────────────────────────────
    def _build_right(self, parent):
        right = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=16,
                             border_width=1, border_color=COLORS["border"])
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=18, pady=(10, 6))
        title = ctk.CTkFrame(hdr, fg_color="transparent")
        title.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(title, text="Order Summary", font=("Helvetica", 16, "bold"),
                     text_color=COLORS["navy"]).pack(anchor="w")
        ctk.CTkButton(hdr, text="Clear", width=72, height=30, corner_radius=9,
                      fg_color=COLORS["bg2"], hover_color=COLORS["red_bg"],
                      text_color=COLORS["txt2"], font=FONTS["small"],
                      command=self._clear_cart).pack(side="right")

        # Cart column header
        chead = ctk.CTkFrame(right, fg_color=COLORS["navy"], corner_radius=10, height=30)
        chead.grid(row=1, column=0, sticky="ew", padx=18)
        chead.pack_propagate(False)
        ctk.CTkLabel(chead, text="PRODUCT", font=FONTS["label"], text_color="#FFFFFF",
                     anchor="w").pack(side="left", fill="x", expand=True, padx=(12, 2))
        for txt, w, anchor in [("QTY", 96, "center"), ("PRICE", 78, "e"),
                               ("TOTAL", 88, "e"), ("", 34, "center")]:
            ctk.CTkLabel(chead, text=txt, font=FONTS["label"], text_color="#FFFFFF",
                         width=w, anchor=anchor).pack(side="left", padx=2)

        self._cart_shell = ctk.CTkFrame(right, fg_color=COLORS["bg2"],
                                        corner_radius=12, height=108)
        self._cart_shell.grid(row=2, column=0, sticky="nsew", padx=18, pady=(5, 8))
        self._cart_shell.pack_propagate(False)
        self._cart_shell.grid_propagate(False)
        self._cart_frame = ctk.CTkScrollableFrame(self._cart_shell, fg_color=COLORS["bg2"],
                                                  corner_radius=12)
        self._cart_frame.pack(fill="both", expand=True)

        checkout = ctk.CTkFrame(right, fg_color="transparent")
        checkout.grid(row=3, column=0, sticky="ew")

        # ── Sale-level discount control ──
        disc = ctk.CTkFrame(checkout, fg_color=COLORS["card"], corner_radius=12,
                            border_width=1, border_color=COLORS["border"])
        disc.pack(fill="x", padx=18, pady=(0, 4))
        ctk.CTkLabel(disc, text="DISCOUNT", font=FONTS["label"],
                     text_color=COLORS["amber"], width=86, anchor="w").pack(
            side="left", padx=(10, 0), pady=5)
        self._disc_type = ctk.CTkSegmentedButton(
            disc, values=["₱ Amount", "% Percent"],
            font=FONTS["small"], height=30, corner_radius=8,
            fg_color=COLORS["card"], selected_color=COLORS["amber"],
            selected_hover_color="#A96514",
            unselected_color=COLORS["card"], unselected_hover_color=COLORS["border"],
            text_color=COLORS["txt"], command=lambda _: self._recompute())
        self._disc_type.set("₱ Amount")
        self._disc_type.pack(side="left", padx=(0, 8))
        self._disc_val = tk.StringVar(value="0")
        ctk.CTkEntry(disc, textvariable=self._disc_val, width=96, height=30,
                     fg_color=COLORS["card"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"], justify="right",
                     corner_radius=8
                     ).pack(side="left", padx=(0, 10))
        self._disc_val.trace_add("write", lambda *_: self._recompute())

        # ── Service / other fees ──
        self._fees = []          # list of {"name","amount"}
        fee_box = ctk.CTkFrame(checkout, fg_color=COLORS["card"], corner_radius=12,
                               border_width=1, border_color=COLORS["border"])
        fee_box.pack(fill="x", padx=18, pady=(0, 4))
        addrow = ctk.CTkFrame(fee_box, fg_color="transparent")
        addrow.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(addrow, text="FEE", font=FONTS["label"],
                     text_color=COLORS["navy"], width=44, anchor="w").pack(side="left")
        self._fee_type_var = tk.StringVar(value="Custom")
        self._fee_menu = ctk.CTkOptionMenu(
            addrow, variable=self._fee_type_var, values=self._fee_type_options(),
            fg_color=COLORS["bg2"], button_color=COLORS["border"],
            text_color=COLORS["txt"], font=FONTS["small"],
            dropdown_fg_color=COLORS["card"], width=150, height=30,
            command=self._on_fee_type)
        self._fee_menu.pack(side="left", padx=(0, 6))
        self._fee_amt_var = tk.StringVar(value="0.00")
        ctk.CTkEntry(addrow, textvariable=self._fee_amt_var, width=80, height=30,
                     fg_color=COLORS["bg2"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["small"], justify="right",
                     corner_radius=8).pack(side="left", padx=(0, 6))
        ctk.CTkButton(addrow, text="Add", width=52, height=30,
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["small"],
                      command=self._add_fee).pack(side="left")
        # Added fees render inside the cart list (see _render_cart) so many
        # fees scroll with the cart instead of shrinking the order summary.
        addrow.pack_configure(pady=(8, 8))

        # ── Totals box ──
        tbox = ctk.CTkFrame(checkout, fg_color=COLORS["bg2"], corner_radius=14)
        tbox.pack(fill="x", padx=18, pady=(0, 5))
        self._lbl_subtotal = self._total_row(tbox, "Subtotal")
        self._lbl_discount = self._total_row(tbox, "Discount", COLORS["amber"])
        self._taxable_row, self._lbl_taxable = self._total_row(
            tbox, "Taxable", with_frame=True)
        self._tax_row, (self._tax_name_lbl, self._lbl_tax) = self._total_row(
            tbox, "Tax", with_label=True, with_frame=True)
        self._tax_rows_shown = True
        self._labor_row, self._lbl_labor = self._total_row(
            tbox, "Fees", with_frame=True)
        ctk.CTkFrame(tbox, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=14, pady=(4, 0))
        self._lbl_grand = self._total_row(tbox, "GRAND TOTAL", COLORS["navy"], big=True)

        # ── Payment ──
        pay = ctk.CTkFrame(checkout, fg_color="transparent")
        pay.pack(fill="x", padx=18, pady=(0, 2))
        pay.columnconfigure((0, 1), weight=1)

        pm = ctk.CTkFrame(pay, fg_color="transparent")
        pm.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkLabel(pm, text="PAYMENT METHOD", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))
        self._pay_var = tk.StringVar(value=PAYMENT_METHODS[0])
        ctk.CTkOptionMenu(pm, variable=self._pay_var, values=PAYMENT_METHODS,
                          fg_color=COLORS["bg"], button_color=COLORS["border"],
                          text_color=COLORS["txt"], font=FONTS["body"],
                          dropdown_fg_color=COLORS["card"], height=34,
                          corner_radius=10,
                          command=lambda _: self._on_pay_change()).pack(fill="x")

        rc = ctk.CTkFrame(pay, fg_color="transparent")
        rc.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ctk.CTkLabel(rc, text="AMOUNT RECEIVED", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))
        self._recv_var = tk.StringVar(value="0.00")
        recv_entry = ctk.CTkEntry(rc, textvariable=self._recv_var,
                                  fg_color=COLORS["bg"], border_color=COLORS["border"],
                                  text_color=COLORS["txt"], font=FONTS["body"], height=34,
                                  corner_radius=10)
        recv_entry.pack(fill="x")
        # Pressing Enter in Amount Received completes the sale (same as the button;
        # _complete_sale itself blocks an empty cart or insufficient cash).
        recv_entry.bind("<Return>", lambda e: self._complete_sale())
        self._recv_var.trace_add("write", lambda *_: self._update_change())

        self._lbl_change = ctk.CTkLabel(checkout, text="Change Due:  ₱0.00",
                                        font=FONTS["heading"], text_color=COLORS["txt3"])
        self._lbl_change.pack(anchor="e", padx=20, pady=(2, 0))

        self._err = ctk.CTkLabel(checkout, text="", font=FONTS["small"], height=16,
                                 text_color=COLORS["red"], anchor="w")
        self._err.pack(fill="x", padx=20)

        action_bar = ctk.CTkFrame(checkout, fg_color="transparent", height=50)
        action_bar.pack(fill="x", padx=18, pady=(4, 10))
        action_bar.pack_propagate(False)
        self._complete_btn = ctk.CTkButton(
            action_bar, text="✓  Complete Sale",
            fg_color=COLORS["amber"], hover_color="#EA580C",
            text_color="#FFFFFF", font=("Helvetica", 16, "bold"), height=46,
            corner_radius=14,
            command=self._complete_sale)
        self._complete_btn.pack(fill="both", expand=True)

        self._render_cart()

    def _total_row(self, parent, label, color=None, big=False, with_label=False,
                   with_frame=False):
        r = ctk.CTkFrame(parent, fg_color="transparent", height=34 if big else 24)
        r.pack(fill="x", padx=14, pady=(3 if big else 1))
        r.pack_propagate(False)
        name_lbl = ctk.CTkLabel(r, text=label, anchor="w",
                                font=FONTS["heading"] if big else FONTS["small"],
                                text_color=color or COLORS["txt3"])
        name_lbl.pack(side="left")
        val = ctk.CTkLabel(r, text="₱0.00", anchor="e",
                           font=FONTS["heading"] if big else FONTS["body"],
                           text_color=color or COLORS["txt"])
        val.pack(side="right")
        inner = (name_lbl, val) if with_label else val
        return (r, inner) if with_frame else inner

    def _on_body_resize(self, event):
        if not hasattr(self, "_cart_shell"):
            return
        if event.height < 700:
            cart_h = 56
        elif event.height < 780:
            cart_h = 64
        elif event.height < 880:
            cart_h = 118
        else:
            cart_h = 164
        self._cart_shell.configure(height=cart_h)
        if hasattr(self, "_results"):
            self._results.set_visible_rows((event.height - 170) // 40)

    # ── Categories ────────────────────────────────────────────────────
    def _category_options(self):
        db = get_session()
        try:
            names = [c.name for c in db.query(Category).order_by(Category.name).all()]
        finally:
            db.close()
        return [_ALL_CATS] + names

    # ── Product results ───────────────────────────────────────────────
    def _refresh_results(self):
        cat = self._cat_var.get()
        cat = "" if cat == _ALL_CATS else cat
        db = get_session()
        try:
            rows = PosService(db).search_parts(
                self._search_var.get().strip(), category=cat, limit=200)
        finally:
            db.close()
        self._result_map = {str(r["id"]): r for r in rows}
        table_rows = []
        for r in rows:
            stock = r.get("current_stock", 0)
            table_rows.append({
                "id": r["id"],
                "_tag": "low" if stock <= 0 else ("warn" if stock <= (r.get("min_stock") or 0) else ""),
                "values": (
                    r["sku"],
                    r["name"],
                    r.get("category") or "Uncategorized",
                    stock,
                    f"₱{(r.get('selling_price') or 0):,.2f}",
                    "Add" if stock > 0 else "—",
                ),
            })
        self._results.load(table_rows)

    def _on_result_click(self, iid, col):
        if col == "#6":
            self._add_from_results(iid)

    def _add_from_results(self, iid):
        if not iid:
            return
        r = self._result_map.get(str(iid))
        if not r:
            return
        stock = r.get("current_stock", 0)
        if stock <= 0:
            Toast(self.app, f"{r['name']} is out of stock.", kind="warning")
            return
        pid = r["id"]
        if pid in self.cart:
            if self.cart[pid]["qty"] < stock:
                self.cart[pid]["qty"] += 1
            else:
                Toast(self.app, f"Only {stock} in stock.", kind="warning")
        else:
            self.cart[pid] = {
                "sku": r["sku"], "name": r["name"], "qty": 1,
                "price": float(r.get("selling_price") or 0),
                "stock": stock, "unit": r.get("unit") or "pcs",
            }
        self._render_cart()
        self._recompute()

    def _focus_search(self):
        try:
            self._search_entry.focus_set()
        except Exception:
            pass

    def _on_search_enter(self, _event=None):
        """Add the best match to the cart on Enter (works with barcode scanners,
        which type the code then send Enter), then clear the box and keep focus
        for the next item. A fresh lookup is used so a fast scan isn't missed by
        the search debounce."""
        term = self._search_var.get().strip()
        if not term:
            return "break"
        db = get_session()
        try:
            rows = PosService(db).search_parts(term, limit=10)
        finally:
            db.close()
        if not rows:
            Toast(self.app, f"No product matches '{term}'.", kind="warning")
            return "break"
        low = term.lower()
        # Prefer an exact SKU/barcode match; otherwise take the top result.
        match = next((r for r in rows
                      if str(r.get("sku", "")).lower() == low), None) or rows[0]
        self._result_map[str(match["id"])] = match
        self._add_from_results(str(match["id"]))
        self._search_var.set("")          # ready for the next scan
        self._focus_search()
        return "break"

    # ── Cart rendering ────────────────────────────────────────────────
    def _render_cart(self):
        for w in self._cart_frame.winfo_children():
            w.destroy()
        if not self.cart and not getattr(self, "_fees", []):
            empty = ctk.CTkFrame(self._cart_frame, fg_color=COLORS["card"],
                                 corner_radius=12, border_width=1,
                                 border_color=COLORS["border"])
            empty.pack(fill="x", padx=4, pady=6)
            ctk.CTkLabel(empty, text="Cart is empty",
                         font=FONTS["heading"], text_color=COLORS["txt"]).pack(pady=(22, 2))
            ctk.CTkLabel(empty, text="Add products from the left to begin checkout.",
                         font=FONTS["small"], text_color=COLORS["txt3"],
                         justify="center").pack(pady=(0, 22))
            return
        for pid, it in list(self.cart.items()):
            row = ctk.CTkFrame(self._cart_frame, fg_color=COLORS["card"], height=44,
                               corner_radius=10, border_width=1,
                               border_color=COLORS["border"])
            row.pack(fill="x", padx=4, pady=3)
            row.pack_propagate(False)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=(10, 3), pady=4)
            ctk.CTkLabel(info, text=it["name"], font=("Helvetica", 12, "normal"),
                         text_color=COLORS["txt"], anchor="w").pack(anchor="w", fill="x")
            ctk.CTkLabel(info, text=f"{it['sku']} · stock {it['stock']}",
                         font=("Helvetica", 10), text_color=COLORS["txt3"],
                         anchor="w").pack(anchor="w", fill="x")

            # Qty stepper (compact, fixed width to line up with header)
            qbox = ctk.CTkFrame(row, fg_color="transparent", width=96)
            qbox.pack(side="left", padx=2, pady=8)
            qbox.pack_propagate(False)
            ctk.CTkButton(qbox, text="−", width=24, height=24, fg_color=COLORS["bg2"],
                          hover_color=COLORS["border"], text_color=COLORS["txt"],
                          font=FONTS["small"],
                          command=lambda p=pid: self._bump_qty(p, -1)).pack(side="left")
            ctk.CTkLabel(qbox, text=str(it["qty"]), width=28, font=FONTS["small"],
                         text_color=COLORS["txt"]).pack(side="left")
            ctk.CTkButton(qbox, text="＋", width=24, height=24, fg_color=COLORS["bg2"],
                          hover_color=COLORS["border"], text_color=COLORS["txt"],
                          font=FONTS["small"],
                          command=lambda p=pid: self._bump_qty(p, 1)).pack(side="left")

            ctk.CTkLabel(row, text=f"₱{it['price']:,.2f}", width=78, anchor="e",
                         font=FONTS["small"], text_color=COLORS["txt2"]).pack(side="left", padx=2)

            line_total = it["price"] * it["qty"]
            ctk.CTkLabel(row, text=f"₱{line_total:,.2f}", width=88, anchor="e",
                         font=FONTS["body"], text_color=COLORS["txt"]).pack(side="left", padx=2)

            ctk.CTkButton(row, text="✕", width=28, height=24, fg_color="transparent",
                          hover_color=COLORS["red_bg"], text_color=COLORS["txt3"],
                          font=FONTS["small"],
                          command=lambda p=pid: self._remove(p)).pack(side="left", padx=2)

        # Service / other fees render as cart rows beneath the products.
        for i, f in enumerate(getattr(self, "_fees", [])):
            frow = ctk.CTkFrame(self._cart_frame, fg_color=COLORS["card"], height=44,
                                corner_radius=10, border_width=1,
                                border_color=COLORS["border"])
            frow.pack(fill="x", padx=4, pady=3)
            frow.pack_propagate(False)

            info = ctk.CTkFrame(frow, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True, padx=(10, 3), pady=4)
            ctk.CTkLabel(info, text=f["name"], font=("Helvetica", 12, "normal"),
                         text_color=COLORS["txt"], anchor="w").pack(anchor="w", fill="x")
            ctk.CTkLabel(info, text="Service / fee", font=("Helvetica", 10),
                         text_color=COLORS["navy"], anchor="w").pack(anchor="w", fill="x")

            ctk.CTkLabel(frow, text=f"₱{f['amount']:,.2f}", width=88, anchor="e",
                         font=FONTS["body"], text_color=COLORS["txt"]).pack(
                side="left", padx=2)
            ctk.CTkButton(frow, text="✕", width=28, height=24, fg_color="transparent",
                          hover_color=COLORS["red_bg"], text_color=COLORS["txt3"],
                          font=FONTS["small"],
                          command=lambda x=i: self._remove_fee(x)).pack(
                side="left", padx=2)

    def _bump_qty(self, pid, delta):
        it = self.cart.get(pid)
        if not it:
            return
        new = it["qty"] + delta
        if new <= 0:
            self._remove(pid)
            return
        if new > it["stock"]:
            Toast(self.app, f"Only {it['stock']} in stock.", kind="warning")
            return
        it["qty"] = new
        self._render_cart()
        self._recompute()

    def _remove(self, pid):
        self.cart.pop(pid, None)
        self._render_cart()
        self._recompute()

    def _clear_cart(self):
        self.cart.clear()
        self._render_cart()
        self._recompute()

    # ── Totals ────────────────────────────────────────────────────────
    def _disc_is_percent(self):
        return self._disc_type.get().startswith("%")

    def _discount_state(self, subtotal):
        try:
            raw = float(self._disc_val.get() or 0)
        except ValueError:
            return 0.0, 0.0, "Discount must be a number."
        if raw < 0:
            return 0.0, raw, "Discount cannot be negative."
        if self._disc_is_percent():
            if raw > 100:
                return 0.0, raw, "Percent discount cannot exceed 100%."
            return round(subtotal * raw / 100, 2), raw, ""
        if raw > subtotal:
            return 0.0, raw, "Amount discount cannot exceed subtotal."
        return round(raw, 2), raw, ""

    # ── Fees ──────────────────────────────────────────────────────────
    def _fee_type_options(self):
        db = get_session()
        try:
            names = [f["name"] for f in SettingsService(db).get_fee_types()]
        finally:
            db.close()
        return names + ["Custom"]

    def _fee_defaults(self):
        db = get_session()
        try:
            return {f["name"]: f["default_amount"]
                    for f in SettingsService(db).get_fee_types()}
        finally:
            db.close()

    def _on_fee_type(self, name):
        amt = self._fee_defaults().get(name)
        if amt is not None:
            self._fee_amt_var.set(f"{amt:.2f}")

    def _add_fee(self):
        name = self._fee_type_var.get()
        if name == "Custom":
            name = "Service fee"
        try:
            amt = round(float(self._fee_amt_var.get() or 0), 2)
        except ValueError:
            self._err.configure(text="Fee amount must be a number.")
            return
        if amt <= 0:
            self._err.configure(text="Fee amount must be greater than 0.")
            return
        self._fees.append({"name": name, "amount": amt})
        self._fee_amt_var.set("0.00")
        self._render_fees()
        self._recompute()

    def _remove_fee(self, idx):
        if 0 <= idx < len(self._fees):
            del self._fees[idx]
        self._render_fees()
        self._recompute()

    def _render_fees(self):
        # Fees now live inside the cart list, so just re-render the cart.
        self._render_cart()

    def _recompute(self):
        cfg = self._settings()
        subtotal = sum(it["price"] * it["qty"] for it in self.cart.values())

        discount, _, discount_error = self._discount_state(subtotal)
        net = round(subtotal - discount, 2)

        tax_enabled = bool(cfg.get("tax_enabled")) and float(cfg.get("tax_rate") or 0) > 0
        rate = float(cfg.get("tax_rate") or 0)
        if tax_enabled:
            taxable = subtotal if cfg.get("tax_apply") == "before_discount" else net
            tax = round(taxable * rate / 100, 2)
        else:
            taxable, tax = net, 0.0
        labor = round(sum(f["amount"] for f in getattr(self, "_fees", [])), 2)
        grand = round(net + tax + labor, 2)
        self._grand_total = grand

        self._lbl_subtotal.configure(text=f"₱{subtotal:,.2f}")
        self._lbl_discount.configure(text=f"−₱{discount:,.2f}" if discount else "—")

        # Show the Taxable/Tax rows only when tax is enabled in settings.
        if tax_enabled:
            if not self._tax_rows_shown:
                self._taxable_row.pack(fill="x", padx=14, pady=1, before=self._labor_row)
                self._tax_row.pack(fill="x", padx=14, pady=1, before=self._labor_row)
                self._tax_rows_shown = True
            self._lbl_taxable.configure(text=f"₱{taxable:,.2f}")
            self._tax_name_lbl.configure(text=f"{cfg.get('tax_name','Tax')} ({rate:g}%)")
            self._lbl_tax.configure(text=f"₱{tax:,.2f}")
        elif self._tax_rows_shown:
            self._taxable_row.pack_forget()
            self._tax_row.pack_forget()
            self._tax_rows_shown = False

        self._lbl_labor.configure(text=f"₱{labor:,.2f}")
        self._lbl_grand.configure(text=f"₱{grand:,.2f}")
        if hasattr(self, "_err"):
            self._err.configure(text=discount_error)
        self._update_change()

    def _on_pay_change(self):
        self._update_change()

    def _update_change(self):
        try:
            recv = float(self._recv_var.get() or 0)
        except ValueError:
            recv = 0
        grand = self._grand_total
        is_cash = self._pay_var.get() == "Cash"
        if is_cash:
            change = recv - grand
            self._lbl_change.configure(
                text=f"Change Due:  ₱{max(change,0):,.2f}",
                text_color=COLORS["navy"] if (change >= 0 and recv > 0) else COLORS["txt3"])
        else:
            self._lbl_change.configure(text="Change Due:  —", text_color=COLORS["txt3"])
        self._update_complete_state(recv, grand, is_cash)

    def _update_complete_state(self, recv, grand, is_cash):
        """Enable Complete Sale only when the sale is valid."""
        _, _, discount_error = self._discount_state(
            sum(it["price"] * it["qty"] for it in self.cart.values()))
        valid = (bool(self.cart) or bool(getattr(self, "_fees", []))) \
            and grand > 0 and not discount_error
        if is_cash and recv < grand:
            valid = False
        if valid:
            self._complete_btn.configure(state="normal", fg_color=COLORS["amber"])
        else:
            self._complete_btn.configure(state="disabled", fg_color=COLORS["txt3"])

    def _settings(self):
        db = get_session()
        try:
            return SettingsService(db).get_pos_settings()
        finally:
            db.close()

    # ── Checkout ──────────────────────────────────────────────────────
    def _complete_sale(self):
        self._err.configure(text="")
        if not self.cart and not self._fees:
            self._err.configure(text="Nothing to sell — add a product or a fee.")
            return
        try:
            recv = float(self._recv_var.get() or 0)
        except ValueError:
            self._err.configure(text="Amount received must be a number.")
            return
        subtotal = sum(it["price"] * it["qty"] for it in self.cart.values())
        _, dval, discount_error = self._discount_state(subtotal)
        if discount_error:
            self._err.configure(text=discount_error)
            return

        items = [{"part_id": pid, "quantity": it["qty"], "unit_price": it["price"]}
                 for pid, it in self.cart.items()]
        from core.services.auth_service import get_current_user
        _u = get_current_user()
        cashier_name = (_u.full_name if _u and _u.full_name else current_username())
        try:
            payload = SaleCreate(
                items=items, payment_method=self._pay_var.get(),
                amount_received=recv, cashier=cashier_name,
                discount_type="percent" if self._disc_is_percent() else "amount",
                discount_value=dval,
                fees=[FeeLine(**f) for f in self._fees])
        except Exception as e:
            self._err.configure(text=str(e))
            return

        db = get_session()
        try:
            sale = PosService(db).create_sale(payload, cashier=cashier_name)
            detail = PosService(db).get_sale_detail(sale.id)
        except ValueError as e:
            self._err.configure(text=str(e))
            db.close()
            return
        except Exception as e:
            self._err.configure(text="Checkout failed. Please try again.")
            print(f"POS checkout error: {e}")
            db.close()
            return
        finally:
            db.close()

        self._clear_cart()
        self._recv_var.set("0.00")
        self._disc_val.set("0")
        self._disc_type.set("₱ Amount")
        self._fees = []
        self._render_fees()
        self._recompute()
        self._refresh_results()
        Toast(self.app, f"Sale {detail['receipt_no']} completed.", kind="success")
        self._show_receipt_summary(detail)

    # ── Receipt summary dialog ────────────────────────────────────────
    def _show_receipt_summary(self, detail):
        win = ctk.CTkToplevel(self)
        win.title(f"Receipt — {detail['receipt_no']}")
        win.geometry("420x560")
        win.minsize(380, 440)
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()
        win.lift()

        header = ctk.CTkFrame(win, fg_color=COLORS["bg"], corner_radius=0)
        header.pack(fill="x", padx=20, pady=(18, 8))
        ctk.CTkLabel(header, text="✓  Sale Completed", font=FONTS["title"],
                     text_color=COLORS["green"]).pack(pady=(0, 2))
        ctk.CTkLabel(header, text=detail["receipt_no"], font=FONTS["body"],
                     text_color=COLORS["txt2"]).pack()

        footer = ctk.CTkFrame(win, fg_color=COLORS["bg"], corner_radius=0)
        footer.pack(fill="x", side="bottom", padx=20, pady=(8, 16))
        ctk.CTkButton(footer, text="🖨  Print Receipt",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"], height=42,
                      command=lambda: open_receipt(detail)).pack(fill="x", pady=(0, 8))
        ctk.CTkButton(footer, text="Close", fg_color=COLORS["bg2"],
                      hover_color=COLORS["border"], text_color=COLORS["txt2"],
                      font=FONTS["body"], height=38,
                      command=win.destroy).pack(fill="x")

        content = ctk.CTkScrollableFrame(win, fg_color=COLORS["bg"],
                                         corner_radius=0)
        content.pack(fill="both", expand=True, padx=0, pady=(0, 0))

        box = ctk.CTkFrame(content, fg_color=COLORS["card"], corner_radius=10,
                           border_width=1, border_color=COLORS["border"])
        box.pack(fill="x", padx=20, pady=(0, 10))

        def line(lbl, val, color=None, big=False):
            r = ctk.CTkFrame(box, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(r, text=lbl, font=FONTS["heading"] if big else FONTS["small"],
                         text_color=color or COLORS["txt3"], anchor="w").pack(side="left")
            ctk.CTkLabel(r, text=val, font=FONTS["heading"] if big else FONTS["body"],
                         text_color=color or COLORS["txt"], anchor="e").pack(side="right")

        line("Qty", str(sum(i["quantity"] for i in detail["items"])))
        line("Subtotal", f"₱{detail['subtotal']:,.2f}")
        if detail["discount_total"]:
            dlabel = "Discount"
            if detail.get("discount_type") == "percent" and detail.get("discount_value"):
                dlabel = f"Discount ({detail['discount_value']:g}%)"
            line(dlabel, f"−₱{detail['discount_total']:,.2f}", COLORS["amber"])
        if detail["tax_enabled"]:
            line(f"{detail['tax_name']} ({detail['tax_rate']:g}%)", f"₱{detail['tax_amount']:,.2f}")
        for f in (detail.get("fees") or []):
            line(f["name"], f"₱{f['amount']:,.2f}")
        if not detail.get("fees") and detail.get("labor_amount"):
            line("Labor", f"₱{detail['labor_amount']:,.2f}")
        line("Grand Total", f"₱{detail['grand_total']:,.2f}", COLORS["navy"], big=True)
        line("Payment", detail["payment_method"])
        line("Received", f"₱{detail['amount_received']:,.2f}")
        line("Change", f"₱{detail['change_due']:,.2f}", COLORS["green"])

    # ── Recent sales window ───────────────────────────────────────────
    def _open_recent_sales(self):
        win = ctk.CTkToplevel(self)
        win.title("Sales History")
        win.geometry("780x540")
        win.configure(fg_color=COLORS["bg"])
        win.grab_set()
        win.lift()

        header = ctk.CTkFrame(win, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(header, text="Sales History", font=FONTS["title"],
                     text_color=COLORS["txt"]).pack(side="left")
        actionbar = ctk.CTkFrame(header, fg_color="transparent")
        actionbar.pack(side="right")

        # Date filter (default = today)
        date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        filt = ctk.CTkFrame(win, fg_color="transparent")
        filt.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(filt, text="Date", font=FONTS["small"],
                     text_color=COLORS["txt3"]).pack(side="left", padx=(0, 8))
        ctk.CTkEntry(filt, textvariable=date_var, placeholder_text="YYYY-MM-DD",
                     fg_color=COLORS["bg2"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["small"],
                     width=120, height=32).pack(side="left")

        COLS = [
            {"id": "receipt", "label": "Receipt #", "width": 150, "stretch": False},
            {"id": "date", "label": "Date / Time", "width": 150, "stretch": False},
            {"id": "cashier", "label": "Cashier", "width": 110, "stretch": False},
            {"id": "pay", "label": "Payment", "width": 100, "stretch": False},
            {"id": "items", "label": "Qty", "width": 60, "stretch": False, "anchor": "center"},
            {"id": "total", "label": "Total", "width": 110, "stretch": False, "anchor": "e"},
        ]
        wrap = ctk.CTkFrame(win, fg_color=COLORS["card"], corner_radius=0)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        table = DataTable(wrap, COLS, height=16)
        table.pack(fill="both", expand=True)

        def _reload():
            v = date_var.get().strip()
            kw = {}
            if v:
                try:
                    datetime.strptime(v, "%Y-%m-%d")
                    kw = {"date_from": v, "date_to": v}
                except ValueError:
                    Toast(self.app, "Use date format YYYY-MM-DD", kind="error")
            db = get_session()
            try:
                sales = PosService(db).get_recent_sales(limit=200, **kw)
                rows = [{
                    "id": s.id,
                    "values": (s.receipt_no, (s.sale_date or "")[:19].replace("T", "  "),
                               s.cashier, s.payment_method,
                               sum(i.quantity for i in s.items),
                               f"₱{s.grand_total:,.2f}"),
                } for s in sales]
            finally:
                db.close()
            table.load(rows)

        # All / Today / Apply buttons beside the date.
        for _txt, _cmd, _w in (
            ("All", lambda: (date_var.set(""), _reload()), 45),
            ("Today", lambda: (date_var.set(datetime.now().strftime("%Y-%m-%d")), _reload()), 60),
            ("Apply", _reload, 58),
        ):
            ctk.CTkButton(filt, text=_txt, fg_color=COLORS["bg2"],
                          hover_color=COLORS["border"], text_color=COLORS["txt2"],
                          font=FONTS["small"], width=_w, height=32,
                          command=_cmd).pack(side="left", padx=(6, 0))

        _reload()

        def print_selected():
            iid = table.get_selected_iid()
            if not iid:
                messagebox.showwarning("No Selection", "Select a sale first.", parent=win)
                return
            db2 = get_session()
            try:
                detail = PosService(db2).get_sale_detail(int(iid))
            finally:
                db2.close()
            if detail:
                open_receipt(detail)

        def void_selected():
            from core.services.auth_service import get_current_user
            from core.services.dashboard_service import DashboardService
            iid = table.get_selected_iid()
            if not iid:
                messagebox.showwarning("No Selection", "Select a sale first.", parent=win)
                return
            if not messagebox.askyesno(
                "Void Sale",
                "Void this sale? This permanently reverses it and restores the "
                "stock.\n\nUse this only for sales entered by mistake — for a "
                "genuine customer return, use the Returns screen instead.",
                icon="warning", parent=win):
                return
            u = get_current_user()
            db3 = get_session()
            try:
                receipt = PosService(db3).void_sale(
                    int(iid), user=u.username if u else "system")
                DashboardService(db3).invalidate()
            except Exception as e:
                messagebox.showerror("Cannot Void", str(e), parent=win)
                return
            finally:
                db3.close()
            Toast(self.app, f"Sale {receipt} voided.", kind="warning")
            _reload()

        ctk.CTkButton(actionbar, text="🖨  Print",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"], width=110, height=36,
                      command=print_selected).pack(side="right", padx=(8, 0))
        ctk.CTkButton(actionbar, text="✕  Void Sale",
                      fg_color=COLORS["red"], hover_color="#a93226",
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=130, height=36,
                      command=void_selected).pack(side="right", padx=(8, 0))
        table.on_double_click = lambda iid: (table.tree.selection_set(iid), print_selected())
