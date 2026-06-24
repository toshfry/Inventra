import customtkinter as ctk
import tkinter as tk
from config.themes import COLORS, FONTS
from ui.components.metric_card import MetricCard
from database.engine import get_session
from core.services.dashboard_service import DashboardService
from datetime import datetime


class DashboardScreen(ctk.CTkFrame):

    def __init__(self, parent, app, **kwargs):
        super().__init__(
            parent, fg_color=COLORS["bg"], corner_radius=0, **kwargs)
        self.app = app
        self._build()

    def _build(self):
        # ── Top bar ───────────────────────────────────────────────────
        topbar = ctk.CTkFrame(self, fg_color=COLORS["card"],
                              corner_radius=0, height=60)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        today = datetime.now().strftime("%A, %B %d %Y")

        title_wrap = ctk.CTkFrame(topbar, fg_color="transparent")
        title_wrap.pack(side="left", padx=24, pady=10)
        ctk.CTkLabel(title_wrap, text="Dashboard",
                     font=FONTS["title"],
                     text_color=COLORS["txt"]).pack(anchor="w")
        ctk.CTkLabel(title_wrap, text="Live overview of your inventory",
                     font=FONTS["small"],
                     text_color=COLORS["txt3"]).pack(anchor="w")

        ctk.CTkLabel(topbar, text=today,
                     font=FONTS["small"],
                     text_color=COLORS["txt3"]).pack(side="right", padx=24)

        ctk.CTkButton(topbar, text="⟳  Refresh",
                      fg_color=COLORS["bg2"],
                      hover_color=COLORS["border"],
                      text_color=COLORS["txt2"],
                      font=FONTS["small"],
                      width=90, height=32,
                      command=lambda: self.refresh(force=True)).pack(side="right", padx=8, pady=14)

        # ── Scrollable content ────────────────────────────────────────
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg"],
                                             corner_radius=0)
        self.scroll.pack(fill="both", expand=True, padx=0, pady=0)

        self._metrics_row = None
        self._alert_frame = None
        self._bottom_row = None
        self._last_metrics = None
        self.refresh()

    def refresh(self, force=False):
        db = get_session()
        try:
            m = DashboardService(db).get_metrics(force=force)
        finally:
            db.close()

        # get_metrics returns the SAME cached object until data changes (any DB
        # commit clears the cache). If nothing changed since the last render,
        # skip rebuilding ~250 widgets so re-opening the Dashboard is instant.
        if not force and m is self._last_metrics:
            return
        self._last_metrics = m

        self._render_metrics(m)
        self._render_alert(m)
        self._render_bottom(m)

    # ── Metrics row ───────────────────────────────────────────────────
    def _render_metrics(self, m):
        low_color = COLORS["red"] if m.low_stock_count > 0 else COLORS["green"]
        low_bg = COLORS["red_bg"] if m.low_stock_count > 0 else COLORS["green_bg"]

        # (label, value, sub, accent, icon, icon_bg)
        specs = [
            ("Total Parts", str(m.total_parts), "Active SKUs",
             COLORS["navy"], "📦", COLORS["navy_bg"]),
            ("Low Stock", str(m.low_stock_count), "Below minimum",
             low_color, "⚠", low_bg),
            ("Inventory Value", f"₱{m.total_stock_value:,.2f}", "At cost price",
             COLORS["teal"], "💰", COLORS["teal_bg"]),
            ("Sales Today", f"₱{m.sales_today:,.2f}",
             f"Profit: ₱{m.profit_today:,.2f}",
             COLORS["blue"], "🛒", COLORS["blue_bg"]),
            ("Sales This Month", f"₱{m.sales_this_month:,.2f}",
             f"Profit: ₱{m.profit_this_month:,.2f}",
             COLORS["purple"], "📈", COLORS["purple_bg"]),
            ("Movements Today", f"↓{m.stock_in_today}  ↑{m.stock_out_today}",
             "Units in / out", COLORS["amber"], "🔄", COLORS["amber_bg"]),
        ]

        # Build the six cards ONCE, then update them in place on later refreshes.
        # Rebuilding them every time cost ~1.4s and made the Dashboard feel slow.
        if getattr(self, "_metric_cards", None):
            for card, (_, val, sub, accent, _, _) in zip(self._metric_cards, specs):
                card.update(val, sub=sub, accent=accent)
            return

        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(20, 0))
        self._metrics_row = row
        for i in range(6):
            row.columnconfigure(i, weight=1, uniform="metric")

        self._metric_cards = []
        for idx, (label, val, sub, accent, icon, icon_bg) in enumerate(specs):
            pad = (0, 6) if idx == 0 else (6, 0) if idx == 5 else 3
            card = MetricCard(row, label, val, sub=sub, accent=accent,
                              icon=icon, icon_bg=icon_bg)
            card.grid(row=0, column=idx, padx=pad, sticky="ew")
            self._metric_cards.append(card)

    # ── Alert banner ──────────────────────────────────────────────────
    def _render_alert(self, m):
        if self._alert_frame:
            self._alert_frame.destroy()
        if m.low_stock_count == 0:
            return

        f = ctk.CTkFrame(self.scroll,
                         fg_color=COLORS["amber_bg"],
                         corner_radius=10,
                         border_width=1,
                         border_color="#E8C87A")
        # Keep the alert above the (persistent) bottom panels in stacking order.
        f.pack(fill="x", padx=20, pady=(14, 0),
               **({"before": self._bottom_row} if self._bottom_row is not None else {}))
        self._alert_frame = f

        inner = ctk.CTkFrame(f, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=10)

        ctk.CTkLabel(inner, text="⚠",
                     font=("Helvetica", 16),
                     text_color=COLORS["amber"]).pack(side="left", padx=(0, 10))

        msg = (f"{m.low_stock_count} part{'s' if m.low_stock_count > 1 else ''} "
               f"{'are' if m.low_stock_count > 1 else 'is'} at or below minimum stock — "
               "reorder recommended before next service day.")
        ctk.CTkLabel(inner, text=msg,
                     font=FONTS["body"],
                     text_color="#7a4d0a",
                     anchor="w").pack(side="left", fill="x", expand=True)

        ctk.CTkButton(inner, text="View →",
                      fg_color="transparent",
                      hover_color=COLORS["amber_bg"],
                      text_color=COLORS["amber"],
                      font=("Helvetica", 12, "bold"),
                      width=70, height=28,
                      command=self.app.show_low_stock_parts).pack(side="right")

    # ── Bottom two-col ────────────────────────────────────────────────
    def _render_bottom(self, m):
        # Build the panel shells (frames + the scrollable container) ONCE, then
        # only refresh their contents. Recreating the shells + CTkScrollableFrame
        # on every redraw was the main remaining cost of a Dashboard refresh.
        if self._bottom_row is None:
            self._build_bottom_shell()
        self._populate_low_stock(m)
        self._populate_movers(m)
        self._populate_activity(m)

    @staticmethod
    def _clear(frame):
        for w in frame.winfo_children():
            w.destroy()

    def _build_bottom_shell(self):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="both", expand=True, padx=20, pady=14)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        self._bottom_row = row

        # Left panel: low-stock, with a persistent scroller + footer label.
        ls_body = self._panel(row, "⚠  Low Stock Alerts", col=0,
                              link_text="View all",
                              link_cmd=self.app.show_low_stock_parts)
        self._ls_scroller = ctk.CTkScrollableFrame(
            ls_body, fg_color="transparent", height=300)
        self._ls_scroller.pack(fill="both", expand=True, padx=0, pady=(0, 4))
        self._ls_footer = ctk.CTkLabel(ls_body, text="", font=FONTS["small"],
                                       text_color=COLORS["txt3"])
        self._ls_footer.pack(pady=(2, 8))

        # Right panel: fast movers (top) + recent activity (bottom).
        right_body = self._panel(row, "Fast-Moving Parts  ·  30 days", col=1,
                                 link_text="Full report",
                                 link_cmd=lambda: self.app.navigate("reports"))
        self._movers_box = ctk.CTkFrame(right_body, fg_color="transparent")
        self._movers_box.pack(fill="x")
        ctk.CTkFrame(right_body, fg_color=COLORS["border"], height=1).pack(
            fill="x", pady=(8, 0))
        ctk.CTkLabel(right_body, text="Recent Activity",
                     font=("Helvetica", 13, "bold"),
                     text_color=COLORS["txt"]).pack(anchor="w", padx=14, pady=(10, 4))
        self._activity_box = ctk.CTkFrame(right_body, fg_color="transparent")
        self._activity_box.pack(fill="x")

    def _panel(self, parent, title: str, col: int, link_text: str = "",
               link_cmd=None) -> ctk.CTkFrame:
        outer = ctk.CTkFrame(parent, fg_color=COLORS["card"],
                             corner_radius=12,
                             border_width=1,
                             border_color=COLORS["border"])
        outer.grid(row=0, column=col,
                   padx=(0, 8) if col == 0 else (8, 0),
                   sticky="nsew")

        header = ctk.CTkFrame(outer, fg_color="transparent", height=44)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(header, text=title,
                     font=("Helvetica", 13, "bold"),
                     text_color=COLORS["txt"]).pack(side="left", padx=16, pady=12)

        if link_text:
            ctk.CTkButton(header, text=link_text,
                          fg_color="transparent",
                          hover_color=COLORS["bg2"],
                          text_color=COLORS["blue"],
                          font=FONTS["small"],
                          width=80, height=26,
                          command=link_cmd).pack(side="right", padx=10)

        sep = ctk.CTkFrame(outer, fg_color=COLORS["border"], height=1)
        sep.pack(fill="x")

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True)
        return body

    def _populate_low_stock(self, m):
        self._clear(self._ls_scroller)

        if not m.low_stock_parts:
            ctk.CTkLabel(self._ls_scroller,
                         text="✓  All parts above minimum stock",
                         font=FONTS["body"],
                         text_color=COLORS["green"]).pack(pady=20)
            self._ls_footer.configure(text="")
            return

        # Keep each row light (3 widgets, not 9): building hundreds of nested
        # frames was a big part of the Dashboard's slow redraw. Name + location
        # go in one multi-line label; the on-hand count sits on the right.
        for part in m.low_stock_parts:
            r = ctk.CTkFrame(self._ls_scroller, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(
                r, justify="left", anchor="w",
                text=(f"{part['name']}\n"
                      f"Bin {part['bin']}  ·  {part['category']}  ·  min {part['min']}"),
                font=FONTS["body"], text_color=COLORS["txt"],
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(r, text=str(part["current"]),
                         font=("Helvetica", 15, "bold"),
                         text_color=COLORS["red"]).pack(side="right", padx=(8, 0))

        # The panel previews only the most urgent rows; point to the full list.
        if m.low_stock_count > len(m.low_stock_parts):
            self._ls_footer.configure(
                text=(f"Showing the {len(m.low_stock_parts)} lowest of "
                      f"{m.low_stock_count} — open Parts for the full list"))
        else:
            self._ls_footer.configure(text="")

    def _populate_movers(self, m):
        self._clear(self._movers_box)
        if not m.top_moving_parts:
            ctk.CTkLabel(self._movers_box,
                         text="No stock-out data in last 30 days",
                         font=FONTS["body"],
                         text_color=COLORS["txt3"]).pack(pady=14)
            return
        max_qty = max(p["quantity"] for p in m.top_moving_parts) or 1
        for part in m.top_moving_parts:
            r = ctk.CTkFrame(self._movers_box, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=4)
            ctk.CTkLabel(r, text=part["name"], font=FONTS["body"],
                         text_color=COLORS["txt2"], width=140,
                         anchor="w").pack(side="left")
            pct = part["quantity"] / max_qty
            bar_bg = ctk.CTkFrame(r, fg_color=COLORS["bg2"], height=8,
                                  corner_radius=4)
            bar_bg.pack(side="left", fill="x", expand=True, padx=(8, 8))
            bar_fill = ctk.CTkFrame(bar_bg, fg_color=COLORS["navy"], height=8,
                                    corner_radius=4, width=max(4, int(pct * 160)))
            bar_fill.place(x=0, y=0, relheight=1)
            ctk.CTkLabel(r, text=str(part["quantity"]), font=FONTS["small"],
                         text_color=COLORS["txt3"], width=36,
                         anchor="e").pack(side="right")

    def _populate_activity(self, m):
        self._clear(self._activity_box)
        ACTION_META = {
            "STOCK_IN":      ("↓", COLORS["green"]),
            "STOCK_OUT":     ("↑", COLORS["amber"]),
            "PART_CREATED":  ("+", COLORS["blue"]),
            "PART_EDITED":   ("✎", COLORS["txt3"]),
            "PART_DELETED":  ("✕", COLORS["red"]),
            "STOCK_ADJUST":  ("⚖", COLORS["purple"]),
            "VOID_SALE":     ("⊘", COLORS["red"]),
            "RETURN":        ("↩", COLORS["teal"]),
        }
        if not m.recent_activity:
            ctk.CTkLabel(self._activity_box, text="No activity yet",
                         font=FONTS["body"], text_color=COLORS["txt3"]).pack(pady=10)
            return
        for act in m.recent_activity[:6]:
            icon, color = ACTION_META.get(act["action"], ("·", COLORS["txt3"]))
            r = ctk.CTkFrame(self._activity_box, fg_color="transparent")
            r.pack(fill="x", padx=14, pady=3)
            ctk.CTkLabel(r, text=icon, font=("Helvetica", 14, "bold"),
                         text_color=color, width=18).pack(side="left")
            desc = act["part_name"]
            if act["delta"]:
                desc = f"{abs(act['delta'])}×  {desc}"
            ctk.CTkLabel(r, text=desc, font=FONTS["body"],
                         text_color=COLORS["txt2"], anchor="w").pack(
                side="left", fill="x", expand=True, padx=6)
            ts = act["created_at"][:16].replace("T", "  ") if act["created_at"] else ""
            ctk.CTkLabel(r, text=ts, font=FONTS["small"],
                         text_color=COLORS["txt3"]).pack(side="right")
