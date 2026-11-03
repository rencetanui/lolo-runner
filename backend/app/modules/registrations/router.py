import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.auth.models import User

from . import service
from .schemas import AvailabilityOut, RegistrationIn, RegistrationOut, WaiverOut
from .waiver import WAIVER_TEXT, WAIVER_VERSION

router = APIRouter(tags=["Registrations"])


@router.get("/waiver", response_model=WaiverOut)
def get_waiver():
    return WaiverOut(version=WAIVER_VERSION, text=WAIVER_TEXT)


@router.get("/events/{event_id}/availability", response_model=list[AvailabilityOut])
def get_availability(event_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.availability(db, event_id)


@router.post(
    "/events/{event_id}/registrations",
    response_model=RegistrationOut,
    status_code=status.HTTP_201_CREATED,
)
def register(
    event_id: uuid.UUID,
    data: RegistrationIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.register(db, user, event_id, data)


# "/registrations/me" must be declared before "/registrations/{registration_id}"
@router.get("/registrations/me", response_model=list[RegistrationOut])
def my_registrations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.list_mine(db, user)


@router.get("/registrations/{registration_id}", response_model=RegistrationOut)
def get_registration(
    registration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.get_mine(db, user, registration_id)


@router.delete("/registrations/{registration_id}", response_model=RegistrationOut)
def cancel_registration(
    registration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.cancel(db, user, registration_id)