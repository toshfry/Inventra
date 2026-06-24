from sqlalchemy import Column, String, Text
from database.base import Base
from datetime import datetime


class AppSetting(Base):
    """
    Generic key/value application settings store.

    The project did not previously have a persisted-settings mechanism
    (settings were either constants in config/ or rows in domain tables).
    This small table provides one consistent place to persist app-level
    configuration such as the POS tax/receipt settings. Values are stored
    as text; callers that need structured data store JSON strings.
    """
    __tablename__ = "app_settings"

    key        = Column(String, primary_key=True)
    value      = Column(Text)
    updated_at = Column(String, nullable=False,
                        default=lambda: datetime.now().isoformat())
