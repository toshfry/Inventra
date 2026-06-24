"""
activation.py — Inventra first-time activation screen

A clean, premium single-card dialog: brand logo, Computer ID with one-click copy,
and an activation key field. Paste the key and press Enter (or click Activate).
The whole card is sized to fit, so the Activate button is always visible.
"""

import os
import sys
import tkinter as tk

import customtkinter as ctk

from utils.app_icon import set_window_icon, resource_path

from core.licensing.license_manager import (
    activate_from_key,
    get_computer_id,
    license_status,
)

BG = "#F7F9FC"
CARD = "#FFFFFF"
NAVY = "#1D3461"
NAVY_HOVER = "#264773"
ORANGE = "#F59E0B"
ORANGE_HOVER = "#D88A06"
TEXT = "#172033"
MUTED = "#64748B"
BORDER = "#DDE6F2"
SOFT = "#F8FAFC"
ERROR = "#DC2626"
SUCCESS = "#16A34A"
FONT = "Segoe UI"

PLACEHOLDER = "Paste your activation key here…"


class ActivationWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)
        self.parent = parent
        self.on_success = on_success
        self.computer_id = get_computer_id()
        self._logo_img = None
        self._busy = False

        self.title("Inventra Activation")
        set_window_icon(self)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._exit_app)

        self._center(500, 690)
        self._build()

        self.after(100, self.lift)
        self.after(150, self.focus_force)

        try:
            self.grab_set()
        except Exception:
            pass

    # ── Window helpers ────────────────────────────────────────────────
    def _center(self, w, h):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x, y = (sw - w) // 2, (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.minsize(470, 660)

    def _load_logo(self, size=78):
        """Load the brand logo as a CTkImage; return None if unavailable."""
        try:
            from PIL import Image
            for rel in ("assets/logo.png", "logo.png", "inventra_icon.png",
                        "web/logo.png"):
                path = resource_path(rel)
                if os.path.exists(path):
                    img = Image.open(path).convert("RGBA")
                    return ctk.CTkImage(light_image=img, dark_image=img,
                                        size=(size, size))
        except Exception:
            pass
        return None

    # ── Layout ────────────────────────────────────────────────────────
    def _build(self):
        self._logo_img = self._load_logo()

        # Centre a fixed-width card using a 3-column grid: the side columns
        # absorb any extra space, the middle column is pinned to 452px. This
        # keeps the card a tidy, premium fixed-width card even when the window is
        # maximised / full-screen, instead of the fields and Activate button
        # stretching across the whole screen. Height stays automatic (sticky
        # "new", no "s") so long status messages never clip the button.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=452)
        self.grid_columnconfigure(2, weight=1)

        card = ctk.CTkFrame(self, fg_color=CARD, border_color=BORDER,
                            border_width=1, corner_radius=22)
        card.grid(row=0, column=1, sticky="ew", pady=22)

        inner = ctk.CTkFrame(card, fg_color=CARD)
        inner.pack(fill="x", padx=30, pady=(24, 22))

        # ── Brand header (centred) ──
        if self._logo_img is not None:
            ctk.CTkLabel(inner, image=self._logo_img, text="").pack(pady=(2, 10))

        wm = ctk.CTkFrame(inner, fg_color=CARD)
        wm.pack()
        ctk.CTkLabel(wm, text="Invent", font=(FONT, 28, "bold"),
                     text_color=NAVY).pack(side="left")
        ctk.CTkLabel(wm, text="ra", font=(FONT, 28, "bold"),
                     text_color=ORANGE).pack(side="left")

        ctk.CTkLabel(inner, text="Software Activation", font=(FONT, 12),
                     text_color=MUTED).pack(pady=(3, 20))

        # ── Heading + instruction ──
        ctk.CTkLabel(inner, text="Activation required",
                     font=(FONT, 18, "bold"), text_color=TEXT,
                     anchor="w").pack(fill="x")
        ctk.CTkLabel(
            inner,
            text="Copy your Computer ID, send it to the developer, then paste the key below.",
            font=(FONT, 12), text_color=MUTED, anchor="w", justify="left",
            wraplength=380,
        ).pack(fill="x", pady=(5, 16))

        # ── Computer ID ──
        ctk.CTkLabel(inner, text="COMPUTER ID", font=(FONT, 11, "bold"),
                     text_color=NAVY, anchor="w").pack(fill="x")

        id_row = ctk.CTkFrame(inner, fg_color=CARD)
        id_row.pack(fill="x", pady=(6, 16))

        self.id_entry = ctk.CTkEntry(
            id_row, height=42, corner_radius=11, border_color=BORDER,
            fg_color=SOFT, text_color=TEXT, font=(FONT, 14, "bold"))
        self.id_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.id_entry.insert(0, self.computer_id)
        self.id_entry.configure(state="readonly")

        self.copy_btn = ctk.CTkButton(
            id_row, text="Copy", width=88, height=42, corner_radius=11,
            fg_color=NAVY, hover_color=NAVY_HOVER, font=(FONT, 12, "bold"),
            command=self._copy_id)
        self.copy_btn.pack(side="right")

        # ── Activation key ──
        ctk.CTkLabel(inner, text="ACTIVATION KEY", font=(FONT, 11, "bold"),
                     text_color=NAVY, anchor="w").pack(fill="x")

        self.key_box = ctk.CTkTextbox(
            inner, height=64, corner_radius=11, border_color=BORDER,
            border_width=1, fg_color=CARD, text_color=TEXT,
            font=("Consolas", 11), wrap="word")
        self.key_box.pack(fill="x", pady=(6, 8))
        self.key_box.insert("1.0", PLACEHOLDER)
        self.key_box.bind("<FocusIn>", self._clear_placeholder)
        self.key_box.bind("<Return>", self._on_return)   # Enter = activate

        ctk.CTkLabel(
            inner, text="Tip: paste your key and press  Enter ↵  to activate.",
            font=(FONT, 11), text_color=MUTED, anchor="w").pack(fill="x")

        # ── Status ──
        self.status_lbl = ctk.CTkLabel(
            inner, text="", font=(FONT, 12), text_color=MUTED, anchor="w",
            justify="left", wraplength=380)
        self.status_lbl.pack(fill="x", pady=(12, 14))

        # ── Buttons ──
        btn_row = ctk.CTkFrame(inner, fg_color=CARD)
        btn_row.pack(fill="x", pady=(2, 0))

        ctk.CTkButton(
            btn_row, text="Exit", width=100, height=46, corner_radius=12,
            fg_color="#E5EAF2", hover_color="#D8E1ED", text_color=NAVY,
            font=(FONT, 13, "bold"), command=self._exit_app).pack(side="left")

        self.activate_btn = ctk.CTkButton(
            btn_row, text="✓  Activate Inventra", height=46, corner_radius=12,
            fg_color=ORANGE, hover_color=ORANGE_HOVER, text_color="#FFFFFF",
            font=(FONT, 13, "bold"), command=self._activate)
        self.activate_btn.pack(side="right", fill="x", expand=True, padx=(10, 0))

        # Show current status if a license file exists but is invalid.
        status = license_status()
        if not status.get("activated"):
            self.status_lbl.configure(text=status.get("message", ""),
                                      text_color=MUTED)

    # ── Behaviour ─────────────────────────────────────────────────────
    def _clear_placeholder(self, event=None):
        if self.key_box.get("1.0", "end").strip() == PLACEHOLDER:
            self.key_box.delete("1.0", "end")

    def _on_return(self, event=None):
        # Enter activates instead of inserting a newline.
        self._activate()
        return "break"

    def _copy_id(self):
        self.clipboard_clear()
        self.clipboard_append(self.computer_id)
        self.copy_btn.configure(text="✓ Copied")
        self.status_lbl.configure(text="Computer ID copied to clipboard.",
                                  text_color=SUCCESS)
        self.after(1600, lambda: self.copy_btn.configure(text="Copy"))

    def _activate(self):
        if self._busy:
            return
        key = self.key_box.get("1.0", "end").strip()

        if not key or key == PLACEHOLDER:
            self.status_lbl.configure(
                text="Please paste your activation key first.", text_color=ERROR)
            return

        self._busy = True
        self.activate_btn.configure(text="Activating…", state="disabled")
        self.status_lbl.configure(text="Checking your key…", text_color=MUTED)
        self.update_idletasks()

        valid, message, payload = activate_from_key(key)

        if not valid:
            self._busy = False
            self.activate_btn.configure(text="✓  Activate Inventra",
                                        state="normal")
            self.status_lbl.configure(text=message, text_color=ERROR)
            return

        business = payload.get("business_name") if payload else "Inventra"
        self.activate_btn.configure(text="✓  Activated")
        self.status_lbl.configure(
            text=f"Activated for {business}. Opening Inventra…",
            text_color=SUCCESS)
        self.after(800, self._success)

    def _success(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        self.on_success()

    def _exit_app(self):
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        sys.exit(0)
