from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import DUMMY_HASH, hash_password, verify_password

from .models import User
from .schemas import SignupIn


class EmailTakenError(Exception):
    pass


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalars(select(User).where(User.email == email.lower())).first()


def create_user(db: Session, data: SignupIn) -> User:
    if get_by_email(db, data.email):
        raise EmailTakenError
    user = User(
        full_name=data.full_name.strip(),
        email=data.email.lower(),
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_by_email(db, email)
    if not user:
        verify_password(password, DUMMY_HASH)  # same work either way
        return None
    if not verify_password(password, user.hashed_password) or not user.is_active:
        return None
    return user