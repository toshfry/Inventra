import customtkinter as ctk
import os
from config.themes import COLORS, FONTS
from core.services.auth_service import get_current_user, is_admin

_DIV = "#123D7A"
_LBL = "#6E8DBF"
_MUTED = "#C7D6F1"
_VER = "#4A6080"
_ACTIVE_BG = "#123D7A"
_USER_BG = "#061D43"

# key, label, icon, admin_only
NAV_ITEMS = [
    ("dashboard",  "Dashboard",     "◈", False),
    ("pos",        "POS",           "🛒", False),
    ("parts",      "Parts Library", "⊞", False),
    ("stock_in",   "Stock In",      "↓", False),
    ("stock_out",  "Stock Out",     "↑", False),
    ("returns",    "Returns",       "↩", False),
    ("suppliers",  "Suppliers",     "⊙", False),
    ("reports",    "Reports",       "≡", False),
    ("settings", "Settings", "⚙", True),
]


class NavSidebar(ctk.CTkFrame):

    def __init__(self, parent, on_navigate, on_logout, on_collapse=None, **kwargs):
        super().__init__(parent, fg_color=COLORS["navy"],
                         corner_radius=0, width=220, **kwargs)
        self.pack_propagate(False)
        self.on_navigate = on_navigate
        self.on_logout = on_logout
        self.on_collapse = on_collapse
        self._active = "dashboard"
        self._buttons = {}
        self._build()

    def _build(self):
        # Logo
        logo = ctk.CTkFrame(self, fg_color="transparent", height=102)
        logo.pack(fill="x")
        logo.pack_propagate(False)
        if self.on_collapse:
            ctk.CTkButton(logo, text="‹", width=26, height=26,
                          fg_color="transparent", hover_color=_DIV,
                          text_color=_MUTED, font=("Helvetica", 18, "bold"),
                          command=self.on_collapse).pack(
                side="right", anchor="n", padx=(0, 12), pady=20)
        txt = ctk.CTkFrame(logo, fg_color="transparent")
        txt.pack(side="left", fill="both", expand=True)
        brand = ctk.CTkFrame(txt, fg_color="transparent")
        brand.pack(anchor="w", padx=22, pady=(18, 2))
        self._navbar_logo = self._load_navbar_logo(26)
        if self._navbar_logo:
            ctk.CTkLabel(brand, image=self._navbar_logo, text="",
                         width=30).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(brand, text="Invent",
                     font=("Helvetica", 20, "bold"),
                     text_color="#FFFFFF").pack(side="left", padx=0)
        ctk.CTkLabel(brand, text="ra",
                     font=("Helvetica", 20, "bold"),
                     text_color=COLORS["amber"]).pack(side="left", padx=0)
        ctk.CTkLabel(txt, text="Inventory & Sales System",
                     font=FONTS["small"],
                     text_color=COLORS["sidebar_sub"],
                     anchor="w").pack(anchor="w", padx=22, pady=(0, 4))

        ctk.CTkFrame(self, fg_color=_DIV, height=1).pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkLabel(self, text="WORKSPACE",
                     font=("Helvetica", 9, "bold"),
                     text_color=_LBL).pack(anchor="w", padx=22, pady=(0, 8))

        # Nav items — filtered by role
        admin = is_admin()
        for key, label, icon, admin_only in NAV_ITEMS:
            if admin_only and not admin:
                continue
            self._buttons[key] = self._nav_btn(key, label, icon)

        # User info + logout — pinned to the BOTTOM so it stays visible no matter
        # how many nav items there are (side="bottom" reserves its space first).
        user = get_current_user()
        user_frame = ctk.CTkFrame(self, fg_color=_USER_BG, corner_radius=0, height=96)
        user_frame.pack(fill="x", side="bottom")
        user_frame.pack_propagate(False)
        ctk.CTkFrame(self, fg_color=_DIV, height=1).pack(
            fill="x", padx=16, side="bottom")
        inner = ctk.CTkFrame(user_frame, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        # Name on its own full-width row so a long name never squeezes the button.
        ctk.CTkLabel(inner,
                     text=f"👤  {user.full_name if user else 'Unknown'}",
                     font=("Helvetica", 12, "bold"),
                     text_color="#FFFFFF",
                     anchor="w").pack(fill="x")

        # Role on the left, Sign Out (fixed width) on the right of the next row.
        role_row = ctk.CTkFrame(inner, fg_color="transparent")
        role_row.pack(fill="x", pady=(4, 0))
        role_label = (
            "Admin" if user and user.is_admin else "Staff") if user else ""
        ctk.CTkLabel(role_row,
                     text=role_label,
                     font=FONTS["small"],
                     text_color=COLORS["sidebar_sub"],
                     anchor="w").pack(side="left")
        ctk.CTkButton(role_row, text="Sign Out",
                      fg_color=COLORS["amber"], hover_color="#EA580C",
                      text_color="#FFFFFF", font=FONTS["small"],
                      height=28, width=82, corner_radius=8,
                      command=self.on_logout).pack(side="right")

        self._set_active("dashboard")

    def _load_navbar_logo(self, size):
        try:
            from PIL import Image

            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(root, "assets", "logo_navbar_nav.png")
            img = Image.open(path).convert("RGBA")
            return ctk.CTkImage(light_image=img, dark_image=img,
                                size=(size, size))
        except Exception:
            return None

    def _nav_btn(self, key, label, icon):
        frame = ctk.CTkFrame(self, fg_color="transparent",
                             corner_radius=0, height=48)
        frame.pack(fill="x", pady=1)
        frame.pack_propagate(False)
        inner = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=10)
        inner.pack(fill="both", expand=True, padx=10, pady=3)
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="both", expand=True)
        bar = ctk.CTkFrame(row, fg_color="transparent", width=3, corner_radius=3)
        bar.pack(side="left", fill="y", padx=(0, 6), pady=8)

        icon_lbl = ctk.CTkLabel(row, text=icon, width=24,
                                font=("Helvetica", 15), text_color=_MUTED)
        icon_lbl.pack(side="left", padx=(0, 8), pady=8)
        text_lbl = ctk.CTkLabel(row, text=label, font=FONTS["body"],
                                text_color=_MUTED, anchor="w")
        text_lbl.pack(side="left", fill="x", expand=True)

        for w in [inner, row, icon_lbl, text_lbl, frame, bar]:
            w.bind("<Button-1>", lambda e, k=key: self._click(k))
            w.configure(cursor="hand2")
        return {"frame": frame, "inner": inner, "icon": icon_lbl, "text": text_lbl, "bar": bar}

    def _click(self, key):
        self.on_navigate(key)

    def _set_active(self, key):
        self._active = key
        for k, w in self._buttons.items():
            if k == key:
                w["inner"].configure(fg_color=_ACTIVE_BG)
                w["bar"].configure(fg_color=COLORS["amber"])
                w["icon"].configure(text_color="#FFFFFF")
                w["text"].configure(text_color="#FFFFFF",
                                    font=("Helvetica", 13, "bold"))
            else:
                w["inner"].configure(fg_color="transparent")
                w["bar"].configure(fg_color="transparent")
                w["icon"].configure(text_color=_MUTED)
                w["text"].configure(text_color=_MUTED, font=FONTS["body"])

    def navigate_to(self, key):
        if key in self._buttons:
            self._set_active(key)
