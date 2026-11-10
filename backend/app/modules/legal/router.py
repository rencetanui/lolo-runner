from fastapi import APIRouter
from pydantic import BaseModel

from .versions import LEGAL_VERSION

router = APIRouter(prefix="/legal", tags=["Legal"])


class VersionOut(BaseModel):
    version: str


@router.get("/version", response_model=VersionOut)
def version():
    return VersionOut(version=LEGAL_VERSION)