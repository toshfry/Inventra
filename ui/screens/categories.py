"""
Category Management Screen
Admins can create, rename, recolour, and delete categories.
"""
import tkinter as tk
import customtkinter as ctk
from config.themes import COLORS, FONTS
from database.engine import get_session
from database.models.category import Category
from core.services.auth_service import is_admin


class CategoryScreen(ctk.CTkFrame):
    def __init__(self, parent, toast=None, **kwargs):
        super().__init__(parent, fg_color=COLORS["bg"], **kwargs)
        self._toast = toast
        self._categories = []
        self._build()
        self.refresh()

    # ── Layout ───────────────────────────────────────────────────────
    def _build(self):
        # Header row
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))
        ctk.CTkLabel(header, text="Categories",
                     font=ctk.CTkFont(*FONTS["title"]),
                     text_color=COLORS["txt"]).pack(side="left")
        if is_admin():
            ctk.CTkButton(header, text="+ Add Category", width=140, height=36,
                          fg_color=COLORS["green"], hover_color="#1f6b43",
                          font=ctk.CTkFont(*FONTS["body"]),
                          command=self._open_add).pack(side="right")

        ctk.CTkLabel(self, text="Manage part categories used across the inventory.",
                     font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["txt2"]).pack(anchor="w", padx=24, pady=(4, 14))

        # List area
        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=COLORS["card"],
            corner_radius=10, border_width=1,
            border_color=COLORS["border"])
        self._list_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    # ── Data ─────────────────────────────────────────────────────────
    def refresh(self):
        # Clear current rows
        for w in self._list_frame.winfo_children():
            w.destroy()

        db = get_session()
        try:
            self._categories = db.query(Category).order_by(Category.name).all()
            cats = [(c.id, c.name, c.color_hex, len(c.parts)) for c in self._categories]
        finally:
            db.close()

        if not cats:
            ctk.CTkLabel(self._list_frame, text="No categories yet. Click '+ Add Category' to create one.",
                         text_color=COLORS["txt2"],
                         font=ctk.CTkFont(*FONTS["body"])).pack(pady=32)
            return

        # Column headers
        hdr = ctk.CTkFrame(self._list_frame, fg_color=COLORS["bg2"], height=32)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        for txt, w in [("Color", 60), ("Name", 260), ("Parts", 60), ("Actions", 180)]:
            ctk.CTkLabel(hdr, text=txt.upper(),
                         font=ctk.CTkFont(*FONTS["label"]),
                         text_color=COLORS["txt2"],
                         width=w).pack(side="left", padx=8)

        for cat_id, name, color, part_count in cats:
            self._add_row(cat_id, name, color, part_count)

    def _add_row(self, cat_id, name, color, part_count):
        row = ctk.CTkFrame(self._list_frame, fg_color="transparent", height=48)
        row.pack(fill="x")
        row.pack_propagate(False)

        sep = ctk.CTkFrame(self._list_frame, fg_color=COLORS["border"], height=1)
        sep.pack(fill="x")

        # Color swatch
        swatch = tk.Frame(row, bg=color, width=24, height=24)
        swatch.place(x=16, rely=0.5, anchor="w")

        # Name
        ctk.CTkLabel(row, text=name,
                     font=ctk.CTkFont(*FONTS["body"]),
                     text_color=COLORS["txt"],
                     width=260, anchor="w").place(x=60, rely=0.5, anchor="w")

        # Part count
        ctk.CTkLabel(row, text=str(part_count),
                     font=ctk.CTkFont(*FONTS["body"]),
                     text_color=COLORS["txt2"],
                     width=60).place(x=330, rely=0.5, anchor="w")

        if is_admin():
            # Edit button
            ctk.CTkButton(row, text="Edit", width=70, height=30,
                          fg_color=COLORS["bg2"], text_color=COLORS["txt"],
                          hover_color=COLORS["border"],
                          font=ctk.CTkFont(*FONTS["small"]),
                          command=lambda cid=cat_id, cn=name, cc=color:
                              self._open_edit(cid, cn, cc)).place(x=400, rely=0.5, anchor="w")

            # Delete button
            ctk.CTkButton(row, text="Delete", width=70, height=30,
                          fg_color=COLORS["red_bg"], text_color=COLORS["red"],
                          hover_color="#f5c6c6",
                          font=ctk.CTkFont(*FONTS["small"]),
                          command=lambda cid=cat_id, cn=name, pc=part_count:
                              self._delete(cid, cn, pc)).place(x=480, rely=0.5, anchor="w")

    # ── Dialogs ───────────────────────────────────────────────────────
    def _open_add(self):
        _CategoryDialog(self, title="Add Category",
                        on_save=self._do_create)

    def _open_edit(self, cat_id, name, color):
        _CategoryDialog(self, title="Edit Category",
                        initial_name=name,
                        initial_color=color,
                        on_save=lambda n, c: self._do_update(cat_id, n, c))

    def _do_create(self, name, color):
        db = get_session()
        try:
            if db.query(Category).filter(Category.name == name).first():
                self._notify(f"Category '{name}' already exists.", "error")
                return
            db.add(Category(name=name, color_hex=color))
            db.commit()
            self._notify(f"Category '{name}' created.", "success")
            self.refresh()
        except Exception as e:
            db.rollback()
            self._notify(str(e), "error")
        finally:
            db.close()

    def _do_update(self, cat_id, name, color):
        db = get_session()
        try:
            cat = db.get(Category, cat_id)
            if not cat:
                self._notify("Category not found.", "error")
                return
            # Check name uniqueness
            clash = db.query(Category).filter(
                Category.name == name, Category.id != cat_id).first()
            if clash:
                self._notify(f"Name '{name}' already used.", "error")
                return
            cat.name      = name
            cat.color_hex = color
            db.commit()
            self._notify(f"Category updated.", "success")
            self.refresh()
        except Exception as e:
            db.rollback()
            self._notify(str(e), "error")
        finally:
            db.close()

    def _delete(self, cat_id, name, part_count):
        if part_count > 0:
            self._notify(
                f"Cannot delete '{name}' — it has {part_count} part(s) assigned. "
                "Re-assign or deactivate those parts first.", "error")
            return
        win = ctk.CTkToplevel(self)
        win.title("Confirm Delete")
        win.geometry("360x160")
        win.grab_set()
        win.resizable(False, False)
        win.configure(fg_color=COLORS["bg"])
        _centre(win, self)
        ctk.CTkLabel(win, text=f'Delete category "{name}"?',
                     font=ctk.CTkFont(*FONTS["heading"]),
                     text_color=COLORS["txt"]).pack(pady=(28, 8))
        ctk.CTkLabel(win, text="This cannot be undone.",
                     font=ctk.CTkFont(*FONTS["small"]),
                     text_color=COLORS["txt2"]).pack()
        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=20)
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color=COLORS["bg2"], text_color=COLORS["txt"],
                      command=win.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Delete", width=100,
                      fg_color=COLORS["red"], hover_color="#a93226",
                      command=lambda: self._confirm_delete(cat_id, name, win)).pack(side="left", padx=8)

    def _confirm_delete(self, cat_id, name, win):
        win.destroy()
        db = get_session()
        try:
            cat = db.get(Category, cat_id)
            if cat:
                db.delete(cat)
                db.commit()
            self._notify(f"Category '{name}' deleted.", "success")
            self.refresh()
        except Exception as e:
            db.rollback()
            self._notify(str(e), "error")
        finally:
            db.close()

    def _notify(self, msg, kind="info"):
        if self._toast:
            self._toast.show(msg, kind)


