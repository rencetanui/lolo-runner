import json
from datetime import date

from fastapi import APIRouter, Depends, Response, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.auth.models import User
from app.modules.auth.router import COOKIE_NAME
from app.modules.auth.schemas import MessageOut, UserOut

from . import service
from .schemas import BlockerOut, DeleteConfirmIn, DeletionCheckOut, NameIn

router = APIRouter(prefix="/account", tags=["Account"])


@router.get("/export")
def export_my_data(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    data = service.export_for_download(db, user)
    body = json.dumps(jsonable_encoder(data), indent=2, ensure_ascii=False)
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="lolo-runner-my-data-{date.today().isoformat()}.json"'},
    )


@router.patch("/name", response_model=UserOut)
def change_name(data: NameIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return service.update_name(db, user, data.full_name)


@router.get("/deletion-check", response_model=DeletionCheckOut)
def deletion_check(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    blockers = service.deletion_blockers(db, user)
    return DeletionCheckOut(can_delete=not blockers, blockers=[BlockerOut(**b) for b in blockers])


@router.post("/delete-request", response_model=MessageOut, status_code=status.HTTP_202_ACCEPTED)
def request_deletion(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service.request_deletion(db, user)
    return MessageOut(message="We've emailed you a link to confirm. It works for 60 minutes.")


@router.post("/delete-confirm", response_model=MessageOut)
def confirm_deletion(
    data: DeleteConfirmIn,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    service.confirm_deletion(db, user, data.token)
    response.delete_cookie(COOKIE_NAME, path="/")
    return MessageOut(message="Your account has been deleted.")