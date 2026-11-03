import hmac
import uuid

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.auth.models import User

from . import service
from .providers.mpesa import get_mpesa_client
from .schemas import PaymentIn, PaymentOut

router = APIRouter(tags=["Payments"])


@router.post(
    "/registrations/{registration_id}/payments",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
def start_payment(
    registration_id: uuid.UUID,
    data: PaymentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    mpesa=Depends(get_mpesa_client),
):
    return service.start_payment(db, user, registration_id, data, mpesa)


@router.get("/registrations/{registration_id}/payments", response_model=list[PaymentOut])
def list_payments(
    registration_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_for_registration(db, user, registration_id)


@router.post("/payments/{payment_id}/check", response_model=PaymentOut)
def check_payment(
    payment_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    mpesa=Depends(get_mpesa_client),
):
    return service.check_payment(db, user, payment_id, mpesa)


@router.post("/payments/callbacks/stk/{secret}", include_in_schema=False)
def stk_callback(secret: str, payload: dict = Body(...), db: Session = Depends(get_db)):
    expected = settings.mpesa_callback_secret
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    service.handle_stk_callback(db, payload)
    return {"ResultCode": 0, "ResultDesc": "Accepted"}