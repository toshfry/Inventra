import customtkinter as ctk
from config.themes import COLORS, FONTS


class MetricCard(ctk.CTkFrame):
    """Clean, premium dashboard stat card with an icon chip and subtle hover."""

    def __init__(self, parent, label: str, value: str,
                 sub: str = "", accent: str = None,
                 icon: str = "", icon_bg: str = None, **kwargs):
        super().__init__(parent,
                         fg_color=COLORS["card"],
                         corner_radius=16,
                         border_width=1,
                         border_color=COLORS["border"],
                         **kwargs)
        self.configure(cursor="hand2")

        self._accent = accent or COLORS["navy"]
        self._icon_bg = icon_bg or COLORS["navy_bg"]

        # Header: icon chip + label
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(16, 6))

        if icon:
            chip = ctk.CTkLabel(top, text=icon, width=32, height=32,
                                corner_radius=10,
                                fg_color=self._icon_bg,
                                text_color=self._accent,
                                font=("Helvetica", 15))
            chip.pack(side="left", padx=(0, 10))

        ctk.CTkLabel(top, text=label.upper(),
                     font=FONTS["label"],
                     text_color=COLORS["txt3"],
                     anchor="w").pack(side="left", fill="x", expand=True)

        self._val_lbl = ctk.CTkLabel(self, text=value,
                                     font=FONTS["metric"],
                                     text_color=accent or COLORS["txt"],
                                     anchor="w")
        self._val_lbl.pack(anchor="w", padx=18)

        self._sub_lbl = ctk.CTkLabel(self, text=sub or " ",
                                     font=FONTS["small"],
                                     text_color=COLORS["txt3"],
                                     anchor="w")
        self._sub_lbl.pack(anchor="w", padx=18, pady=(2, 16))

        # Hover lift — recurse so the effect fires from any child widget too.
        self._bind_hover(self)

    def _bind_hover(self, widget):
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        for child in widget.winfo_children():
            self._bind_hover(child)

    def _on_enter(self, _=None):
        self.configure(border_color=self._accent, fg_color=COLORS["card_hover"])

    def _on_leave(self, _=None):
        self.configure(border_color=COLORS["border"], fg_color=COLORS["card"])

    def update_value(self, value: str, accent: str = None):
        self._val_lbl.configure(text=value,
                                text_color=accent or COLORS["txt"])

    def update(self, value: str, sub: str = None, accent: str = None):
        """Update value, sub-text and accent in place (no widget rebuild)."""
        if accent:
            self._accent = accent
        self._val_lbl.configure(text=value, text_color=self._accent)
        if sub is not None:
            self._sub_lbl.configure(text=sub or " ")
