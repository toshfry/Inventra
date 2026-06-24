from sqlalchemy.orm import Session
from sqlalchemy import text, event
from dataclasses import dataclass, field
from typing import List
import time
from datetime import datetime

_cache: dict = {}
CACHE_TTL = 30

# The dashboard panel only previews the most urgent low-stock parts. Rendering
# every low-stock row (hundreds, on a large catalog) builds thousands of UI
# widgets and freezes the desktop app. The full list lives on the Parts screen.
DASHBOARD_LOW_STOCK_LIMIT = 20


@event.listens_for(Session, "after_commit")
def _invalidate_dashboard_cache(_session):
    """Clear the metrics cache whenever ANY data is committed (sale, stock move,
    edit, etc.). With no changes the cache stays warm, so re-opening the
    Dashboard returns the same object instantly instead of recomputing — which
    lets the screen skip its costly widget rebuild."""
    _cache.clear()

@dataclass
class DashboardMetrics:
    total_parts:       int        = 0
    total_stock_value: float      = 0.0
    low_stock_count:   int        = 0
    stock_in_today:    int        = 0
    stock_out_today:   int        = 0
    sales_today:       float      = 0.0
    profit_today:      float      = 0.0
    sales_this_month:  float      = 0.0
    profit_this_month: float      = 0.0
    top_moving_parts:  List[dict] = field(default_factory=list)
    low_stock_parts:   List[dict] = field(default_factory=list)
    recent_activity:   List[dict] = field(default_factory=list)


class DashboardService:

    def __init__(self, db: Session):
        self.db = db

    def get_metrics(self, force: bool = False) -> DashboardMetrics:
        now = time.time()
        if not force and "metrics" in _cache:
            cached_at, data = _cache["metrics"]
            if now - cached_at < CACHE_TTL:
                return data

        today = datetime.now().strftime("%Y-%m-%d")
        month = datetime.now().strftime("%Y-%m")

        # Period sales & profit: real sales − refunds + labor (labor = pure margin).
        def _period(like):
            rev = self._q(f"SELECT COALESCE(SUM(total_amount),0) FROM stock_out WHERE reason IN ('Sale','POS Sale') AND issued_at LIKE '{like}%'")
            pft = self._q(f"SELECT COALESCE(SUM(gross_profit),0) FROM stock_out WHERE reason IN ('Sale','POS Sale') AND issued_at LIKE '{like}%'")
            refunds = self._q(f"SELECT COALESCE(SUM(refund_amount),0) FROM customer_returns WHERE created_at LIKE '{like}%'")
            rdelta = self._q(f"SELECT COALESCE(SUM(profit_delta),0) FROM customer_returns WHERE created_at LIKE '{like}%'")
            labor = self._q(f"SELECT COALESCE(SUM(labor_amount),0) FROM sales WHERE sale_date LIKE '{like}%'")
            return round(rev - refunds + labor, 2), round(pft + rdelta + labor, 2)

        st_rev, st_pft = _period(today)
        sm_rev, sm_pft = _period(month)

        m = DashboardMetrics(
            total_parts       = self._q("SELECT COUNT(*) FROM parts WHERE is_active=1"),
            total_stock_value = round(self._q("SELECT COALESCE(SUM(stock_value),0) FROM part_stock"), 2),
            low_stock_count   = self._q("SELECT COUNT(*) FROM part_stock WHERE is_low_stock=1"),
            stock_in_today    = self._q(f"SELECT COALESCE(SUM(quantity),0) FROM stock_in  WHERE received_at LIKE '{today}%'"),
            stock_out_today   = self._q(f"SELECT COALESCE(SUM(quantity),0) FROM stock_out WHERE issued_at   LIKE '{today}%'"),
            sales_today       = st_rev,
            profit_today      = st_pft,
            sales_this_month  = sm_rev,
            profit_this_month = sm_pft,
            top_moving_parts  = self._top_movers(5),
            low_stock_parts   = self._low_stock_list(limit=DASHBOARD_LOW_STOCK_LIMIT),
            recent_activity   = self._recent_activity(8),
        )
        _cache["metrics"] = (now, m)
        return m

    def invalidate(self):
        _cache.clear()

    def get_low_stock_parts(self, limit=None):
        """Full low-stock list (reports use this; the dashboard caps the panel)."""
        return self._low_stock_list(limit=limit)

    def _q(self, sql: str):
        return self.db.execute(text(sql)).fetchone()[0]

    def _top_movers(self, limit):
        rows = self.db.execute(text(f"""
            SELECT p.name, SUM(so.quantity) AS qty, COALESCE(SUM(so.total_amount),0) AS rev
            FROM stock_out so JOIN parts p ON p.id=so.part_id
            WHERE so.reason IN ('Sale','POS Sale')
              AND so.issued_at >= datetime('now','-30 days')
            GROUP BY p.id ORDER BY qty DESC LIMIT {limit}
        """)).fetchall()
        return [{"name": r[0], "quantity": r[1], "revenue": round(r[2], 2)} for r in rows]

    def _low_stock_list(self, limit=None):
        sql = """
            SELECT name, current_stock, min_stock, bin_location, category
            FROM part_stock WHERE is_low_stock=1
            ORDER BY current_stock ASC
        """
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = self.db.execute(text(sql)).fetchall()
        return [{"name": r[0], "current": r[1], "min": r[2],
                 "bin": r[3] or "—", "category": r[4] or "—"} for r in rows]

    def _recent_activity(self, limit):
        rows = self.db.execute(text(f"""
            SELECT al.action, al.delta, al.reason, al.created_at,
                   p.name, al.user
            FROM audit_log al LEFT JOIN parts p ON p.id=al.part_id
            ORDER BY al.created_at DESC LIMIT {limit}
        """)).fetchall()
        return [{"action": r[0], "delta": r[1], "reason": r[2],
                 "created_at": r[3], "part_name": r[4] or "—", "user": r[5]} for r in rows]
