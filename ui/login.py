"""
login.py — Inventra Automotive Inventory
Premium Minimal Login Screen — No Card Outline

This version removes the visible outline/shadow around the login card.
It keeps the same backend authentication flow:

    db = get_session()
    AuthService(db).login(username, password)

Compatibility:
    LoginWindow = PremiumLogin
"""

import os
import sys
import tkinter as tk
import customtkinter as ctk

from database.engine import get_session
from core.services.auth_service import AuthService


def _load_logo_image(size):
    """Load the Inventra logo (assets/logo.png) as a Tk image, or None."""
    try:
        from PIL import Image, ImageTk
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        img = Image.open(os.path.join(root, "assets", "logo.png")).convert("RGBA")
        img = img.resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


# ─────────────────────────────────────────────
# Design tokens
# ─────────────────────────────────────────────
BG_NAVY = "#203B68"
BG_NAVY_DARK = "#1A335D"

CARD_BG = "#FFFFFF"

NAVY_TEXT = "#112A4D"
NAVY_BUTTON = "#15345F"
NAVY_BUTTON_HOVER = "#1C4174"

ORANGE = "#F59E0B"

INPUT_BG = "#FFFFFF"
INPUT_BORDER = "#DCE4EF"
INPUT_FOCUS = "#AFC0D6"

TEXT_PRIMARY = "#1D2D44"
TEXT_MUTED = "#64748B"
TEXT_SOFT = "#8A9BB2"
LABEL = "#3F5575"

ERROR = "#DC2626"
SUCCESS = "#16A34A"

FONT_MAIN = "Segoe UI"


# ─────────────────────────────────────────────
# Small canvas helpers
# ─────────────────────────────────────────────
def rounded_rect(canvas, x1, y1, x2, y2, radius, **kwargs):
    """Draw a rounded rectangle on a Tk canvas."""
    points = [
        x1 + radius, y1,
        x2 - radius, y1,
        x2, y1,
        x2, y1 + radius,
        x2, y2 - radius,
        x2, y2,
        x2 - radius, y2,
        x1 + radius, y2,
        x1, y2,
        x1, y2 - radius,
        x1, y1 + radius,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kwargs)


