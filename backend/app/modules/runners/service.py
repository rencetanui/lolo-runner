import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import RunnerProfile
from .schemas import RunnerProfileIn


def get_profile(db: Session, user_id: uuid.UUID) -> RunnerProfile | None:
    return db.scalars(select(RunnerProfile).where(RunnerProfile.user_id == user_id)).first()


def upsert_profile(db: Session, user_id: uuid.UUID, data: RunnerProfileIn) -> RunnerProfile:
    profile = get_profile(db, user_id)
    if profile is None:
        profile = RunnerProfile(user_id=user_id)
        db.add(profile)
    for field, value in data.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return profile