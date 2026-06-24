from sqlalchemy import Column, Integer, String
from database.base import Base
from datetime import datetime
import hashlib, os

class User(Base):
    __tablename__ = "users"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    username   = Column(String, nullable=False, unique=True)
    full_name  = Column(String, nullable=False)
    role       = Column(String, nullable=False, default="staff")  # "admin" | "staff"
    password_hash = Column(String, nullable=False)
    is_active  = Column(Integer, nullable=False, default=1)
    created_at = Column(String, default=lambda: datetime.now().isoformat())

    @staticmethod
    def hash_password(password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def check_password(self, password: str) -> bool:
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"
