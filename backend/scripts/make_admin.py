"""Promote a signed-up user to platform admin.

Usage (from backend/):  uv run python scripts/make_admin.py [email]
Defaults to ADMIN_EMAIL from .env. The user must have signed up first.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_sessionmaker  # noqa: E402
from app.models import Profile  # noqa: E402


def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else get_settings().admin_email
    if not email:
        print("No email given and ADMIN_EMAIL is not set.")
        return 1
    with get_sessionmaker()() as db:
        profile = db.scalar(select(Profile).where(func.lower(Profile.email) == email.lower()))
        if profile is None:
            print(f"No profile for {email}. Sign up first, then rerun.")
            return 1
        profile.is_admin = True
        db.commit()
    print(f"{email} is now a platform admin.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
