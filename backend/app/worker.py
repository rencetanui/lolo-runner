"""Background worker. Run it next to the API:  python -m app.worker"""
import logging
import signal
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.notifications import service as notifications
from app.modules.notifications.providers import get_email_sender, get_sms_sender
from app.modules.payments import service as payments
from app.modules.payments.providers.mpesa import get_mpesa_client
from app.modules.registrations.service import expire_stale
from app.modules.auth import service as auth_service
from app.modules.support import service as support_service

log = logging.getLogger("worker")


@dataclass(frozen=True)
class Job:
    name: str
    every: float          # seconds between runs
    run: Callable[[Session], object]


def send_notifications(db: Session):
    return notifications.process_due(db, get_email_sender(), get_sms_sender())


def release_expired_holds(db: Session):
    expire_stale(db)
    db.commit()


def settle_payments(db: Session):
    return payments.reconcile_pending(db, get_mpesa_client())


def queue_reminders(db: Session):
    return notifications.enqueue_event_reminders(db)


def purge_notifications(db: Session):
    return notifications.purge_old(db)

def purge_security_data(db: Session):
    return auth_service.purge_expired(db)

def purge_support(db: Session):
    return support_service.purge_resolved(db)

JOBS = [
    Job("send_notifications", 5, send_notifications),
    Job("release_expired_holds", 60, release_expired_holds),
    Job("settle_payments", 60, settle_payments),
    Job("queue_reminders", 600, queue_reminders),
    Job("purge_notifications", 3600, purge_notifications),
    Job("purge_security_data", 3600, purge_security_data),
    Job("purge_support", 3600, purge_support),
]


def _noteworthy(result: object) -> bool:
    if isinstance(result, dict):
        return any(result.values())
    return bool(result)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stopping = False

    def stop(*_args) -> None:
        nonlocal stopping
        stopping = True
        log.info("Stopping after the current job...")

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    last_run = {job.name: float("-inf") for job in JOBS}
    log.info("Worker started with jobs: %s", ", ".join(j.name for j in JOBS))
    while not stopping:
        for job in JOBS:
            if time.monotonic() - last_run[job.name] < job.every:
                continue
            last_run[job.name] = time.monotonic()
            try:
                with SessionLocal() as db:
                    result = job.run(db)
                if _noteworthy(result):
                    log.info("%s: %s", job.name, result)
            except Exception:
                log.exception("Job %s failed; it will run again on schedule", job.name)
        time.sleep(1)
    log.info("Worker stopped")


if __name__ == "__main__":
    main()