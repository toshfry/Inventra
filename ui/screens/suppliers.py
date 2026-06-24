import customtkinter as ctk
import tkinter as tk
from config.themes import COLORS, FONTS
from ui.components.data_table import DataTable
from ui.components.modal import Modal, field_row
from ui.components.toast import Toast
from database.engine import get_session
from core.services.supplier_service import SupplierService
from core.validators.supplier_schema import SupplierCreate, SupplierUpdate


class SuppliersScreen(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(
            parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self.app = app
        self._build()

    def _build(self):
        topbar = ctk.CTkFrame(self, fg_color=COLORS["card"],
                              corner_radius=0, height=60)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        ctk.CTkLabel(topbar, text="Suppliers",
                     font=FONTS["title"],
                     text_color=COLORS["txt"]).pack(side="left", padx=24, pady=16)
        ctk.CTkButton(topbar, text="+ Add Supplier",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=130, height=34,
                      command=self._open_add).pack(side="right", padx=16, pady=13)

        ctk.CTkButton(topbar, text="Delete",
                      fg_color=COLORS["red"], hover_color="#9F2F24",
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=90, height=34,
                      command=self._delete).pack(side="right", padx=(0, 8), pady=13)

        ctk.CTkButton(topbar, text="Edit",
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"], font=FONTS["body"],
                      width=80, height=34,
                      command=self._open_edit).pack(side="right", padx=(0, 8), pady=13)

        COLS = [
            {"id": "name",    "label": "Supplier Name",  "width": 200},
            {"id": "contact", "label": "Contact Person",
                "width": 160, "stretch": False},
            {"id": "phone",   "label": "Phone",
                "width": 140, "stretch": False},
            {"id": "email",   "label": "Email",
                "width": 200, "stretch": False},
            {"id": "status",  "label": "Status",         "width": 80,
                "stretch": False, "anchor": "center"},
        ]
        tbl_frame = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0)
        tbl_frame.pack(fill="both", expand=True)
        self.table = DataTable(tbl_frame, COLS, height=28,
                               on_double_click=self._on_double)
        self.table.pack(fill="both", expand=True)

        ctx = tk.Menu(self, tearoff=0, bg=COLORS["card"], fg=COLORS["txt"],
                      activebackground=COLORS["blue_bg"], activeforeground=COLORS["blue"],
                      font=("Helvetica", 12))
        ctx.add_command(label="✎  Edit Supplier",   command=self._open_edit)
        ctx.add_command(label="🗑  Delete Supplier", command=self._delete)
        self.table.tree.bind("<Button-3>", lambda e: self._show_ctx(e, ctx))

        self.refresh()

    def refresh(self):
        db = get_session()
        try:
            suppliers = SupplierService(db).get_all()
            rows = [{"id": s.id, "values": (
                s.name,
                s.contact_name or "—",
                s.phone or "—",
                s.email or "—",
                "Active" if s.is_active else "Inactive",
            )} for s in suppliers]
        finally:
            db.close()
        self.table.load(rows)

    def _show_ctx(self, event, menu):
        iid = self.table.tree.identify_row(event.y)
        if iid:
            self.table.tree.selection_set(iid)
            menu.tk_popup(event.x_root, event.y_root)

    def _on_double(self, _):
        self._open_edit()

    def _supplier_form(self, modal, defaults: dict = None):
        d = defaults or {}
        vars_ = {k: tk.StringVar(value=d.get(k, ""))
                 for k in ["name", "contact_name", "phone", "email", "address", "notes"]}

        field_row(modal.body, "Supplier Name", lambda p: ctk.CTkEntry(
            p, textvariable=vars_["name"], fg_color=COLORS["bg"],
            border_color=COLORS["border"], text_color=COLORS["txt"],
            font=FONTS["body"], height=36), required=True)

        field_row(modal.body, "Contact Person", lambda p: ctk.CTkEntry(
            p, textvariable=vars_["contact_name"], fg_color=COLORS["bg"],
            border_color=COLORS["border"], text_color=COLORS["txt"],
            font=FONTS["body"], height=36))

        row = ctk.CTkFrame(modal.body, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 12))
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        for col, key in enumerate(["phone", "email"]):
            f = ctk.CTkFrame(row, fg_color="transparent")
            f.grid(row=0, column=col, padx=(
                0 if col == 0 else 8, 0), sticky="ew")
            ctk.CTkLabel(f, text=key.upper(), font=FONTS["label"],
                         text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 4))
            ctk.CTkEntry(f, textvariable=vars_[key], fg_color=COLORS["bg"],
                         border_color=COLORS["border"], text_color=COLORS["txt"],
                         font=FONTS["body"], height=36).pack(fill="x")

        field_row(modal.body, "Address", lambda p: ctk.CTkEntry(
            p, textvariable=vars_["address"], fg_color=COLORS["bg"],
            border_color=COLORS["border"], text_color=COLORS["txt"],
            font=FONTS["body"], height=36))

        return vars_

    def _open_add(self):
        m = Modal(self, "Add Supplier", width=500, height=460)
        vars_ = self._supplier_form(m)
        err = ctk.CTkLabel(
            m.body, text="", font=FONTS["small"], text_color=COLORS["red"])
        err.pack(padx=20, anchor="w")

        def confirm():
            if not vars_["name"].get().strip():
                err.configure(text="Supplier name is required.")
                return
            schema = SupplierCreate(
                name=vars_["name"].get().strip(),
                contact_name=vars_["contact_name"].get().strip() or None,
                phone=vars_["phone"].get().strip() or None,
                email=vars_["email"].get().strip() or None,
                address=vars_["address"].get().strip() or None,
            )
            db = get_session()
            try:
                SupplierService(db).create(schema)
            finally:
                db.close()
            m.destroy()
            self.refresh()
            Toast(self.app, "Supplier added.", kind="success")

        m.add_footer_buttons("Cancel", "Add Supplier", on_confirm=confirm)

    def _open_edit(self):
        iid = self.table.get_selected_iid()
        if not iid:
            Toast(self.app, "Select a supplier first.", kind="warning")
            return
        sid = int(iid)
        db = get_session()
        try:
            s = SupplierService(db).get_by_id(sid)
        finally:
            db.close()
        if not s:
            return

        m = Modal(self, f"Edit — {s.name}", width=500, height=460)
        vars_ = self._supplier_form(m, {
            "name": s.name, "contact_name": s.contact_name or "",
            "phone": s.phone or "", "email": s.email or "",
            "address": s.address or "",
        })
        err = ctk.CTkLabel(
            m.body, text="", font=FONTS["small"], text_color=COLORS["red"])
        err.pack(padx=20, anchor="w")

        def confirm():
            if not vars_["name"].get().strip():
                err.configure(text="Supplier name is required.")
                return
            schema = SupplierUpdate(
                name=vars_["name"].get().strip(),
                contact_name=vars_["contact_name"].get().strip() or None,
                phone=vars_["phone"].get().strip() or None,
                email=vars_["email"].get().strip() or None,
                address=vars_["address"].get().strip() or None,
            )
            db = get_session()
            try:
                SupplierService(db).update(sid, schema)
            finally:
                db.close()
            m.destroy()
            self.refresh()
            Toast(self.app, "Supplier updated.", kind="success")

        m.add_footer_buttons("Cancel", "Save Changes", on_confirm=confirm)

    def _delete(self):
        iid = self.table.get_selected_iid()
        if not iid:
            Toast(self.app, "Select a supplier first.", kind="warning")
            return

        if tk.messagebox.askyesno(
            "Delete Supplier",
            "Delete this supplier?\n\nThis will remove it from the active supplier list but keep old stock-in history safe.",
            parent=self
        ):
            db = get_session()
            try:
                SupplierService(db).delete(int(iid))
            finally:
                db.close()

            self.refresh()
            Toast(self.app, "Supplier deleted.", kind="warning")