# ── Dialog ────────────────────────────────────────────────────────────────────

class _CategoryDialog(ctk.CTkToplevel):
    """Shared Add / Edit dialog for a category."""

    PRESET_COLORS = [
        "#2D8C5A", "#4338CA", "#2563EB", "#C0392B",
        "#C47C22", "#7C3AED", "#0891B2", "#78716C",
        "#E11D48", "#0D9488", "#D97706", "#6D28D9",
    ]

    def __init__(self, parent, title, on_save,
                 initial_name="", initial_color="#888888"):
        super().__init__(parent)
        self.on_save = on_save
        self._color  = initial_color
        self.title(title)
        self.geometry("420x380")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        _centre(self, parent)

        self._build(title, initial_name, initial_color)

    def _build(self, title, init_name, init_color):
        ctk.CTkLabel(self, text=title,
                     font=ctk.CTkFont(*FONTS["heading"]),
                     text_color=COLORS["txt"]).pack(anchor="w", padx=24, pady=(20, 2))
        ctk.CTkFrame(self, height=1, fg_color=COLORS["border"]).pack(fill="x", padx=16, pady=(8, 0))

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=16)

        # Name field
        ctk.CTkLabel(body, text="NAME",
                     font=ctk.CTkFont(*FONTS["label"]),
                     text_color=COLORS["txt2"]).pack(anchor="w", pady=(8, 3))
        self._name_entry = ctk.CTkEntry(body, height=38, fg_color=COLORS["bg2"],
                                        border_color=COLORS["border"],
                                        placeholder_text="e.g. Brakes")
        self._name_entry.pack(fill="x")
        if init_name:
            self._name_entry.insert(0, init_name)

        # Color label
        ctk.CTkLabel(body, text="COLOR",
                     font=ctk.CTkFont(*FONTS["label"]),
                     text_color=COLORS["txt2"]).pack(anchor="w", pady=(16, 6))

        # Preset swatches
        swatch_frame = ctk.CTkFrame(body, fg_color="transparent")
        swatch_frame.pack(fill="x")
        for i, hex_col in enumerate(self.PRESET_COLORS):
            btn = tk.Frame(swatch_frame, bg=hex_col, width=28, height=28,
                           cursor="hand2", relief="flat")
            btn.grid(row=i // 6, column=i % 6, padx=3, pady=3)
            btn.bind("<Button-1>", lambda e, c=hex_col: self._pick(c))

        # Custom color row
        custom_row = ctk.CTkFrame(body, fg_color="transparent")
        custom_row.pack(fill="x", pady=(10, 0))

        self._swatch = tk.Frame(custom_row, bg=init_color, width=32, height=32,
                                relief="solid", borderwidth=1, cursor="hand2")
        self._swatch.pack(side="left")
        self._swatch.bind("<Button-1>", lambda e: self._open_color_picker())

        self._color_lbl = ctk.CTkLabel(custom_row, text=init_color,
                                       font=ctk.CTkFont(*FONTS["body"]),
                                       text_color=COLORS["txt2"])
        self._color_lbl.pack(side="left", padx=10)
        ctk.CTkButton(custom_row, text="Pick custom…", width=120, height=30,
                      fg_color=COLORS["bg2"], text_color=COLORS["txt"],
                      font=ctk.CTkFont(*FONTS["small"]),
                      command=self._open_color_picker).pack(side="left", padx=8)

        # Error label
        self._err = ctk.CTkLabel(body, text="", text_color=COLORS["red"],
                                 font=ctk.CTkFont(*FONTS["small"]))
        self._err.pack(anchor="w", pady=(6, 0))

        # Buttons
        btn_row = ctk.CTkFrame(body, fg_color="transparent")
        btn_row.pack(fill="x", pady=(8, 0))
        ctk.CTkButton(btn_row, text="Cancel", width=100,
                      fg_color=COLORS["bg2"], text_color=COLORS["txt"],
                      command=self.destroy).pack(side="left")
        ctk.CTkButton(btn_row, text="Save", width=100,
                      fg_color=COLORS["green"], hover_color="#1f6b43",
                      command=self._save).pack(side="right")

    def _pick(self, color):
        self._color = color
        self._swatch.configure(bg=color)
        self._color_lbl.configure(text=color)

    def _open_color_picker(self):
        from tkinter import colorchooser
        result = colorchooser.askcolor(color=self._color, title="Choose color")
        if result and result[1]:
            self._pick(result[1])

    def _save(self):
        name = self._name_entry.get().strip()
        if not name:
            self._err.configure(text="Name cannot be empty.")
            return
        self.destroy()
        self.on_save(name, self._color)


def _centre(win, parent):
    win.update_idletasks()
    w = win.winfo_reqwidth()
    h = win.winfo_reqheight()
    try:
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        pw, ph = parent.winfo_width(), parent.winfo_height()
    except Exception:
        px, py, pw, ph = 0, 0, 1280, 820
    win.geometry(f"{w}x{h}+{px+(pw-w)//2}+{py+(ph-h)//2}")
