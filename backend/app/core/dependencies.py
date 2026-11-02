import uuid

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.auth.models import Role, User


def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    if not access_token:
        raise unauthorized
    sub = decode_access_token(access_token)
    if not sub:
        raise unauthorized
    try:
        user = db.get(User, uuid.UUID(sub))
    except ValueError:
        raise unauthorized
    if not user or not user.is_active:
        raise unauthorized
    return user


def require_role(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not allowed")
        return user
    return checker