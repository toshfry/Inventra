import tkinter as tk
from config.themes import COLORS, FONTS


class Toast:
    """Temporary floating notification."""

    def __init__(self, parent, message: str, kind: str = "success", duration: int = 3000):
        self.parent = parent
        colors = {
            "success": (COLORS["green"],    COLORS["green_bg"]),
            "error":   (COLORS["red"],      COLORS["red_bg"]),
            "warning": (COLORS["amber"],    COLORS["amber_bg"]),
            "info":    (COLORS["blue"],     COLORS["blue_bg"]),
        }
        fg, bg = colors.get(kind, colors["info"])

        self.win = tk.Toplevel(parent)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=bg)

        frame = tk.Frame(self.win, bg=bg, padx=16, pady=10)
        frame.pack()

        icons = {"success": "✓", "error": "✕", "warning": "⚠", "info": "ℹ"}
        icon  = icons.get(kind, "ℹ")

        tk.Label(frame, text=f"{icon}  {message}", bg=bg, fg=fg,
                 font=FONTS["body"]).pack()

        self._position()
        parent.after(duration, self.destroy)

    def _position(self):
        self.win.update_idletasks()
        pw = self.parent.winfo_width()
        px = self.parent.winfo_rootx()
        py = self.parent.winfo_rooty()
        w  = self.win.winfo_width()
        x  = px + pw - w - 24
        y  = py + 24
        self.win.geometry(f"+{x}+{y}")

    def destroy(self):
        try:
            self.win.destroy()
        except tk.TclError:
            pass
