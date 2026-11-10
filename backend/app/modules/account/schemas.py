from pydantic import BaseModel, ConfigDict, Field


class NameIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str = Field(min_length=2, max_length=100)


class BlockerOut(BaseModel):
    code: str
    message: str


class DeletionCheckOut(BaseModel):
    can_delete: bool
    blockers: list[BlockerOut]


class DeleteConfirmIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)