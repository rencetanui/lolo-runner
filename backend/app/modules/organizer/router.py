import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db.session import get_db
from app.modules.auth.models import Role, User

from . import service
from .schemas import (
    DistanceIn, DistanceUpdate, EventAdminOut, EventIn, EventSummaryOut, EventUpdate, ParticipantPage,
)

router = APIRouter(prefix="/organizer/events", tags=["Organizer"])

OrganizerUser = Annotated[User, Depends(require_role(Role.organizer, Role.admin))]
DB = Annotated[Session, Depends(get_db)]


@router.get("", response_model=list[EventSummaryOut])
def list_events(user: OrganizerUser, db: DB):
    return service.list_events(db, user)


@router.post("", response_model=EventAdminOut, status_code=status.HTTP_201_CREATED)
def create_event(data: EventIn, user: OrganizerUser, db: DB):
    return service.create_event(db, user, data)


@router.get("/{event_id}", response_model=EventAdminOut)
def get_event(event_id: uuid.UUID, user: OrganizerUser, db: DB):
    return service.get_event(db, user, event_id)


@router.patch("/{event_id}", response_model=EventAdminOut)
def update_event(event_id: uuid.UUID, data: EventUpdate, user: OrganizerUser, db: DB):
    return service.update_event(db, user, event_id, data)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(event_id: uuid.UUID, user: OrganizerUser, db: DB):
    service.delete_event(db, user, event_id)


@router.post("/{event_id}/publish", response_model=EventAdminOut)
def publish_event(event_id: uuid.UUID, user: OrganizerUser, db: DB):
    return service.publish_event(db, user, event_id)


@router.post("/{event_id}/unpublish", response_model=EventAdminOut)
def unpublish_event(event_id: uuid.UUID, user: OrganizerUser, db: DB):
    return service.unpublish_event(db, user, event_id)


@router.post("/{event_id}/distances", response_model=EventAdminOut, status_code=status.HTTP_201_CREATED)
def add_distance(event_id: uuid.UUID, data: DistanceIn, user: OrganizerUser, db: DB):
    return service.add_distance(db, user, event_id, data)


@router.patch("/{event_id}/distances/{distance_id}", response_model=EventAdminOut)
def update_distance(event_id: uuid.UUID, distance_id: uuid.UUID, data: DistanceUpdate, user: OrganizerUser, db: DB):
    return service.update_distance(db, user, event_id, distance_id, data)


@router.delete("/{event_id}/distances/{distance_id}", response_model=EventAdminOut)
def delete_distance(event_id: uuid.UUID, distance_id: uuid.UUID, user: OrganizerUser, db: DB):
    return service.delete_distance(db, user, event_id, distance_id)


@router.get("/{event_id}/participants", response_model=ParticipantPage)
def list_participants(
    event_id: uuid.UUID,
    user: OrganizerUser,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    include_cancelled: bool = False,
):
    return service.list_participants(
        db, user, event_id, include_cancelled=include_cancelled, limit=page_size, offset=(page - 1) * page_size
    )


@router.get("/{event_id}/participants.csv")
def participants_csv(event_id: uuid.UUID, user: OrganizerUser, db: DB):
    content, filename = service.participants_csv(db, user, event_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )