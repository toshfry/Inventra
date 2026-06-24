from sqlalchemy.orm import Session
from database.models.user import User
from datetime import datetime


# Global session state — set after login
_current_user: User = None


def get_current_user() -> User:
    return _current_user

def set_current_user(user: User):
    global _current_user
    _current_user = user

def logout():
    global _current_user
    _current_user = None

def current_username() -> str:
    return _current_user.username if _current_user else "system"

def is_admin() -> bool:
    return _current_user is not None and _current_user.is_admin


class AuthService:

    def __init__(self, db: Session):
        self.db = db

    def login(self, username: str, password: str) -> User:
        user = self.db.query(User)\
            .filter(User.username == username, User.is_active == 1)\
            .first()
        if not user or not user.check_password(password):
            raise ValueError("Invalid username or password.")
        set_current_user(user)
        return user

    def get_all_users(self):
        return self.db.query(User).order_by(User.username).all()

    def create_user(self, username: str, full_name: str,
                    role: str, password: str) -> User:
        if self.db.query(User).filter(User.username == username).first():
            raise ValueError(f"Username '{username}' already exists.")
        if role not in ("admin", "staff"):
            raise ValueError("Role must be 'admin' or 'staff'.")
        user = User(
            username      = username.strip().lower(),
            full_name     = full_name.strip(),
            role          = role,
            password_hash = User.hash_password(password),
            created_at    = datetime.now().isoformat(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_user(self, user_id: int, full_name: str = None,
                    role: str = None, password: str = None):
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found.")
        if full_name:
            user.full_name = full_name.strip()
        if role and role in ("admin", "staff"):
            user.role = role
        if password:
            user.password_hash = User.hash_password(password)
        self.db.commit()

    def deactivate_user(self, user_id: int):
        user = self.db.get(User, user_id)
        if not user:
            raise ValueError("User not found.")
        # Cannot deactivate the last admin
        if user.is_admin:
            admin_count = self.db.query(User)\
                .filter(User.role == "admin", User.is_active == 1).count()
            if admin_count <= 1:
                raise ValueError("Cannot deactivate the last admin account.")
        user.is_active = 0
        self.db.commit()

    def ensure_default_admin(self):
        """Create default admin if no users exist."""
        if self.db.query(User).count() == 0:
            self.create_user(
                username  = "admin",
                full_name = "Administrator",
                role      = "admin",
                password  = "admin123",
            )
