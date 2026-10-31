"""Import every module's models here so Alembic autogenerate sees them (env.py imports this file)."""
from app.modules.accounts.models import RefreshToken, User, UserRole  # noqa: F401