class NavyBackground(tk.Canvas):
    """Deep navy background with a very subtle premium center glow."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            bg=BG_NAVY,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self.delete("all")

        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)

        self.create_rectangle(0, 0, w, h, fill=BG_NAVY, outline="")

        # Subtle center depth. No borders, no lines, no card outline.
        cx = w / 2
        cy = h / 2
        for scale, color in [
            (1.00, "#254978"),
            (1.35, "#234571"),
            (1.75, "#213F68"),
        ]:
            rx = w * 0.22 * scale
            ry = h * 0.26 * scale
            self.create_oval(
                cx - rx,
                cy - ry,
                cx + rx,
                cy + ry,
                fill=color,
                outline="",
            )

        self.create_rectangle(0, 0, w, h, fill=BG_NAVY,
                              stipple="gray75", outline="")


class HexagonLogo(tk.Canvas):
    """Small Inventra hexagon mark."""

    def __init__(self, parent, size=24, color=NAVY_TEXT, bg=CARD_BG, **kwargs):
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=bg,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.size = size
        self.color = color
        self._draw()

    def _draw(self):
        s = self.size
        pad = 3
        mid = s / 2

        points = [
            mid, pad,
            s - pad, s * 0.28,
            s - pad, s * 0.72,
            mid, s - pad,
            pad, s * 0.72,
            pad, s * 0.28,
        ]

        self.create_polygon(
            points,
            outline=self.color,
            fill="",
            width=3,
            joinstyle="round",
        )


class InventraWordmark(tk.Canvas):
    """Inventra wordmark with clean spacing between dark text and orange accent."""

    def __init__(self, parent, **kwargs):
        super().__init__(
            parent,
            width=150,
            height=38,
            bg=CARD_BG,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.bind("<Configure>", self._draw)

    def _draw(self, event=None):
        self.delete("all")

        invent_id = self.create_text(
            0,
            19,
            text="Invent",
            anchor="w",
            font=(FONT_MAIN, 23, "bold"),
            fill=NAVY_TEXT,
        )

        self.update_idletasks()
        bbox = self.bbox(invent_id)
        ra_x = bbox[2] - 1 if bbox else 91

        self.create_text(
            ra_x,
            19,
            text="ra",
            anchor="w",
            font=(FONT_MAIN, 23, "bold"),
            fill=ORANGE,
        )


class PremiumEntry(tk.Frame):
    """Rounded white input field with focus border."""

    def __init__(self, parent, show="", initial_text="", **kwargs):
        super().__init__(parent, bg=CARD_BG, **kwargs)

        self._focused = False

        self.canvas = tk.Canvas(
            self,
            height=55,
            bg=CARD_BG,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="x", expand=True)

        self.entry = tk.Entry(
            self.canvas,
            bd=0,
            relief="flat",
            bg=INPUT_BG,
            fg=TEXT_PRIMARY,
            insertbackground=NAVY_TEXT,
            font=(FONT_MAIN, 12),
            show=show,
            highlightthickness=0,
        )
        self.entry.insert(0, initial_text)

        self._entry_window = self.canvas.create_window(
            18,
            27,
            anchor="w",
            window=self.entry,
            height=31,
        )

        self.canvas.bind("<Configure>", self._redraw)
        self.entry.bind("<FocusIn>", self._focus_in)
        self.entry.bind("<FocusOut>", self._focus_out)

    def _redraw(self, event=None):
        self.canvas.delete("shape")

        w = max(self.canvas.winfo_width(), 10)
        border = INPUT_FOCUS if self._focused else INPUT_BORDER
        width = 1.45 if self._focused else 1.05

        rounded_rect(
            self.canvas,
            1,
            1,
            w - 1,
            54,
            12,
            fill=INPUT_BG,
            outline=border,
            width=width,
            tags="shape",
        )

        self.canvas.tag_lower("shape")
        self.canvas.itemconfigure(self._entry_window, width=max(w - 36, 10))

    def _focus_in(self, event=None):
        self._focused = True
        self._redraw()

    def _focus_out(self, event=None):
        self._focused = False
        self._redraw()

    def get(self):
        return self.entry.get()

    def delete(self, first, last=None):
        self.entry.delete(first, last)

    def focus(self):
        self.entry.focus()

    def bind_entry(self, sequence, callback):
        self.entry.bind(sequence, callback)


class PremiumButton(tk.Canvas):
    """Rounded dark navy sign-in button."""

    def __init__(self, parent, command=None, **kwargs):
        super().__init__(
            parent,
            height=56,
            bg=CARD_BG,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            **kwargs,
        )

        self.command = command
        self.text = "Sign In"
        self.fill = NAVY_BUTTON
        self.loading = False

        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._hover_on)
        self.bind("<Leave>", self._hover_off)
        self.bind("<Button-1>", self._click)

    def _draw(self, event=None):
        self.delete("all")

        w = max(self.winfo_width(), 10)

        rounded_rect(
            self,
            0,
            0,
            w,
            56,
            12,
            fill=self.fill,
            outline=self.fill,
        )

        self.create_text(
            w / 2,
            28,
            text=self.text,
            fill="#FFFFFF",
            font=(FONT_MAIN, 13, "bold"),
        )

    def _hover_on(self, event=None):
        if not self.loading:
            self.fill = NAVY_BUTTON_HOVER
            self._draw()

    def _hover_off(self, event=None):
        if not self.loading:
            self.fill = NAVY_BUTTON
            self._draw()

    def _click(self, event=None):
        if not self.loading and self.command:
            self.command()

    def set_loading(self, state):
        self.loading = state

        if state:
            self.text = "Signing In..."
            self.fill = NAVY_BUTTON_HOVER
            self.configure(cursor="watch")
        else:
            self.text = "Sign In"
            self.fill = NAVY_BUTTON
            self.configure(cursor="hand2")

        self._draw()

    def set_success(self):
        self.loading = True
        self.text = "Signed In"
        self.fill = SUCCESS
        self.configure(cursor="watch")
        self._draw()


class FooterBadge(tk.Frame):
    """Premium footer under the button, without card outlines or extra borders."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=CARD_BG, **kwargs)

        canvas = tk.Canvas(
            self,
            height=42,
            bg=CARD_BG,
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(fill="x")

        def draw(event=None):
            canvas.delete("all")

            w = max(canvas.winfo_width(), 10)

            # Soft short divider only above the footer.
            divider_w = min(158, w - 100)
            x1 = (w - divider_w) / 2
            x2 = x1 + divider_w
            canvas.create_line(x1, 4, x2, 4, fill="#E7ECF4", width=1)

            # Footer pill. It has a very subtle border, but no card outline.
            pill_w = min(318, w - 8)
            px1 = (w - pill_w) / 2
            py1 = 14
            px2 = px1 + pill_w
            py2 = 40

            rounded_rect(
                canvas,
                px1,
                py1,
                px2,
                py2,
                13,
                fill="#F8FAFC",
                outline="#E5EBF3",
                width=1,
            )

            canvas.create_oval(
                px1 + 13,
                24,
                px1 + 20,
                31,
                fill=ORANGE,
                outline="",
            )

            canvas.create_text(
                px1 + 30,
                27,
                text="© 2026 Inventra Automotive Systems",
                anchor="w",
                font=(FONT_MAIN, 8),
                fill=TEXT_MUTED,
            )

            canvas.create_line(
                px2 - 82,
                20,
                px2 - 82,
                34,
                fill="#DCE4EF",
                width=1,
            )

            canvas.create_text(
                px2 - 14,
                27,
                text="@toshfry",
                anchor="e",
                font=(FONT_MAIN, 8, "bold"),
                fill=NAVY_TEXT,
            )

        canvas.bind("<Configure>", draw)


class PremiumLogin(ctk.CTkToplevel):
    def __init__(self, parent, on_success):
        super().__init__(parent)

        self.parent = parent
        self.on_success = on_success

        ctk.set_appearance_mode("light")

        self.title("Inventra — Sign In")
        self.geometry("1040x660")
        self.minsize(920, 600)
        self.configure(fg_color=BG_NAVY)
        self.resizable(True, True)

        self.grab_set()
        self.focus_force()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._center()
        self._build_ui()

    def _center(self):
        self.update_idletasks()

        width = 1040
        height = 660

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()

        x = (sw - width) // 2
        y = (sh - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")

    def _build_ui(self):
        self.bg_canvas = NavyBackground(self)
        self.bg_canvas.pack(fill="both", expand=True)

        # IMPORTANT:
        # This is a CTkFrame with border_width=0 and no manual canvas shadow.
        # That removes the visible outline around the login card.
        self.card = ctk.CTkFrame(
            self.bg_canvas,
            width=428,
            height=482,
            corner_radius=22,
            fg_color=CARD_BG,
            border_width=0,
            border_color=CARD_BG,
        )

        self.card_window = self.bg_canvas.create_window(
            520,
            330,
            window=self.card,
            anchor="center",
        )
        self.card.pack_propagate(False)

        self.content = tk.Frame(self.card, bg=CARD_BG)
        self.content.place(relx=0.5, rely=0.5, anchor="center", width=338)

        self.bg_canvas.bind("<Configure>", self._layout)

        # Brand — "Inventra" wordmark stays centered; the logo sits on the left
        # side (placed, so it never shifts the wordmark off-center). Falls back
        # to the drawn hexagon mark if the image can't be loaded.
        self._logo_img = _load_logo_image(58)

        brand = tk.Frame(self.content, bg=CARD_BG)
        brand.pack(anchor="center", pady=(0, 4))

        if self._logo_img:
            tk.Label(brand, image=self._logo_img, bg=CARD_BG).pack(
                side="left", padx=(0, 10))
        else:
            HexagonLogo(brand, size=25).pack(side="left", padx=(0, 9))
        InventraWordmark(brand).pack(side="left")

        tk.Label(
            self.content,
            text="Automotive Inventory & Sales System",
            font=(FONT_MAIN, 10),
            fg=TEXT_MUTED,
            bg=CARD_BG,
        ).pack(anchor="center", pady=(0, 29))

        # Username
        tk.Label(
            self.content,
            text="USERNAME",
            font=(FONT_MAIN, 9, "bold"),
            fg=LABEL,
            bg=CARD_BG,
        ).pack(anchor="w", pady=(0, 6))

        self.username_e = PremiumEntry(self.content, initial_text="admin")
        self.username_e.pack(fill="x", pady=(0, 18))

        # Password
        tk.Label(
            self.content,
            text="PASSWORD",
            font=(FONT_MAIN, 9, "bold"),
            fg=LABEL,
            bg=CARD_BG,
        ).pack(anchor="w", pady=(0, 6))

        self.password_e = PremiumEntry(self.content, show="•", initial_text="")
        self.password_e.pack(fill="x", pady=(0, 11))

        self.error_lbl = tk.Label(
            self.content,
            text="",
            font=(FONT_MAIN, 8),
            fg=ERROR,
            bg=CARD_BG,
            anchor="w",
        )
        self.error_lbl.pack(fill="x", pady=(0, 7))

        self.sign_btn = PremiumButton(self.content, command=self._login)
        self.sign_btn.pack(fill="x", pady=(0, 14))

        FooterBadge(self.content).pack(fill="x")

        self.username_e.bind_entry(
            "<Return>", lambda event: self.password_e.focus())
        self.password_e.bind_entry("<Return>", lambda event: self._login())

        self.after(180, self.username_e.focus)

    def _layout(self, event=None):
        w = max(self.bg_canvas.winfo_width(), 1)
        h = max(self.bg_canvas.winfo_height(), 1)
        self.bg_canvas.coords(self.card_window, w / 2, h / 2)

    def _login(self):
        username = self.username_e.get().strip()
        password = self.password_e.get()

        self.error_lbl.configure(text="")

        if not username or not password:
            self.error_lbl.configure(
                text="Please enter your username and password.")
            return

        self.sign_btn.set_loading(True)
        self.update_idletasks()

        db = None

        try:
            db = get_session()
            AuthService(db).login(username, password)

            self.sign_btn.set_success()
            self.after(450, self._success)

        except ValueError as exc:
            self.sign_btn.set_loading(False)
            self.error_lbl.configure(
                text=str(exc) or "Invalid username or password.")
            self.password_e.delete(0, "end")
            self.password_e.focus()

        except Exception as exc:
            self.sign_btn.set_loading(False)
            self.error_lbl.configure(text=f"Login failed: {exc}")
            self.password_e.focus()

        finally:
            if db is not None:
                db.close()

    def _success(self):
        self.destroy()
        self.on_success()

    def _on_close(self):
        sys.exit(0)


# ─────────────────────────────────────────────
# Compatibility layer
# ─────────────────────────────────────────────
LoginWindow = PremiumLogin
