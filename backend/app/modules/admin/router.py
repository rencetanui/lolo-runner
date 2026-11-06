import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.db.session import get_db
from app.modules.auth.models import Role, User
from app.modules.payments import service as payments
from app.modules.payments.models import PaymentStatus
from app.modules.payments.providers.mpesa import get_mpesa_client
from app.modules.refunds import service as refunds
from app.modules.refunds.models import RefundStatus

from . import service
from .schemas import (
    AdminPaymentDetail, AdminPaymentPage, AdminRefundDetail, AdminRefundPage, AdminSummary,
    CreateRefundIn, MarkPaidIn, RejectRefundIn, ResolveIn,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

AdminUser = Annotated[User, Depends(require_role(Role.admin))]
DB = Annotated[Session, Depends(get_db)]


@router.get("/summary", response_model=AdminSummary)
def summary(admin: AdminUser, db: DB):
    return service.summary(db)


# ------------------------------------------------------------------ payments
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


@router.post("/payments/{payment_id}/refund", response_model=AdminRefundDetail, status_code=status.HTTP_201_CREATED)
def create_refund(payment_id: uuid.UUID, data: CreateRefundIn, admin: AdminUser, db: DB):
    refund = refunds.create_admin_refund(db, admin, payment_id, data.note)
    return service.get_refund(db, refund.id)


# ------------------------------------------------------------------ refunds
@router.get("/refunds", response_model=AdminRefundPage)
def list_refunds(
    admin: AdminUser,
    db: DB,
    status: RefundStatus | None = None,
    q: str | None = Query(default=None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    return service.list_refunds(db, status=status, q=q, page=page, page_size=page_size)


@router.get("/refunds/{refund_id}", response_model=AdminRefundDetail)
def get_refund(refund_id: uuid.UUID, admin: AdminUser, db: DB):
    return service.get_refund(db, refund_id)


@router.post("/refunds/{refund_id}/paid", response_model=AdminRefundDetail)
def mark_refund_paid(refund_id: uuid.UUID, data: MarkPaidIn, admin: AdminUser, db: DB):
    refunds.mark_paid(db, admin, refund_id, data.mpesa_reference, data.note)
    return service.get_refund(db, refund_id)


@router.post("/refunds/{refund_id}/reject", response_model=AdminRefundDetail)
def reject_refund(refund_id: uuid.UUID, data: RejectRefundIn, admin: AdminUser, db: DB):
    refunds.reject(db, admin, refund_id, data.note)
    return service.get_refund(db, refund_id)