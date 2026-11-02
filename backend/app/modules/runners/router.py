from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.auth.models import User

from . import service
from .schemas import RunnerProfileIn, RunnerProfileOut

router = APIRouter(prefix="/runners", tags=["Runners"])


@router.get("/me", response_model=RunnerProfileOut)
def get_my_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = service.get_profile(db, user.id)
    if not profile:
        raise HTTPException(404, "Runner profile not set up yet")
    return profile


@router.put("/me", response_model=RunnerProfileOut)
def save_my_profile(
    data: RunnerProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.upsert_profile(db, user.id, data)