from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_optional_user
from app.core.rate_limit import client_ip
from app.db.session import get_db
from app.modules.auth.models import User

from . import service
from .schemas import SupportCreatedOut, SupportIn

router = APIRouter(prefix="/support", tags=["Support"])


@router.post("", response_model=SupportCreatedOut, status_code=status.HTTP_202_ACCEPTED)
def send_message(
    data: SupportIn,
    request: Request,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    return service.create_message(db, user, data, client_ip(request))