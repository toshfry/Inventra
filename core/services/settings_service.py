from sqlalchemy.orm import Session
from database.models.app_setting import AppSetting
from datetime import datetime
import json

# POS settings are stored as a single JSON blob under this key.
_POS_KEY = "pos_settings"
_FEE_TYPES_KEY = "fee_types"

# Safe defaults so the POS works immediately even if Settings is never opened.
POS_DEFAULTS = {
    # Tax
    "tax_enabled": False,
    "tax_name":    "VAT",
    "tax_rate":    0.0,
    "tax_apply":   "after_discount",   # tax applied after discounts by default
    # Receipt print
    "store_name":         "Inventra Store",
    "store_address":      "",
    "store_phone":        "",
    "receipt_footer":     "Thank you for your purchase!",
    "show_cashier":       True,
    "show_sku":           True,
    "show_tax_breakdown": True,
    "paper_size":         "80mm",
}


class SettingsService:
    """Read/write app-level settings (currently the POS tax + receipt config)."""

    def __init__(self, db: Session):
        self.db = db

    # ── Generic key/value ─────────────────────────────────────────────
    def get_raw(self, key: str, default=None):
        row = self.db.get(AppSetting, key)
        return row.value if row else default

    def set_raw(self, key: str, value: str):
        row = self.db.get(AppSetting, key)
        if row:
            row.value = value
            row.updated_at = datetime.now().isoformat()
        else:
            self.db.add(AppSetting(key=key, value=value,
                                   updated_at=datetime.now().isoformat()))
        self.db.commit()

    # ── POS settings ──────────────────────────────────────────────────
    def get_pos_settings(self) -> dict:
        """Return POS settings with safe defaults merged over stored values."""
        result = dict(POS_DEFAULTS)
        raw = self.get_raw(_POS_KEY)
        if raw:
            try:
                stored = json.loads(raw)
                if isinstance(stored, dict):
                    result.update({k: stored[k] for k in stored if k in POS_DEFAULTS})
            except (ValueError, TypeError):
                pass
        return result

    def update_pos_settings(self, updates: dict) -> dict:
        """Merge ``updates`` (only known, non-None keys) and persist."""
        current = self.get_pos_settings()
        for k, v in (updates or {}).items():
            if k in POS_DEFAULTS and v is not None:
                current[k] = v
        self.set_raw(_POS_KEY, json.dumps(current))
        return current

    # ── Service / other fee types ─────────────────────────────────────
    def get_fee_types(self) -> list:
        """Return the configured fee types: list of {name, default_amount}."""
        raw = self.get_raw(_FEE_TYPES_KEY)
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            return []
        out = []
        for d in data if isinstance(data, list) else []:
            name = str(d.get("name", "")).strip()
            if not name:
                continue
            try:
                amt = round(float(d.get("default_amount") or 0), 2)
            except (ValueError, TypeError):
                amt = 0.0
            out.append({"name": name, "default_amount": max(amt, 0.0)})
        return out

    def set_fee_types(self, fee_types: list) -> list:
        """Validate + persist the fee-type list (dedup by name, amount >= 0)."""
        clean, seen = [], set()
        for d in fee_types or []:
            name = str((d or {}).get("name", "")).strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            try:
                amt = max(round(float(d.get("default_amount") or 0), 2), 0.0)
            except (ValueError, TypeError):
                amt = 0.0
            clean.append({"name": name, "default_amount": amt})
        self.set_raw(_FEE_TYPES_KEY, json.dumps(clean))
        return clean
