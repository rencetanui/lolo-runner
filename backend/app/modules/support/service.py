import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.rate_limit import hit
from app.modules.audit.service import log_action
from app.modules.auth.models import User
from app.modules.notifications import service as notifications

from .models import SupportMessage, SupportStatus
from .schemas import AdminSupportOut, SupportCreatedOut, SupportIn, SupportPage

HOUR = timedelta(hours=1)
THANKS = "Thanks. We've received your message and will reply by email."


class SupportError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 409):
        self.code = code
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_message(db: Session, user: User | None, data: SupportIn, ip: str) -> SupportCreatedOut:
    if data.website:
        # A bot filled in the hidden field. Pretend it worked and keep nothing.
        return SupportCreatedOut(reference="--------", message=THANKS)
    hit(db, "support:ip", ip, limit=5, window=HOUR)
    hit(db, "support:email", data.email.lower(), limit=3, window=HOUR)
    msg = SupportMessage(
        id=uuid.uuid4(),
        user_id=user.id if user else None,
        name=data.name,
        email=data.email.lower(),
        topic=data.topic,
        message=data.message,
    )
    db.add(msg)
    notifications.notify_admins_support_message(db, msg)
    db.commit()
    return SupportCreatedOut(reference=str(msg.id)[:8].upper(), message=THANKS)


# ---------------------------------------------------------------- admin
def _out(db: Session, msg: SupportMessage) -> AdminSupportOut:
    resolver = db.get(User, msg.resolved_by) if msg.resolved_by else None
    return AdminSupportOut(
        id=msg.id, reference=str(msg.id)[:8].upper(), created_at=msg.created_at, name=msg.name,
        email=msg.email, topic=msg.topic, message=msg.message, status=msg.status, user_id=msg.user_id,
        resolved_at=msg.resolved_at, resolved_by_name=resolver.full_name if resolver else None,
        admin_note=msg.admin_note,
    )


def list_messages(db: Session, *, status: SupportStatus | None, page: int, page_size: int) -> SupportPage:
    conds = [SupportMessage.status == status] if status else []
    total = db.scalar(select(func.count(SupportMessage.id)).where(*conds)) or 0
    # A queue is worked oldest-first. Anything else reads newest-first.
    order = SupportMessage.created_at.asc() if status == SupportStatus.open else SupportMessage.created_at.desc()
    rows = db.scalars(
        select(SupportMessage).where(*conds).order_by(order).limit(page_size).offset((page - 1) * page_size)
    ).all()
    return SupportPage(items=[_out(db, m) for m in rows], total=total)


def open_count(db: Session) -> int:
    return db.scalar(select(func.count(SupportMessage.id)).where(SupportMessage.status == SupportStatus.open)) or 0


def resolve(db: Session, admin: User, message_id: uuid.UUID, note: str | None) -> AdminSupportOut:
    msg = db.scalars(select(SupportMessage).where(SupportMessage.id == message_id).with_for_update()).first()
    if msg is None:
        raise SupportError("support_not_found", "Message not found", 404)
    if msg.status == SupportStatus.resolved:
        raise SupportError("already_resolved", "This message is already resolved.", 409)
    msg.status = SupportStatus.resolved
    msg.admin_note = note
    msg.resolved_by = admin.id
    msg.resolved_at = _now()
    log_action(db, admin, "support.resolved", "support", msg.id, note=note)
    db.commit()
    return _out(db, msg)


def purge_resolved(db: Session, days: int = 365) -> int:
    """Worker job: delete resolved messages after `days`. They contain personal data. Commits."""
    cutoff = _now() - timedelta(days=days)
    res = db.execute(
        delete(SupportMessage).where(SupportMessage.status == SupportStatus.resolved, SupportMessage.resolved_at < cutoff)
    )
    db.commit()
    return res.rowcount or 0