"""
Open a rendered receipt in the user's browser so they can use the native print
dialog. The desktop stack (Tkinter) has no direct printer integration, so this
preview-and-print approach is the practical option and reuses the shared
receipt_renderer (so printed totals match the stored sale exactly).
"""
import os
import tempfile
import webbrowser
from core.services.receipt_renderer import render_receipt_html


def open_receipt(sale_detail: dict, settings: dict = None):
    html = render_receipt_html(sale_detail, settings)
    fd, path = tempfile.mkstemp(
        suffix=".html", prefix=f"receipt_{sale_detail.get('receipt_no', 'sale')}_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open("file://" + path.replace("\\", "/"))
    return path
