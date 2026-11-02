import sys

from app.db.session import SessionLocal
from app.modules.auth.models import Role
from app.modules.auth.service import get_by_email

with SessionLocal() as db:
    user = get_by_email(db, sys.argv[1])
    if not user:
        sys.exit("No user with that email")
    user.role = Role.admin
    db.commit()
    print(f"{user.email} is now an admin")