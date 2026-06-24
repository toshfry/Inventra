import tkinter as tk
import customtkinter as ctk
from config.themes import COLORS, FONTS
from database.engine import get_session
from core.services.adjustment_service import AdjustmentService, REASONS
from ui.components.toast import Toast


class AdjustStockDialog(ctk.CTkToplevel):
    """Admin dialog to correct a part's on-hand stock."""

    def __init__(self, parent, app, part_id, on_done=None):
        super().__init__(parent)
        self.app = app
        self.part_id = part_id
        self.on_done = on_done

        # Load part snapshot.
        db = get_session()
        try:
            from database.models.part import Part
            part = db.get(Part, part_id)
            self._name = part.name if part else "—"
            self._sku = part.sku if part else "—"
            self._current = part.current_stock if part else 0
            self._unit_cost = (part.unit_cost or 0.0) if part else 0.0
        finally:
            db.close()

        self.title("Adjust Stock")
        self.geometry("440x470")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.lift()
        self.focus_force()
        self._centre(parent)

        self._mode = tk.StringVar(value="set")
        self._value = tk.StringVar(value=str(self._current))
        self._reason = tk.StringVar(value=list(REASONS.values())[0])
        self._note = tk.StringVar(value="")
        self._build()

    def _centre(self, parent):
        self.update_idletasks()
        w, h = 440, 470
        try:
            px = parent.winfo_rootx() + parent.winfo_width() // 2
            py = parent.winfo_rooty() + parent.winfo_height() // 2
        except Exception:
            px, py = 640, 400
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="Adjust Stock", font=FONTS["heading"],
                     text_color=COLORS["txt"]).pack(side="left", padx=20, pady=16)
        # Native title-bar close only (no redundant custom ✕).

        # Footer (packed before body so it anchors to bottom correctly)
        footer = ctk.CTkFrame(self, fg_color=COLORS["card"], corner_radius=0, height=58)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkButton(footer, text="Cancel", width=100, fg_color=COLORS["bg2"],
                      text_color=COLORS["txt"], hover_color=COLORS["border"],
                      command=self.destroy).pack(side="right", padx=10, pady=11)
        ctk.CTkButton(footer, text="Apply Adjustment", width=160,
                      fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
                      text_color="#FFFFFF", command=self._apply).pack(
            side="right", padx=(0, 4), pady=11)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=16)

        ctk.CTkLabel(body, text=f"{self._name}   ·   {self._sku}",
                     font=FONTS["body"], text_color=COLORS["txt"],
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(body, text=f"Current on-hand: {self._current}",
                     font=FONTS["small"], text_color=COLORS["txt3"],
                     anchor="w").pack(fill="x", pady=(2, 12))

        # Mode toggle
        ctk.CTkLabel(body, text="MODE", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w")
        mode_row = ctk.CTkFrame(body, fg_color="transparent")
        mode_row.pack(fill="x", pady=(2, 10))
        ctk.CTkRadioButton(mode_row, text="Set actual count", variable=self._mode,
                           value="set", command=self._update_preview,
                           fg_color=COLORS["navy"], text_color=COLORS["txt"],
                           font=FONTS["body"]).pack(side="left", padx=(0, 16))
        ctk.CTkRadioButton(mode_row, text="Add / remove amount", variable=self._mode,
                           value="delta", command=self._update_preview,
                           fg_color=COLORS["navy"], text_color=COLORS["txt"],
                           font=FONTS["body"]).pack(side="left")

        # Value
        ctk.CTkLabel(body, text="VALUE", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w")
        val_entry = ctk.CTkEntry(body, textvariable=self._value, height=36,
                                 fg_color=COLORS["bg2"], border_color=COLORS["border"],
                                 text_color=COLORS["txt"], font=FONTS["body"])
        val_entry.pack(fill="x", pady=(2, 4))
        self._value.trace_add("write", lambda *_: self._update_preview())

        # Reason
        ctk.CTkLabel(body, text="REASON", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w", pady=(8, 0))
        ctk.CTkOptionMenu(body, variable=self._reason, values=list(REASONS.values()),
                          fg_color=COLORS["bg2"], button_color=COLORS["border"],
                          text_color=COLORS["txt"], font=FONTS["body"],
                          dropdown_fg_color=COLORS["card"], height=36).pack(
            fill="x", pady=(2, 8))

        # Note
        ctk.CTkLabel(body, text="NOTE (optional)", font=FONTS["label"],
                     text_color=COLORS["txt3"]).pack(anchor="w")
        ctk.CTkEntry(body, textvariable=self._note, height=36,
                     fg_color=COLORS["bg2"], border_color=COLORS["border"],
                     text_color=COLORS["txt"], font=FONTS["body"],
                     placeholder_text="e.g. annual count").pack(fill="x", pady=(2, 10))

        # Live preview
        self._preview = ctk.CTkLabel(body, text="", font=FONTS["body"],
                                     text_color=COLORS["txt2"], anchor="w",
                                     justify="left")
        self._preview.pack(fill="x")

        self._update_preview()

    def _reason_code(self):
        label = self._reason.get()
        for code, lbl in REASONS.items():
            if lbl == label:
                return code
        return "OTHER"

    def _compute(self):
        """Return (delta, new_count) or (None, None) if the value is invalid."""
        raw = self._value.get().strip()
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None, None
        if self._mode.get() == "set":
            return value - self._current, value
        return value, self._current + value

    def _update_preview(self):
        delta, new_count = self._compute()
        if delta is None:
            self._preview.configure(text="Enter a whole number.",
                                    text_color=COLORS["txt3"])
            return
        if delta == 0:
            self._preview.configure(
                text="No change — current stock is already this value.",
                text_color=COLORS["txt3"])
            return
        money = round(delta * self._unit_cost, 2)
        sign = "+" if delta > 0 else ""
        color = COLORS["green"] if delta > 0 else (
            COLORS["red"] if delta < 0 else COLORS["txt3"])
        self._preview.configure(
            text=f"{self._current} → {new_count}   "
                 f"({sign}{delta} units,  {sign}₱{money:,.2f})",
            text_color=color)

    def _apply(self):
        from tkinter import messagebox
        from core.validators.adjustment_schema import AdjustmentCreate
        delta, new_count = self._compute()
        if delta is None:
            messagebox.showerror("Invalid", "Enter a whole number.", parent=self)
            return

        value = new_count if self._mode.get() == "set" else delta

        user = "system"
        try:
            from core.services.auth_service import get_current_user
            u = get_current_user()
            if u:
                user = u.username
        except Exception:
            pass

        data = AdjustmentCreate(
            part_id=self.part_id,
            mode=self._mode.get(),
            value=value,
            reason_code=self._reason_code(),
            note=self._note.get().strip() or None,
        )

        db = get_session()
        try:
            AdjustmentService(db).adjust(data, user=user)
        except Exception as e:
            messagebox.showerror("Cannot Adjust", str(e), parent=self)
            return
        finally:
            db.close()

        Toast(self.app, "Stock adjusted.", kind="success")
        if self.on_done:
            self.on_done()
        self.destroy()
