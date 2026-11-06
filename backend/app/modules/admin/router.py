import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db.session import get_db
from app.modules.auth.models import Role, User
from app.modules.payments import service as payments
from app.modules.payments.models import PaymentStatus
from app.modules.payments.providers.mpesa import get_mpesa_client

from . import service
from .schemas import AdminPaymentDetail, AdminPaymentPage, AdminSummary, ResolveIn

router = APIRouter(prefix="/admin", tags=["Admin"])

AdminUser = Annotated[User, Depends(require_role(Role.admin))]
DB = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=AdminSummary)
def summary(admin: AdminUser, db: DB):
    return service.summary(db)


@router.get("/payments", response_model=AdminPaymentPage)
def list_payments(
    admin: AdminUser,
    db: DB,
    status: PaymentStatus | None = None,
    attention: bool = False,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    return service.list_payments(db, status=status, attention=attention, q=q, page=page, page_size=page_size)


@router.get("/payments.csv")
def payments_csv(admin: AdminUser, db: DB, start: date, end: date):
    content, filename = service.payments_csv(db, start, end)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/payments/{payment_id}", response_model=AdminPaymentDetail)
def get_payment(payment_id: uuid.UUID, admin: AdminUser, db: DB):
    return service.get_payment(db, payment_id)


@router.post("/payments/{payment_id}/resolve", response_model=AdminPaymentDetail)
def resolve_payment(payment_id: uuid.UUID, data: ResolveIn, admin: AdminUser, db: DB):
    payments.resolve_review(db, admin, payment_id, data.action, data.note, data.mpesa_receipt)
    return service.get_payment(db, payment_id)


@router.post("/payments/{payment_id}/check", response_model=AdminPaymentDetail)
def recheck_payment(payment_id: uuid.UUID, admin: AdminUser, db: DB, mpesa=Depends(get_mpesa_client)):
    payments.recheck_payment(db, payment_id, mpesa)
    return service.get_payment(db, payment_id)