from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

from . import service

router = APIRouter(tags=["Health"], include_in_schema=False)


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(status_code=503, content={"status": "database unavailable"})
    return {"status": "ok"}


@router.get("/health/worker")
def worker_health(db: Session = Depends(get_db)):
    status = service.worker_status(db)
    return JSONResponse(status_code=200 if status["ok"] else 503, content=status)