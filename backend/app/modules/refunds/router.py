import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.auth.models import User

from . import service
from .models import RefundStatus
from .schemas import CancellationPreviewOut, RefundOut

router = APIRouter(tags=["Refunds"])


@router.get("/registrations/{registration_id}/cancellation-preview", response_model=CancellationPreviewOut)
def cancellation_preview(
    registration_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return service.cancellation_preview(db, user, registration_id)


@router.get("/registrations/{registration_id}/refund", response_model=RefundOut | None)
def my_refund(registration_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    refund = service.latest_refund(db, user, registration_id)
    if refund is None:
        return None
    return RefundOut(
        id=refund.id, status=refund.status, reason=refund.reason, amount=refund.amount, phone=refund.phone,
        created_at=refund.created_at, decided_at=refund.decided_at, mpesa_reference=refund.mpesa_reference,
        message=refund.admin_note if refund.status == RefundStatus.rejected else None,
    )