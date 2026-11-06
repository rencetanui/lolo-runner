from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User

from .models import AuditLog


def log_action(db: Session, actor: User | None, action: str, entity_type: str, entity_id, **detail) -> None:
    """Add an entry to the caller's transaction. `actor=None` means the system did it."""
    db.add(AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        detail=detail or None,
    ))


def entries_for(db: Session, entity_type: str, entity_id) -> list[AuditLog]:
    return list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == str(entity_id))
            .order_by(AuditLog.created_at)
        )
    )