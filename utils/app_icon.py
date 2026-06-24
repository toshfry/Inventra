"""
app_icon.py — shared Inventra window icon helper

This sets the visible title-bar/taskbar icon for Tkinter/CustomTkinter windows.
PyInstaller's icon="icon.ico" changes the EXE icon, but Tk/CTk windows also
need iconbitmap() at runtime.
"""

from __future__ import annotations

import os
import sys


def resource_path(relative_path: str) -> str:
    """Find files correctly when running normally or as a PyInstaller EXE."""
    if getattr(sys, "frozen", False):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    return os.path.join(base_path, relative_path)


def set_window_icon(window) -> None:
    """Safely set Inventra's .ico on a CTk/Tk window."""
    try:
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            window.iconbitmap(icon_path)
    except Exception:
        # Never break app startup because of icon loading.
        pass
