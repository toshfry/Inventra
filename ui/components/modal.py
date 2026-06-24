import tkinter as tk
import customtkinter as ctk
from config.themes import COLORS, FONTS


class Modal(ctk.CTkToplevel):
    """Base modal dialog."""

    def __init__(self, parent, title: str, width: int = 520, height: int = 400):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.configure(fg_color=COLORS["bg"])
        self.grab_set()
        self.lift()
        self.focus_force()
        self._center(parent, width, height)

        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["card"],
                               corner_radius=0, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text=title, font=FONTS["heading"],
                     text_color=COLORS["txt"]).pack(side="left", padx=20, pady=14)
        # No custom ✕ here — the native window title bar already provides a
        # close button, so a second one would be redundant/confusing.

        # Body
        self.body = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"],
                                            corner_radius=0)
        self.body.pack(fill="both", expand=True, padx=0, pady=0)

        # Footer
        self.footer = ctk.CTkFrame(self, fg_color=COLORS["card"],
                                    corner_radius=0, height=56)
        self.footer.pack(fill="x", side="bottom")
        self.footer.pack_propagate(False)

    def _center(self, parent, w, h):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width()  // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"{w}x{h}+{px - w//2}+{py - h//2}")

    def add_footer_buttons(self, cancel_text="Cancel",
                           confirm_text="Confirm",
                           on_confirm=None):
        ctk.CTkButton(
            self.footer, text=cancel_text,
            fg_color=COLORS["bg2"], hover_color=COLORS["border"],
            text_color=COLORS["txt2"], font=FONTS["body"],
            width=100, height=36,
            command=self.destroy,
        ).pack(side="right", padx=8, pady=10)

        ctk.CTkButton(
            self.footer, text=confirm_text,
            fg_color=COLORS["navy"], hover_color=COLORS["navy_hover"],
            text_color="#FFFFFF", font=FONTS["body"],
            width=140, height=36,
            command=on_confirm or self.destroy,
        ).pack(side="right", padx=(0, 4), pady=10)


def field_row(parent, label: str, widget_factory, required=False):
    """Helper: create a label + widget row."""
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.pack(fill="x", padx=20, pady=(0, 12))

    lbl_text = label.upper() + (" *" if required else "")
    ctk.CTkLabel(frame, text=lbl_text, font=FONTS["label"],
                 text_color=COLORS["txt3"]).pack(anchor="w", pady=(0, 4))

    widget = widget_factory(frame)
    widget.pack(fill="x")
    return widget
