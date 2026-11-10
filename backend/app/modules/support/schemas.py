import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import SupportStatus, SupportTopic


class SupportIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    topic: SupportTopic = SupportTopic.other
    message: str = Field(min_length=10, max_length=2000)
    website: str = Field(default="", max_length=200, description="Spam trap: real people leave it empty.")


class SupportCreatedOut(BaseModel):
    reference: str
    message: str


class AdminSupportOut(BaseModel):
    id: uuid.UUID
    reference: str
    created_at: datetime
    name: str
    email: str
    topic: SupportTopic
    message: str
    status: SupportStatus
    user_id: uuid.UUID | None
    resolved_at: datetime | None
    resolved_by_name: str | None
    admin_note: str | None


class SupportPage(BaseModel):
    items: list[AdminSupportOut]
    total: int


class ResolveSupportIn(BaseModel):
    note: str | None = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None