from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from database.base import Base
from config.settings import DB_PATH

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    connect_args={"check_same_thread": False},
    echo=False,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, _):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def init_db():
    from database.models import (category, supplier, part, stock_in, stock_out,
                                  audit_log, user, app_setting, sale, sale_item,
                                  stock_adjustment, customer_return, sale_fee)
    Base.metadata.create_all(bind=engine)
    _migrate()
    _create_views()
    _seed_defaults()

def _migrate():
    migrations = [
        ("parts",     "selling_price",   "REAL DEFAULT 0.0"),
        ("stock_out", "selling_price",   "REAL DEFAULT 0.0"),
        ("stock_out", "discount_pct",    "REAL DEFAULT 0.0"),
        ("stock_out", "discount_amount", "REAL DEFAULT 0.0"),
        ("stock_out", "subtotal",        "REAL DEFAULT 0.0"),
        ("stock_out", "total_amount",    "REAL DEFAULT 0.0"),
        ("stock_out", "unit_cost",       "REAL DEFAULT 0.0"),
        ("stock_out", "gross_profit",    "REAL DEFAULT 0.0"),
        # POS sale-level discount (added after initial POS release)
        ("sales",     "discount_type",   "TEXT DEFAULT 'amount'"),
        ("sales",     "discount_value",  "REAL DEFAULT 0.0"),
        ("sales",     "labor_amount",    "REAL DEFAULT 0.0"),
    ]
    with engine.connect() as conn:
        for table, col, col_def in migrations:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}"))
                conn.commit()
            except Exception:
                pass

def _create_views(target_engine=None):
    eng = target_engine or engine
    with eng.connect() as conn:
        conn.execute(text("DROP VIEW IF EXISTS part_stock"))
        conn.execute(text("""
        CREATE VIEW part_stock AS
        SELECT
            p.id, p.sku, p.name, p.min_stock, p.bin_location,
            p.unit_cost, p.selling_price, p.unit,
            c.name      AS category,
            c.color_hex AS category_color,
            COALESCE((SELECT SUM(si.quantity) FROM stock_in si  WHERE si.part_id=p.id),0) AS total_in,
            COALESCE((SELECT SUM(so.quantity) FROM stock_out so WHERE so.part_id=p.id),0) AS total_out,
            (COALESCE((SELECT SUM(si.quantity) FROM stock_in si  WHERE si.part_id=p.id),0)
             - COALESCE((SELECT SUM(so.quantity) FROM stock_out so WHERE so.part_id=p.id),0)
             + COALESCE((SELECT SUM(sa.delta) FROM stock_adjustments sa WHERE sa.part_id=p.id),0)
             + COALESCE((SELECT SUM(cr.restock_qty) FROM customer_returns cr WHERE cr.part_id=p.id),0)
            ) AS current_stock,
            p.unit_cost * (
                COALESCE((SELECT SUM(si.quantity) FROM stock_in si  WHERE si.part_id=p.id),0)
                - COALESCE((SELECT SUM(so.quantity) FROM stock_out so WHERE so.part_id=p.id),0)
                + COALESCE((SELECT SUM(sa.delta) FROM stock_adjustments sa WHERE sa.part_id=p.id),0)
                + COALESCE((SELECT SUM(cr.restock_qty) FROM customer_returns cr WHERE cr.part_id=p.id),0)
            ) AS stock_value,
            CASE WHEN (
                COALESCE((SELECT SUM(si.quantity) FROM stock_in si  WHERE si.part_id=p.id),0)
                - COALESCE((SELECT SUM(so.quantity) FROM stock_out so WHERE so.part_id=p.id),0)
                + COALESCE((SELECT SUM(sa.delta) FROM stock_adjustments sa WHERE sa.part_id=p.id),0)
                + COALESCE((SELECT SUM(cr.restock_qty) FROM customer_returns cr WHERE cr.part_id=p.id),0)
            ) <= p.min_stock THEN 1 ELSE 0 END AS is_low_stock,
            p.vehicle_makes, p.is_active, p.created_at
        FROM parts p
        LEFT JOIN categories c ON c.id=p.category_id
        WHERE p.is_active=1
        """))
        conn.commit()

def _seed_defaults():
    from database.models.category import Category
    from database.models.user import User
    from core.services.auth_service import AuthService
    with SessionLocal() as session:
        if session.query(Category).count() == 0:
            session.add_all([
                Category(name="Engine",      color_hex="#2D8C5A"),
                Category(name="Brakes",      color_hex="#4338CA"),
                Category(name="Electrical",  color_hex="#2563EB"),
                Category(name="Suspension",  color_hex="#C0392B"),
                Category(name="Lubricants",  color_hex="#C47C22"),
                Category(name="Filters",     color_hex="#7C3AED"),
                Category(name="Accessories", color_hex="#0891B2"),
                Category(name="Body",        color_hex="#78716C"),
            ])
            session.commit()
        AuthService(session).ensure_default_admin()

def get_session():
    return SessionLocal()
