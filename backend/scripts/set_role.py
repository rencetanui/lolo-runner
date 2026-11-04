"""Usage: python -m scripts.set_role someone@example.com organizer"""
import sys

from app.db.session import SessionLocal
from app.modules.auth.models import Role
from app.modules.auth.service import get_by_email

if len(sys.argv) != 3 or sys.argv[2] not in {r.value for r in Role}:
    sys.exit("Usage: python -m scripts.set_role <email> <runner|organizer|admin>")

with SessionLocal() as db:
    user = get_by_email(db, sys.argv[1])
    if not user:
        sys.exit("No user with that email")
    user.role = Role(sys.argv[2])
    db.commit()
    print(f"{user.email} is now {user.role.value}")