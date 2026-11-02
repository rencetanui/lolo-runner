import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from app.utils.age import age_category as compute_category
from app.utils.age import age_on
from app.utils.phone import normalize_phone

from .models import Gender, TShirtSize


class RunnerProfileIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    date_of_birth: date
    gender: Gender
    phone: str = Field(min_length=7, max_length=20)
    county: str | None = Field(default=None, max_length=60)
    club: str | None = Field(default=None, max_length=100)
    tshirt_size: TShirtSize
    emergency_contact_name: str = Field(min_length=2, max_length=100)
    emergency_contact_phone: str = Field(min_length=7, max_length=20)
    emergency_contact_relationship: str = Field(min_length=2, max_length=50)
    medical_notes: str | None = Field(
        default=None, max_length=500, description="Conditions, allergies, medication"
    )

    @field_validator("date_of_birth")
    @classmethod
    def dob_is_sensible(cls, v: date) -> date:
        today = date.today()
        if v > today:
            raise ValueError("Date of birth can't be in the future")
        if age_on(v, today) > 110:
            raise ValueError("Please check your date of birth")
        return v

    @field_validator("phone", "emergency_contact_phone")
    @classmethod
    def phone_is_valid(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator("county", "club", "medical_notes", mode="before")
    @classmethod
    def blank_to_none(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class RunnerProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    date_of_birth: date
    gender: Gender
    phone: str
    county: str | None
    club: str | None
    tshirt_size: TShirtSize
    emergency_contact_name: str
    emergency_contact_phone: str
    emergency_contact_relationship: str
    medical_notes: str | None

    @computed_field
    @property
    def age(self) -> int:
        return age_on(self.date_of_birth, date.today())

    @computed_field
    @property
    def age_category(self) -> str:
        return compute_category(self.age, self.gender.value)