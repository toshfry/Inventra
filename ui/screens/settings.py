import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, colorchooser, filedialog
from config.themes import COLORS, FONTS
from ui.components.toast import Toast
from ui.components.data_table import DataTable
from ui.components.modal import Modal
from config.settings import APP_VERSION, DB_PATH, BACKUP_DIR, EXPORT_DIR
from database.engine import get_session
from database.models.category import Category
from core.services.auth_service import AuthService, get_current_user, is_admin
from core.services.settings_service import SettingsService
from utils.backup import create_backup, list_backups, restore_backup
from core.licensing.license_manager import activate_from_key, get_computer_id, license_status
import os
import subprocess
import sys
import threading
import socket


# ── Web-server state (module-level so it persists) ──────────────────────────
_web_thread = None
_web_server = None   # werkzeug server instance


def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _start_flask(port=5000):
    """Run Flask in background thread, returns the server object."""
    import sys
    import os
    # Make sure imports work when running from PyInstaller
    sys.path.insert(0, os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))
    from werkzeug.serving import make_server
    import importlib
    ws = importlib.import_module("web_server")
    srv = make_server("0.0.0.0", port, ws.app)
    return srv


# ── Settings Screen ──────────────────────────────────────────────────────────
class SettingsScreen(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(
            parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self.app = app
        self._web_running = False
        self._web_port = 5000
        self._build()

    def _build(self):
        topbar = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0, height=60)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)
        title_wrap = ctk.CTkFrame(topbar, fg_color="transparent")
        title_wrap.pack(side="left", padx=24, pady=10)
        ctk.CTkLabel(title_wrap, text="Settings", font=FONTS["title"],
                     text_color=COLORS["txt"]).pack(anchor="w")
        ctk.CTkLabel(title_wrap, text="Configure Inventra to fit your shop",
                     font=FONTS["small"],
                     text_color=COLORS["txt3"]).pack(anchor="w")

        scroll = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["bg"], corner_radius=0)
        scroll.pack(fill="both", expand=True)

        if is_admin():
            self._section(scroll, "User Management", icon="👤")
            self._build_users(scroll)

            self._section(scroll, "Categories", icon="🏷")
            self._build_categories(scroll)

            self._section(scroll, "POS — Tax & Receipt", icon="🧾")
            self._build_pos_settings(scroll)

            self._section(scroll, "Service / Other Fees", icon="🧰")
            self._build_fee_types(scroll)

        self._section(scroll, "Web Server (LAN Access)", icon="🌐")
        self._build_web_server(scroll)

        self._section(scroll, "Database & Backup", icon="🗄")
        self._build_backup(scroll)

        self._section(scroll, "License & Activation", icon="🔑")
        self._build_license(scroll)

        self._section(scroll, "Exports", icon="📁")
        exp_card = self._card(scroll)
        self._info_row(exp_card, "Export Folder", EXPORT_DIR)
        ctk.CTkButton(exp_card, text="📁  Open Export Folder",
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"], font=FONTS["body"],
                      width=170, height=36,
                      command=lambda: self._open_folder(EXPORT_DIR)
                      ).pack(anchor="w", padx=20, pady=(0, 16))

        self._section(scroll, "About", icon="ℹ")
        about = self._card(scroll)

        inner = ctk.CTkFrame(about, fg_color="transparent")
        inner.pack(padx=30, pady=28)

        # Logo (the uploaded logo is shown ONLY here, in About).
        self._about_logo = self._load_about_logo(104)
        if self._about_logo:
            ctk.CTkLabel(inner, image=self._about_logo, text="").pack(pady=(0, 14))

        name = ctk.CTkFrame(inner, fg_color="transparent")
        name.pack()
        ctk.CTkLabel(name, text="Invent", font=("Helvetica", 26, "bold"),
                     text_color=COLORS["navy"]).pack(side="left", padx=0)
        ctk.CTkLabel(name, text="ra", font=("Helvetica", 26, "bold"),
                     text_color="#F59E0B").pack(side="left", padx=0)
        ctk.CTkLabel(inner, text="Automotive Inventory & Sales System",
                     font=FONTS["body"], text_color=COLORS["txt2"]).pack(pady=(4, 18))

        ctk.CTkFrame(inner, fg_color=COLORS["border"], height=1).pack(
            fill="x", pady=(0, 18))

        current_user = get_current_user()
        current_user_name = (
            getattr(current_user, "full_name", None)
            or getattr(current_user, "username", None)
            or "Unknown"
        )
        specs = [
            ("Version", f"{APP_VERSION}"),
            ("Database", "SQLite"),
            ("Desktop UI", "CustomTkinter"),
            ("Web UI", "Vanilla JS SPA"),
            ("Backend", "Flask + SQLAlchemy"),
            ("Reports", "openpyxl (.xlsx)"),
            ("Validation", "Pydantic"),
            ("Web Server", "Waitress (LAN)"),
            ("Current User", current_user_name),
            ("Developer", "John Lloyd Sereno (toshfry)"),
        ]
        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="spec")
        for i, (label, value) in enumerate(specs):
            cell = ctk.CTkFrame(grid, fg_color="transparent")
            cell.grid(row=i // 2, column=i % 2, sticky="w", padx=14, pady=7)
            ctk.CTkLabel(cell, text=f"{label}:", font=("Helvetica", 13, "bold"),
                         text_color=COLORS["txt"]).pack(side="left")
            ctk.CTkLabel(cell, text=f" {value}", font=FONTS["body"],
                         text_color=COLORS["txt2"]).pack(side="left")

        ctk.CTkFrame(inner, fg_color=COLORS["border"], height=1).pack(
            fill="x", pady=(20, 14))
        ctk.CTkLabel(
            inner,
            text=("Inventra runs locally on your computer and can be accessed from phones\n"
                  "and tablets on the same Wi-Fi network through the Network URL shown\n"
                  "in Settings → Web Server (LAN Access)."),
            font=FONTS["small"], text_color=COLORS["txt2"],
            justify="center").pack()

    def _load_about_logo(self, size):
        """Load the Inventra logo (About page only) as a CTkImage, or None."""
        try:
            import os
            from PIL import Image
            root = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__))))
            img = Image.open(os.path.join(root, "assets", "logo.png"))
            return ctk.CTkImage(light_image=img, dark_image=img,
                                size=(size, size))
        except Exception:
            return None

    def refresh(self):
        """Reload data that may have changed elsewhere (e.g. categories or users
        added from the web app) so the desktop stays in sync without a restart.
        Called by the app router each time the Settings screen is shown."""
        for fn in (getattr(self, "_refresh_categories", None),
                   getattr(self, "_refresh_users", None),
                   getattr(self, "_refresh_fee_types", None)):
            if fn:
                try:
                    fn()
                except Exception:
                    pass

    # ── Web Server panel ──────────────────────────────────────────────
    def _build_web_server(self, parent):
        card = self._card(parent)

        # Status row
        status_row = ctk.CTkFrame(card, fg_color="transparent")
        status_row.pack(fill="x", padx=20, pady=(14, 6))

        ctk.CTkLabel(status_row, text="Status", font=FONTS["body"],
                     text_color=COLORS["txt"], width=130, anchor="w").pack(side="left")
        self._ws_status_lbl = ctk.CTkLabel(status_row, text="⏸  Stopped",
                                           font=FONTS["body"],
                                           text_color=COLORS["txt3"])
        self._ws_status_lbl.pack(side="left")
        ctk.CTkFrame(card, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20)

        # IP row (shown when running)
        ip_row = ctk.CTkFrame(card, fg_color="transparent")
        ip_row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(ip_row, text="Browser URL", font=FONTS["body"],
                     text_color=COLORS["txt"], width=130, anchor="w").pack(side="left")
        self._ws_url_lbl = ctk.CTkLabel(ip_row, text="—",
                                        font=FONTS["body"],
                                        text_color=COLORS["txt3"])
        self._ws_url_lbl.pack(side="left")
        ctk.CTkFrame(card, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20)

        # Port row
        port_row = ctk.CTkFrame(card, fg_color="transparent")
        port_row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(port_row, text="Port", font=FONTS["body"],
                     text_color=COLORS["txt"], width=130, anchor="w").pack(side="left")
        self._port_var = tk.StringVar(value=str(self._web_port))
        port_entry = ctk.CTkEntry(port_row, textvariable=self._port_var,
                                  width=80, height=30,
                                  fg_color=COLORS["bg2"],
                                  border_color=COLORS["border"],
                                  font=FONTS["body"])
        port_entry.pack(side="left")
        ctk.CTkFrame(card, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20)

        # Buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 16))

        self._ws_start_btn = ctk.CTkButton(
            btn_row, text="▶  Start Server",
            fg_color=COLORS["green"], hover_color="#1f6b43",
            text_color="#FFFFFF", font=FONTS["body"],
            width=140, height=36,
            command=self._start_web_server)
        self._ws_start_btn.pack(side="left", padx=(0, 10))

        self._ws_stop_btn = ctk.CTkButton(
            btn_row, text="⏹  Stop Server",
            fg_color=COLORS["red"], hover_color="#a93226",
            text_color="#FFFFFF", font=FONTS["body"],
            width=140, height=36,
            state="disabled",
            command=self._stop_web_server)
        self._ws_stop_btn.pack(side="left")

        # Info note
        ctk.CTkLabel(card,
                     text="Open the browser URL on any device connected to the same WiFi network.",
                     font=FONTS["small"], text_color=COLORS["txt3"],
                     wraplength=520, anchor="w"
                     ).pack(anchor="w", padx=20, pady=(0, 12))

    def _start_web_server(self):
        global _web_thread, _web_server
        if self._web_running:
            return
        try:
            port = int(self._port_var.get())
        except ValueError:
            port = 5000
            self._port_var.set("5000")
        self._web_port = port

        try:
            srv = _start_flask(port)
        except Exception as e:
            messagebox.showerror("Web Server Error",
                                 f"Could not start server:\n{e}", parent=self)
            return

        _web_server = srv
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        _web_thread = t

        self._web_running = True
        ip = _get_local_ip()
        url = f"http://{ip}:{port}"
        self._ws_status_lbl.configure(
            text="▶  Running", text_color=COLORS["green"])
        self._ws_url_lbl.configure(text=url, text_color=COLORS["navy"])
        self._ws_start_btn.configure(state="disabled")
        self._ws_stop_btn.configure(state="normal")
        Toast(self.app, f"Web server started — {url}", kind="success")

    def _stop_web_server(self):
        global _web_server
        if not self._web_running:
            return
        if _web_server:
            threading.Thread(target=_web_server.shutdown, daemon=True).start()
            _web_server = None
        self._web_running = False
        self._ws_status_lbl.configure(
            text="⏸  Stopped", text_color=COLORS["txt3"])
        self._ws_url_lbl.configure(text="—", text_color=COLORS["txt3"])
        self._ws_start_btn.configure(state="normal")
        self._ws_stop_btn.configure(state="disabled")
        Toast(self.app, "Web server stopped.", kind="warning")

    # ── POS Tax & Receipt panel ───────────────────────────────────────
    def _build_pos_settings(self, parent):
        card = self._card(parent)
        db = get_session()
        try:
            cfg = SettingsService(db).get_pos_settings()
        finally:
            db.close()

        self._pos_vars = {}

        def _entry_row(key, label, hint=""):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(row, text=label, font=FONTS["body"], text_color=COLORS["txt"],
                         width=180, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(cfg.get(key, "")))
            ctk.CTkEntry(row, textvariable=var, fg_color=COLORS["bg2"],
                         border_color=COLORS["border"], text_color=COLORS["txt"],
                         font=FONTS["body"], height=34).pack(
                side="left", fill="x", expand=True)
            self._pos_vars[key] = var
            return var

        def _bool_row(key, label):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=6)
            var = tk.BooleanVar(value=bool(cfg.get(key)))
            ctk.CTkSwitch(row, text=label, variable=var,
                          font=FONTS["body"], text_color=COLORS["txt"],
                          progress_color=COLORS["green"]).pack(side="left")
            self._pos_vars[key] = var

        def _choice_row(key, label, options):
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(row, text=label, font=FONTS["body"], text_color=COLORS["txt"],
                         width=180, anchor="w").pack(side="left")
            var = tk.StringVar(value=str(cfg.get(key, options[0])))
            ctk.CTkOptionMenu(row, variable=var, values=options,
                              fg_color=COLORS["bg2"], button_color=COLORS["border"],
                              text_color=COLORS["txt"], font=FONTS["body"],
                              dropdown_fg_color=COLORS["card"], height=34).pack(side="left")
            self._pos_vars[key] = var

        ctk.CTkLabel(card, text="TAX", font=FONTS["label"], text_color=COLORS["txt3"]
                     ).pack(anchor="w", padx=20, pady=(14, 0))
        _bool_row("tax_enabled", "Enable tax")
        _entry_row("tax_name", "Tax name")
        _entry_row("tax_rate", "Tax rate (%)")
        _choice_row("tax_apply", "Apply tax", ["after_discount", "before_discount"])
        ctk.CTkLabel(card, text="Tax is applied after discounts by default.",
                     font=FONTS["small"], text_color=COLORS["txt3"]).pack(
            anchor="w", padx=20, pady=(0, 6))

        ctk.CTkLabel(card, text="RECEIPT", font=FONTS["label"], text_color=COLORS["txt3"]
                     ).pack(anchor="w", padx=20, pady=(10, 0))
        _entry_row("store_name", "Business / store name")
        _entry_row("store_address", "Store address")
        _entry_row("store_phone", "Phone / contact")
        _entry_row("receipt_footer", "Footer message")
        _choice_row("paper_size", "Paper size", ["58mm", "80mm", "Letter", "A4"])
        _bool_row("show_cashier", "Show cashier name on receipt")
        _bool_row("show_sku", "Show SKU on receipt")
        _bool_row("show_tax_breakdown", "Show tax breakdown on receipt")

        ctk.CTkButton(card, text="💾  Save POS Settings",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"], height=38,
                      command=self._save_pos_settings).pack(
            anchor="w", padx=20, pady=(10, 16))

    def _save_pos_settings(self):
        updates = {}
        for key, var in self._pos_vars.items():
            val = var.get()
            if key == "tax_rate":
                try:
                    val = float(val or 0)
                except ValueError:
                    messagebox.showerror("Invalid", "Tax rate must be a number.", parent=self)
                    return
            updates[key] = val
        db = get_session()
        try:
            SettingsService(db).update_pos_settings(updates)
            Toast(self.app, "POS settings saved.", kind="success")
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)
        finally:
            db.close()

    # ── Service / Other Fees panel ────────────────────────────────────
    def _build_fee_types(self, parent):
        card = self._card(parent)
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 8))
        ctk.CTkLabel(hdr, text="Fee Types (POS service/other charges)",
                     font=("Helvetica", 13, "bold"),
                     text_color=COLORS["txt"]).pack(side="left")
        ctk.CTkButton(hdr, text="+ Add Fee Type",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["small"], width=130, height=30,
                      command=self._open_add_fee).pack(side="right")

        COLS = [
            {"id": "name", "label": "Name", "width": 240},
            {"id": "amount", "label": "Default", "width": 110,
             "stretch": False, "anchor": "e"},
        ]
        self._fee_table = DataTable(card, COLS, height=5,
                                    on_double_click=self._edit_fee_by_iid)
        self._fee_table.pack(fill="x", padx=0)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 16))
        ctk.CTkButton(btn_row, text="✎  Edit", fg_color=COLORS["bg2"],
                      hover_color=COLORS["border"], text_color=COLORS["txt2"],
                      font=FONTS["small"], width=90, height=30,
                      command=lambda: self._edit_fee_by_iid(
                          self._fee_table.get_selected_iid())).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="✕  Delete", fg_color=COLORS["red_bg"],
                      hover_color="#F5CACA", text_color=COLORS["red"],
                      font=FONTS["small"], width=90, height=30,
                      command=self._delete_fee).pack(side="left")
        self._refresh_fee_types()

    def _refresh_fee_types(self):
        db = get_session()
        try:
            self._fee_types = SettingsService(db).get_fee_types()
        finally:
            db.close()
        self._fee_table.load([
            {"id": i, "values": (f["name"], f"₱{f['default_amount']:,.2f}")}
            for i, f in enumerate(self._fee_types)])

    def _save_fee_types(self):
        db = get_session()
        try:
            self._fee_types = SettingsService(db).set_fee_types(self._fee_types)
        finally:
            db.close()
        self._refresh_fee_types()

    def _open_add_fee(self):
        _FeeTypeDialog(self, "Add Fee Type", on_save=lambda n, a: (
            self._fee_types.append({"name": n, "default_amount": a}),
            self._save_fee_types()))

    def _edit_fee_by_iid(self, iid):
        if iid is None:
            return
        i = int(iid)
        if i >= len(self._fee_types):
            return
        f = self._fee_types[i]
        _FeeTypeDialog(self, f"Edit — {f['name']}", initial_name=f["name"],
                       initial_amount=f["default_amount"],
                       on_save=lambda n, a: (
                           self._fee_types.__setitem__(i, {"name": n, "default_amount": a}),
                           self._save_fee_types()))

    def _delete_fee(self):
        iid = self._fee_table.get_selected_iid()
        if iid is None:
            return
        i = int(iid)
        if i < len(self._fee_types):
            del self._fee_types[i]
            self._save_fee_types()

    # ── Categories panel ──────────────────────────────────────────────
    def _build_categories(self, parent):
        card = self._card(parent)

        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 8))
        ctk.CTkLabel(hdr, text="Part Categories",
                     font=("Helvetica", 13, "bold"),
                     text_color=COLORS["txt"]).pack(side="left")
        ctk.CTkButton(hdr, text="+ Add Category",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["small"],
                      width=120, height=30,
                      command=self._open_add_category).pack(side="right")

        COLS = [
            {"id": "color", "label": "Color",  "width": 60,  "stretch": False},
            {"id": "name",  "label": "Name",   "width": 200},
            {"id": "parts", "label": "Parts",  "width": 60,
                "stretch": False, "anchor": "center"},
        ]
        self._cat_table = DataTable(card, COLS, height=6,
                                    on_double_click=self._edit_category_by_iid)
        self._cat_table.pack(fill="x", padx=0)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 16))
        ctk.CTkButton(btn_row, text="✎  Edit",
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"], font=FONTS["small"],
                      width=90, height=30,
                      command=lambda: self._edit_category_by_iid(
                          self._cat_table.get_selected_iid())
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="✕  Delete",
                      fg_color=COLORS["red_bg"], hover_color="#F5CACA",
                      text_color=COLORS["red"], font=FONTS["small"],
                      width=90, height=30,
                      command=self._delete_category).pack(side="left")

        self._refresh_categories()

    def _refresh_categories(self):
        db = get_session()
        try:
            cats = db.query(Category).order_by(Category.name).all()
            self._cat_data = {str(c.id): c for c in cats}
            rows = [{"id": c.id, "values": (
                c.color_hex, c.name, str(len(c.parts))
            )} for c in cats]
        finally:
            db.close()
        self._cat_table.load(rows)

    def _open_add_category(self):
        _CategoryDialog(self, title="Add Category",
                        on_save=self._do_create_category)

    def _edit_category_by_iid(self, iid):
        if not iid:
            return
        cat = self._cat_data.get(str(iid))
        if not cat:
            return
        _CategoryDialog(self, title=f"Edit — {cat.name}",
                        initial_name=cat.name,
                        initial_color=cat.color_hex,
                        on_save=lambda n, c: self._do_update_category(int(iid), n, c))

    def _do_create_category(self, name, color):
        db = get_session()
        try:
            if db.query(Category).filter(Category.name == name).first():
                messagebox.showerror(
                    "Duplicate", f"Category '{name}' already exists.", parent=self)
                return
            db.add(Category(name=name, color_hex=color))
            db.commit()
            Toast(self.app, f"Category '{name}' created.", kind="success")
            self._refresh_categories()
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error", str(e), parent=self)
        finally:
            db.close()

    def _do_update_category(self, cat_id, name, color):
        db = get_session()
        try:
            cat = db.get(Category, cat_id)
            clash = db.query(Category).filter(
                Category.name == name, Category.id != cat_id).first()
            if clash:
                messagebox.showerror(
                    "Duplicate", f"Name '{name}' already used.", parent=self)
                return
            cat.name = name
            cat.color_hex = color
            db.commit()
            Toast(self.app, "Category updated.", kind="success")
            self._refresh_categories()
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error", str(e), parent=self)
        finally:
            db.close()

    def _delete_category(self):
        iid = self._cat_table.get_selected_iid()
        if not iid:
            messagebox.showwarning(
                "No Selection", "Select a category first.", parent=self)
            return
        cat = self._cat_data.get(str(iid))
        if not cat:
            return
        if len(cat.parts) > 0:
            messagebox.showerror(
                "Cannot Delete",
                f"'{cat.name}' has {len(cat.parts)} part(s) assigned to it.\n"
                "Re-assign those parts to another category first.",
                parent=self)
            return
        if not messagebox.askyesno("Confirm Delete",
                                   f"Delete category '{cat.name}'? This cannot be undone.",
                                   parent=self):
            return
        db = get_session()
        try:
            obj = db.get(Category, int(iid))
            if obj:
                db.delete(obj)
                db.commit()
            Toast(self.app, f"Category '{cat.name}' deleted.", kind="warning")
            self._refresh_categories()
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error", str(e), parent=self)
        finally:
            db.close()

    # ── User management panel ─────────────────────────────────────────
    def _build_users(self, parent):
        card = self._card(parent)
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 8))
        ctk.CTkLabel(hdr, text="System Users",
                     font=("Helvetica", 13, "bold"),
                     text_color=COLORS["txt"]).pack(side="left")
        ctk.CTkButton(hdr, text="+ Add User",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["small"],
                      width=100, height=30,
                      command=self._open_add_user).pack(side="right")

        COLS = [
            {"id": "user",   "label": "Username",  "width": 130, "stretch": False},
            {"id": "name",   "label": "Full Name",  "width": 180},
            {"id": "role",   "label": "Role",       "width": 80,
                "stretch": False, "anchor": "center"},
            {"id": "status", "label": "Status",     "width": 80,
                "stretch": False, "anchor": "center"},
        ]
        self._user_table = DataTable(card, COLS, height=6,
                                     on_double_click=self._edit_user)
        self._user_table.pack(fill="x", padx=0)

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(8, 16))
        ctk.CTkButton(btn_row, text="✎  Edit User",
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"], font=FONTS["small"],
                      width=110, height=30,
                      command=lambda: self._edit_user(
                          self._user_table.get_selected_iid())
                      ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="✕  Deactivate",
                      fg_color=COLORS["red_bg"], hover_color="#F5CACA",
                      text_color=COLORS["red"], font=FONTS["small"],
                      width=110, height=30,
                      command=self._deactivate_user).pack(side="left")

        self._refresh_users()

    def _refresh_users(self):
        db = get_session()
        try:
            users = AuthService(db).get_all_users()
        finally:
            db.close()
        rows = [{"id": u.id, "values": (
            u.username, u.full_name, u.role.title(),
            "Active" if u.is_active else "Inactive",
        ), "_tag": "" if u.is_active else "warn"} for u in users]
        self._user_table.load(rows)

    def _open_add_user(self):
        m = Modal(self, "Add User", width=440, height=420)
        user_var = tk.StringVar()
        name_var = tk.StringVar()
        role_var = tk.StringVar(value="staff")
        pass_var = tk.StringVar()
        pass2_var = tk.StringVar()

        def _field(lbl, var, placeholder="", show=None):
            f = ctk.CTkFrame(m.body, fg_color="transparent")
            f.pack(fill="x", padx=20, pady=(0, 10))
            ctk.CTkLabel(f, text=lbl.upper(), font=FONTS["label"],
                         text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))
            kw = {"show": show} if show else {}
            ctk.CTkEntry(f, textvariable=var, placeholder_text=placeholder,
                         fg_color=COLORS["bg"], border_color=COLORS["border"],
                         text_color=COLORS["txt"], font=FONTS["body"],
                         height=36, **kw).pack(fill="x")

        _field("Username",         user_var,  "e.g. jsmith")
        _field("Full Name",        name_var,  "e.g. John Smith")

        rf = ctk.CTkFrame(m.body, fg_color="transparent")
        rf.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(rf, text="ROLE", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 4))
        for role, desc in [("admin", "Admin — full access"), ("staff", "Staff — all access except Settings")]:
            ctk.CTkRadioButton(rf, text=desc, variable=role_var, value=role,
                               fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                               text_color=COLORS["txt"], font=FONTS["body"]).pack(anchor="w", pady=1)

        _field("Password",         pass_var,  "Min 6 characters", show="●")
        _field("Confirm Password", pass2_var, "Re-enter password", show="●")

        err = ctk.CTkLabel(
            m.body, text="", font=FONTS["small"], text_color=COLORS["red"])
        err.pack(padx=20, anchor="w")

        def confirm():
            u = user_var.get().strip().lower()
            n = name_var.get().strip()
            p = pass_var.get()
            p2 = pass2_var.get()
            if not u:
                err.configure(text="Username required.")
                return
            if not n:
                err.configure(text="Full name required.")
                return
            if len(p) < 6:
                err.configure(text="Password ≥ 6 chars.")
                return
            if p != p2:
                err.configure(text="Passwords do not match.")
                return
            db = get_session()
            try:
                AuthService(db).create_user(u, n, role_var.get(), p)
            except ValueError as e:
                err.configure(text=str(e))
                return
            finally:
                db.close()
            m.destroy()
            self._refresh_users()
            Toast(self.app, f"User '{u}' created.", kind="success")

        m.add_footer_buttons("Cancel", "Create User", on_confirm=confirm)

    def _edit_user(self, iid):
        if not iid:
            return
        uid = int(iid)
        db = get_session()
        try:
            users = AuthService(db).get_all_users()
            user = next((u for u in users if u.id == uid), None)
        finally:
            db.close()
        if not user:
            return

        m = Modal(self, f"Edit — {user.username}", width=440, height=340)
        name_var = tk.StringVar(value=user.full_name)
        role_var = tk.StringVar(value=user.role)
        pass_var = tk.StringVar()

        f1 = ctk.CTkFrame(m.body, fg_color="transparent")
        f1.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(f1, text="FULL NAME", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))
        ctk.CTkEntry(f1, textvariable=name_var, fg_color=COLORS["bg"],
                     border_color=COLORS["border"], text_color=COLORS["txt"],
                     font=FONTS["body"], height=36).pack(fill="x")

        rf = ctk.CTkFrame(m.body, fg_color="transparent")
        rf.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(rf, text="ROLE", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 4))
        for role, desc in [("admin", "Admin — full access"), ("staff", "Staff — all access except Settings")]:
            ctk.CTkRadioButton(rf, text=desc, variable=role_var, value=role,
                               fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                               text_color=COLORS["txt"], font=FONTS["body"]).pack(anchor="w", pady=1)

        f3 = ctk.CTkFrame(m.body, fg_color="transparent")
        f3.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(f3, text="NEW PASSWORD (leave blank to keep current)",
                     font=FONTS["label"], text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))
        ctk.CTkEntry(f3, textvariable=pass_var, show="●",
                     fg_color=COLORS["bg"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"], height=36).pack(fill="x")

        err = ctk.CTkLabel(
            m.body, text="", font=FONTS["small"], text_color=COLORS["red"])
        err.pack(padx=20, anchor="w")

        def confirm():
            db2 = get_session()
            try:
                AuthService(db2).update_user(uid,
                                             full_name=name_var.get().strip() or None,
                                             role=role_var.get(),
                                             password=pass_var.get() or None)
            except ValueError as e:
                err.configure(text=str(e))
                return
            finally:
                db2.close()
            m.destroy()
            self._refresh_users()
            Toast(self.app, "User updated.", kind="success")

        m.add_footer_buttons("Cancel", "Save Changes", on_confirm=confirm)

    def _deactivate_user(self):
        iid = self._user_table.get_selected_iid()
        if not iid:
            return
        if messagebox.askyesno("Confirm", "Deactivate this user?", parent=self):
            db = get_session()
            try:
                AuthService(db).deactivate_user(int(iid))
            except ValueError as e:
                messagebox.showerror("Error", str(e), parent=self)
                return
            finally:
                db.close()
            self._refresh_users()
            Toast(self.app, "User deactivated.", kind="warning")

    # ── License & Activation panel ─────────────────────────────────────
    def _build_license(self, parent):
        card = self._card(parent)
        self._license_labels = {}

        status = license_status()

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 8))

        self._license_status_badge = ctk.CTkLabel(
            header,
            text="",
            font=("Helvetica", 13, "bold"),
            text_color="#FFFFFF",
            fg_color=COLORS["green"] if status.get(
                "activated") else COLORS["red"],
            corner_radius=8,
            padx=12,
            pady=5,
        )
        self._license_status_badge.pack(side="left")

        ctk.CTkLabel(
            header,
            text="Manage the local Inventra license for this computer.",
            font=FONTS["small"],
            text_color=COLORS["txt3"],
            anchor="w",
        ).pack(side="left", padx=(12, 0), fill="x", expand=True)

        ctk.CTkFrame(card, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20)

        # Dynamic rows
        for key, label in [
            ("business_name", "Business Name"),
            ("owner_name", "Owner Name"),
            ("license_type", "License Type"),
            ("issued_at", "Issued Date"),
            ("expires_on", "Expiration Date"),
            ("days_remaining", "Days Remaining"),
            ("computer_id", "Computer ID"),
            ("license_file", "License File"),
        ]:
            self._license_info_row(card, key, label, "—")

        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(10, 16))

        ctk.CTkButton(
            btn_row,
            text="📋  Copy Computer ID",
            fg_color=COLORS["bg2"],
            hover_color=COLORS["border"],
            text_color=COLORS["txt2"],
            font=FONTS["body"],
            width=170,
            height=36,
            command=self._copy_computer_id,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="🔄  Refresh",
            fg_color=COLORS["bg2"],
            hover_color=COLORS["border"],
            text_color=COLORS["txt2"],
            font=FONTS["body"],
            width=110,
            height=36,
            command=self._refresh_license_info,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_row,
            text="🔑  Change License Key",
            fg_color=COLORS["navy"],
            hover_color=COLORS["navy_hover"],
            text_color="#FFFFFF",
            font=FONTS["body"],
            width=180,
            height=36,
            command=self._open_change_license,
        ).pack(side="right")

        self._refresh_license_info()

    def _license_info_row(self, parent, key, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            row,
            text=label,
            font=FONTS["body"],
            text_color=COLORS["txt"],
            width=160,
            anchor="w",
        ).pack(side="left")

        value_lbl = ctk.CTkLabel(
            row,
            text=value,
            font=FONTS["small"],
            text_color=COLORS["txt3"],
            anchor="w",
            wraplength=560,
        )
        value_lbl.pack(side="left", fill="x", expand=True)
        self._license_labels[key] = value_lbl

        ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20)

    def _format_license_type(self, value):
        if not value:
            return "—"
        return str(value).replace("_", " ").title()

    def _format_license_date(self, value):
        if not value:
            return "Lifetime / No expiration"
        text = str(value)
        # Keep only date part if ISO datetime is used.
        return text.split("T")[0] if "T" in text else text

    def _calculate_days_remaining(self, expires_on):
        if not expires_on:
            return "Lifetime"

        try:
            import datetime as _dt
            expiry = _dt.date.fromisoformat(str(expires_on).split("T")[0])
            days = (expiry - _dt.date.today()).days

            if days < 0:
                return f"Expired {abs(days)} day(s) ago"
            if days == 0:
                return "Expires today"
            return f"{days} day(s)"
        except Exception:
            return "—"

    def _refresh_license_info(self):
        try:
            status = license_status()
        except Exception as exc:
            status = {
                "activated": False,
                "message": str(exc),
                "computer_id": get_computer_id(),
            }

        activated = bool(status.get("activated"))

        if hasattr(self, "_license_status_badge"):
            self._license_status_badge.configure(
                text="✅  Activated" if activated else "⚠  Not Activated",
                fg_color=COLORS["green"] if activated else COLORS["red"],
            )

        expires_on = status.get("expires_on")

        values = {
            "business_name": status.get("business_name") or "—",
            "owner_name": status.get("owner_name") or "—",
            "license_type": self._format_license_type(status.get("license_type")),
            "issued_at": self._format_license_date(status.get("issued_at")) if status.get("issued_at") else "—",
            "expires_on": self._format_license_date(expires_on),
            "days_remaining": self._calculate_days_remaining(expires_on),
            "computer_id": status.get("computer_id") or get_computer_id(),
            "license_file": status.get("license_file") or "—",
        }

        for key, value in values.items():
            lbl = getattr(self, "_license_labels", {}).get(key)
            if lbl:
                lbl.configure(text=str(value))

        # Make expiration warning easier to notice.
        days_lbl = getattr(self, "_license_labels", {}).get("days_remaining")
        if days_lbl:
            text = values["days_remaining"].lower()
            if "expired" in text or "today" in text:
                days_lbl.configure(text_color=COLORS["red"])
            elif text.endswith("day(s)") and text.split()[0].isdigit() and int(text.split()[0]) <= 30:
                days_lbl.configure(text_color=COLORS["amber"])
            else:
                days_lbl.configure(text_color=COLORS["txt3"])

    def _copy_computer_id(self):
        computer_id = get_computer_id()
        try:
            self.clipboard_clear()
            self.clipboard_append(computer_id)
            Toast(self.app, "Computer ID copied.", kind="success")
        except Exception:
            messagebox.showinfo("Computer ID", computer_id, parent=self)

    def _open_change_license(self):
        _ChangeLicenseDialog(
            self,
            on_success=lambda: (
                self._refresh_license_info(),
                Toast(self.app, "License updated successfully.", kind="success"),
            ),
        )

    # ── Backup panel ──────────────────────────────────────────────────
    def _build_backup(self, parent):
        card = self._card(parent)
        self._info_row(card, "Database File", DB_PATH)
        self._info_row(card, "Backup Folder", BACKUP_DIR)
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 6))
        ctk.CTkButton(btn_row, text="⬆  Backup Now",
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=140, height=36,
                      command=self._do_backup).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="⟲  Restore Backup",
                      fg_color=COLORS["amber"], hover_color="#d8620a",
                      text_color="#FFFFFF", font=FONTS["body"],
                      width=160, height=36,
                      command=self._open_restore_dialog).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btn_row, text="📁  Open Folder",
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"], font=FONTS["body"],
                      width=130, height=36,
                      command=lambda: self._open_folder(BACKUP_DIR)).pack(side="left")
        ctk.CTkLabel(card,
                     text="Restoring overwrites your current database with a saved backup. "
                          "A safety backup of the current data is taken first.",
                     font=FONTS["small"], text_color=COLORS["txt3"],
                     wraplength=560, anchor="w", justify="left"
                     ).pack(anchor="w", padx=20, pady=(0, 14))

    def _open_restore_dialog(self):
        _RestoreDialog(self, app=self.app)

    # ── Helpers ───────────────────────────────────────────────────────
    def _section(self, parent, title, icon=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(22, 8))

        if icon:
            ctk.CTkLabel(row, text=icon, width=26, height=26, corner_radius=8,
                         fg_color=COLORS["navy_bg"], text_color=COLORS["navy"],
                         font=("Helvetica", 13)).pack(side="left", padx=(0, 10))

        ctk.CTkLabel(row, text=title.upper(), font=FONTS["label"],
                     text_color=COLORS["txt2"]).pack(side="left")

    def _card(self, parent):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=14,
                            border_width=1, border_color=COLORS["border"])
        card.pack(fill="x", padx=20, pady=(0, 4))
        return card

    def _info_row(self, parent, label, value):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=8)
        ctk.CTkLabel(row, text=label, font=FONTS["body"],
                     text_color=COLORS["txt"], width=160, anchor="w").pack(side="left")
        ctk.CTkLabel(row, text=value, font=FONTS["small"],
                     text_color=COLORS["txt3"], anchor="w",
                     wraplength=500).pack(side="left", fill="x", expand=True)
        ctk.CTkFrame(parent, fg_color=COLORS["border"], height=1).pack(
            fill="x", padx=20)

    def _do_backup(self):
        path = create_backup()
        Toast(self.app, "Backup created." if path else "Nothing to backup yet.",
              kind="success" if path else "info")

    def _open_folder(self, path):
        os.makedirs(path, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# ── Change License Dialog ─────────────────────────────────────────────────────
class _ChangeLicenseDialog(ctk.CTkToplevel):

    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.parent = parent
        self.on_success = on_success

        self.title("Change License Key")
        self.geometry("640x560")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])

        self.grab_set()
        self.lift()
        self.focus_force()
        self._centre(parent)
        self._build()

    def _centre(self, parent):
        self.update_idletasks()
        w, h = 640, 560
        try:
            px = parent.winfo_rootx() + parent.winfo_width() // 2
            py = parent.winfo_rooty() + parent.winfo_height() // 2
        except Exception:
            px, py = 640, 400
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    def _build(self):
        hdr = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        ctk.CTkLabel(
            hdr,
            text="Change License Key",
            font=FONTS["heading"],
            text_color=COLORS["txt"],
        ).pack(side="left", padx=20, pady=16)
        # Native title-bar close only (no redundant custom ✕).

        # Footer is packed BEFORE the expandable body so the buttons never disappear.
        footer = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0, height=62)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        ctk.CTkButton(
            footer,
            text="Cancel",
            width=110,
            fg_color=COLORS["bg2"],
            text_color=COLORS["txt"],
            hover_color=COLORS["border"],
            command=self.destroy,
        ).pack(side="right", padx=10, pady=13)

        ctk.CTkButton(
            footer,
            text="Apply New License",
            width=170,
            fg_color=COLORS["navy"],
            hover_color=COLORS["navy_hover"],
            text_color="#FFFFFF",
            command=self._apply_license,
        ).pack(side="right", padx=(0, 4), pady=13)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=18)

        ctk.CTkLabel(
            body,
            text="Paste the new activation key from the developer.",
            font=FONTS["body"],
            text_color=COLORS["txt"],
            anchor="w",
        ).pack(fill="x")

        ctk.CTkLabel(
            body,
            text="The old license will only be replaced if the new key is valid for this computer.",
            font=FONTS["small"],
            text_color=COLORS["txt3"],
            anchor="w",
            wraplength=580,
        ).pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(
            body,
            text="CURRENT COMPUTER ID",
            font=FONTS["label"],
            text_color=COLORS["txt3"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        id_row = ctk.CTkFrame(body, fg_color="transparent")
        id_row.pack(fill="x", pady=(0, 12))

        computer_id = get_computer_id()
        self._computer_id_entry = ctk.CTkEntry(
            id_row,
            height=34,
            fg_color=COLORS["bg2"],
            border_color=COLORS["border"],
            text_color=COLORS["txt"],
            font=FONTS["body"],
        )
        self._computer_id_entry.pack(
            side="left", fill="x", expand=True, padx=(0, 8))
        self._computer_id_entry.insert(0, computer_id)
        self._computer_id_entry.configure(state="readonly")

        ctk.CTkButton(
            id_row,
            text="Copy",
            width=80,
            height=34,
            fg_color=COLORS["bg2"],
            hover_color=COLORS["border"],
            text_color=COLORS["txt2"],
            command=self._copy_id,
        ).pack(side="right")

        ctk.CTkLabel(
            body,
            text="NEW LICENSE KEY",
            font=FONTS["label"],
            text_color=COLORS["txt3"],
            anchor="w",
        ).pack(fill="x", pady=(0, 4))

        self._key_box = ctk.CTkTextbox(
            body,
            height=180,
            fg_color=COLORS["card"],
            border_color=COLORS["border"],
            border_width=1,
            text_color=COLORS["txt"],
            font=("Consolas", 11),
            wrap="word",
        )
        self._key_box.pack(fill="x")

        self._status = ctk.CTkLabel(
            body,
            text="",
            font=FONTS["small"],
            text_color=COLORS["red"],
            anchor="w",
            wraplength=580,
        )
        self._status.pack(fill="x", pady=(10, 0))

    def _copy_id(self):
        computer_id = get_computer_id()
        try:
            self.clipboard_clear()
            self.clipboard_append(computer_id)
            self._status.configure(
                text="Computer ID copied.", text_color=COLORS["green"])
        except Exception:
            messagebox.showinfo("Computer ID", computer_id, parent=self)

    def _apply_license(self):
        key = self._key_box.get("1.0", "end").strip()

        if not key:
            self._status.configure(
                text="Please paste the new license key.", text_color=COLORS["red"])
            return

        valid, message, payload = activate_from_key(key)

        if not valid:
            self._status.configure(text=message, text_color=COLORS["red"])
            return

        business = payload.get(
            "business_name", "Inventra") if payload else "Inventra"
        license_type = payload.get(
            "license_type", "license") if payload else "license"

        self._status.configure(
            text=f"License updated for {business} ({license_type}).",
            text_color=COLORS["green"],
        )

        self.after(600, self._finish)

    def _finish(self):
        self.destroy()
        self.on_success()


# ── Category Dialog ───────────────────────────────────────────────────────────
PRESET_COLORS = [
    "#2D8C5A", "#4338CA", "#2563EB", "#C0392B",
    "#C47C22", "#7C3AED", "#0891B2", "#78716C",
    "#E11D48", "#0D9488", "#D97706", "#6D28D9",
]


class _CategoryDialog(ctk.CTkToplevel):

    def __init__(self, parent, title, on_save,
                 initial_name="", initial_color="#888888"):
        super().__init__(parent)
        self.on_save = on_save
        self._color = initial_color
        self.title(title)
        self.geometry("420x500")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.lift()
        self.focus_force()
        self._centre(parent)
        self._build(title, initial_name, initial_color)

    def _centre(self, parent):
        self.update_idletasks()
        w, h = 420, 500
        try:
            px = parent.winfo_rootx() + parent.winfo_width() // 2
            py = parent.winfo_rooty() + parent.winfo_height() // 2
        except Exception:
            px, py = 640, 400
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    def _build(self, title, init_name, init_color):
        # Header
        hdr = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=title, font=FONTS["heading"],
                     text_color=COLORS["txt"]).pack(side="left", padx=20, pady=14)
        # Native title-bar close only (no redundant custom ✕).

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        # Name
        ctk.CTkLabel(body, text="NAME", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))
        self._name_entry = ctk.CTkEntry(body, height=38,
                                        fg_color=COLORS["bg2"],
                                        border_color=COLORS["border"],
                                        placeholder_text="e.g. Brakes",
                                        text_color=COLORS["txt"],
                                        font=FONTS["body"])
        self._name_entry.pack(fill="x")
        if init_name:
            self._name_entry.insert(0, init_name)

        # Color
        ctk.CTkLabel(body, text="COLOR", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(14, 6))

        swatch_frame = ctk.CTkFrame(body, fg_color="transparent")
        swatch_frame.pack(fill="x")
        for i, hex_col in enumerate(PRESET_COLORS):
            import tkinter as _tk
            btn = _tk.Frame(swatch_frame, bg=hex_col, width=28, height=28,
                            cursor="hand2")
            btn.grid(row=i // 6, column=i % 6, padx=3, pady=3)
            btn.bind("<Button-1>", lambda e, c=hex_col: self._pick(c))

        custom_row = ctk.CTkFrame(body, fg_color="transparent")
        custom_row.pack(fill="x", pady=(10, 0))
        import tkinter as _tk
        self._swatch = _tk.Frame(custom_row, bg=init_color, width=32, height=32,
                                 relief="solid", borderwidth=1, cursor="hand2")
        self._swatch.pack(side="left")
        self._swatch.bind("<Button-1>", lambda e: self._open_picker())
        self._color_lbl = ctk.CTkLabel(custom_row, text=init_color,
                                       font=FONTS["body"], text_color=COLORS["txt2"])
        self._color_lbl.pack(side="left", padx=10)
        ctk.CTkButton(custom_row, text="Pick custom…", width=120, height=30,
                      fg_color=COLORS["bg2"], text_color=COLORS["txt"],
                      font=FONTS["small"], command=self._open_picker
                      ).pack(side="left", padx=8)

        self._err = ctk.CTkLabel(body, text="", text_color=COLORS["red"],
                                 font=FONTS["small"])
        self._err.pack(anchor="w", pady=(8, 0))

        # Footer
        footer = ctk.CTkFrame(
            self, fg_color=COLORS["card"], corner_radius=0, height=56)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkButton(footer, text="Cancel", width=100,
                      fg_color=COLORS["bg2"], text_color=COLORS["txt"],
                      hover_color=COLORS["border"],
                      command=self.destroy).pack(side="right", padx=8, pady=10)
        ctk.CTkButton(footer, text="Save", width=120,
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF",
                      command=self._save).pack(side="right", padx=(0, 4), pady=10)

    def _pick(self, color):
        self._color = color
        self._swatch.configure(bg=color)
        self._color_lbl.configure(text=color)

    def _open_picker(self):
        result = colorchooser.askcolor(
            color=self._color, title="Choose colour")
        if result and result[1]:
            self._pick(result[1])

    def _save(self):
        name = self._name_entry.get().strip()
        if not name:
            self._err.configure(text="Name cannot be empty.")
            return
        self.destroy()
        self.on_save(name, self._color)


# ── Restore Database Dialog ────────────────────────────────────────────────────
class _RestoreDialog(ctk.CTkToplevel):
    """Pick a backup (from the backups folder or anywhere) and restore it."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.parent = parent
        self.app = app
        self._selected = tk.StringVar(value="")

        self.title("Restore Database")
        self.geometry("620x560")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.lift()
        self.focus_force()
        self._centre(parent)
        self._build()

    def _centre(self, parent):
        self.update_idletasks()
        w, h = 620, 560
        try:
            px = parent.winfo_rootx() + parent.winfo_width() // 2
            py = parent.winfo_rooty() + parent.winfo_height() // 2
        except Exception:
            px, py = 640, 400
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    @staticmethod
    def _human_size(num_bytes):
        size = float(num_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:,.0f} {unit}" if unit == "B" else f"{size:,.1f} {unit}"
            size /= 1024

    @staticmethod
    def _backup_when(path):
        try:
            ts = os.path.getmtime(path)
            from datetime import datetime as _dt
            return _dt.fromtimestamp(ts).strftime("%Y-%m-%d  %H:%M")
        except Exception:
            return "—"

    def _build(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS["card"],
                           corner_radius=0, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Restore Database", font=FONTS["heading"],
                     text_color=COLORS["txt"]).pack(side="left", padx=20, pady=16)
        # Native title-bar close only (no redundant custom ✕).

        # Footer (packed before body so buttons stay visible)
        footer = ctk.CTkFrame(self, fg_color=COLORS["card"],
                              corner_radius=0, height=62)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkButton(footer, text="Cancel", width=110,
                      fg_color=COLORS["bg2"], text_color=COLORS["txt"],
                      hover_color=COLORS["border"],
                      command=self.destroy).pack(side="right", padx=10, pady=13)
        ctk.CTkButton(footer, text="⟲  Restore Selected", width=180,
                      fg_color=COLORS["amber"], hover_color="#d8620a",
                      text_color="#FFFFFF",
                      command=self._restore_selected).pack(
            side="right", padx=(0, 4), pady=13)
        ctk.CTkButton(footer, text="📂  Browse…", width=120,
                      fg_color=COLORS["bg2"], hover_color=COLORS["border"],
                      text_color=COLORS["txt2"],
                      command=self._browse_file).pack(side="left", padx=10, pady=13)

        # Body
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(16, 8))

        ctk.CTkLabel(body, text="Choose a backup to restore:", font=FONTS["body"],
                     text_color=COLORS["txt"], anchor="w").pack(fill="x")
        ctk.CTkLabel(body,
                     text="The current database is overwritten. A safety backup is "
                          "created automatically before restoring.",
                     font=FONTS["small"], text_color=COLORS["txt3"],
                     anchor="w", justify="left", wraplength=560
                     ).pack(fill="x", pady=(2, 10))

        list_wrap = ctk.CTkScrollableFrame(body, fg_color=COLORS["card"],
                                           corner_radius=12,
                                           border_width=1,
                                           border_color=COLORS["border"])
        list_wrap.pack(fill="both", expand=True)

        backups = list_backups()
        if not backups:
            ctk.CTkLabel(list_wrap, text="No backups found yet.\nUse “Backup Now” first.",
                         font=FONTS["body"], text_color=COLORS["txt3"],
                         justify="center").pack(pady=40)
            return

        for path in backups:
            row = ctk.CTkFrame(list_wrap, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            rb = ctk.CTkRadioButton(
                row, text="", variable=self._selected, value=path,
                width=22, fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"])
            rb.pack(side="left", padx=(6, 8), pady=8)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(info, text=os.path.basename(path), font=FONTS["body"],
                         text_color=COLORS["txt"], anchor="w").pack(anchor="w")
            try:
                size = self._human_size(os.path.getsize(path))
            except OSError:
                size = "—"
            ctk.CTkLabel(info, text=f"{self._backup_when(path)}   ·   {size}",
                         font=FONTS["small"], text_color=COLORS["txt3"],
                         anchor="w").pack(anchor="w")

            ctk.CTkFrame(list_wrap, fg_color=COLORS["border_soft"],
                         height=1).pack(fill="x", padx=10)

        # Pre-select the newest backup.
        self._selected.set(backups[0])

    def _browse_file(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose a database backup",
            initialdir=BACKUP_DIR,
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")],
        )
        if path:
            self._confirm_and_restore(path)

    def _restore_selected(self):
        path = self._selected.get()
        if not path:
            messagebox.showwarning(
                "No Selection", "Select a backup to restore first.", parent=self)
            return
        self._confirm_and_restore(path)

    def _confirm_and_restore(self, path):
        if not os.path.exists(path):
            messagebox.showerror(
                "Not Found", "That backup file no longer exists.", parent=self)
            return

        name = os.path.basename(path)
        if not messagebox.askyesno(
            "Confirm Restore",
            f"Restore the database from:\n\n{name}\n\n"
            "This will OVERWRITE all current data. A safety backup of the "
            "current database is created first.\n\nContinue?",
            icon="warning", parent=self,
        ):
            return

        # Safety backup of current state before overwriting.
        try:
            create_backup()
        except Exception:
            pass

        ok = restore_backup(path)
        if not ok:
            messagebox.showerror(
                "Restore Failed",
                "The database could not be restored. The current data is unchanged.",
                parent=self)
            return

        self.destroy()
        self._show_restart_screen()

    def _show_restart_screen(self):
        """
        Cover the whole window with a clear 'restart required' message.

        After a restore the live database engine is disposed, so the app must be
        reopened for the restored data to load. We replace the UI with a big,
        unmistakable instruction instead of leaving a blank window behind.
        """
        root = self.app.winfo_toplevel()

        overlay = ctk.CTkFrame(root, fg_color=COLORS["bg"], corner_radius=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()

        center = ctk.CTkFrame(overlay, fg_color="transparent")
        center.place(relx=0.5, rely=0.45, anchor="center")

        ctk.CTkLabel(center, text="✓", font=("Helvetica", 88, "bold"),
                     text_color=COLORS["green"]).pack()
        ctk.CTkLabel(center, text="Database Restored Successfully",
                     font=("Helvetica", 34, "bold"),
                     text_color=COLORS["txt"]).pack(pady=(10, 12))
        ctk.CTkLabel(
            center,
            text="Please CLOSE Inventra and OPEN it again\n"
                 "for your restored data to load.",
            font=("Helvetica", 21),
            text_color=COLORS["txt2"], justify="center").pack(pady=(0, 30))
        ctk.CTkButton(
            center, text="Close Inventra Now",
            width=280, height=54,
            fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
            text_color="#FFFFFF", font=("Helvetica", 17, "bold"),
            command=root.destroy).pack()


# ── Fee Type Dialog ─────────────────────────────────────────────────────────
class _FeeTypeDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, on_save, initial_name="", initial_amount=0.0):
        super().__init__(parent)
        self.on_save = on_save
        self.title(title)
        self.geometry("400x340")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set(); self.lift(); self.focus_force()
        try:
            self.geometry(f"+{parent.winfo_rootx()+200}+{parent.winfo_rooty()+200}")
        except Exception:
            pass
        # Pin Save to the bottom FIRST so it's always reserved/visible even if
        # the window is short (DPI scaling can shrink the dialog).
        save_bar = ctk.CTkFrame(self, fg_color="transparent")
        save_bar.pack(side="bottom", fill="x", padx=20, pady=(0, 18))
        ctk.CTkButton(save_bar, text="Save", fg_color=COLORS["navy"],
                      hover_color=COLORS["navy_hover"], text_color="#FFFFFF",
                      height=38, command=self._save).pack(fill="x")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(18, 0))
        ctk.CTkLabel(body, text="NAME", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 3))
        self._name = ctk.CTkEntry(body, height=36, fg_color=COLORS["bg2"],
                                  border_color=COLORS["border"], text_color=COLORS["txt"],
                                  placeholder_text="e.g. Battery Charge")
        self._name.pack(fill="x")
        if initial_name:
            self._name.insert(0, initial_name)
        ctk.CTkLabel(body, text="DEFAULT AMOUNT (₱)", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(12, 3))
        self._amt = ctk.CTkEntry(body, height=36, fg_color=COLORS["bg2"],
                                 border_color=COLORS["border"], text_color=COLORS["txt"])
        self._amt.pack(fill="x")
        self._amt.insert(0, f"{initial_amount:.2f}")
        self._err = ctk.CTkLabel(body, text="", font=FONTS["small"],
                                 text_color=COLORS["red"])
        self._err.pack(anchor="w", pady=(6, 0))

    def _save(self):
        name = self._name.get().strip()
        if not name:
            self._err.configure(text="Name is required."); return
        try:
            amt = max(float(self._amt.get() or 0), 0)
        except ValueError:
            self._err.configure(text="Amount must be a number."); return
        self.destroy()
        self.on_save(name, round(amt, 2))
