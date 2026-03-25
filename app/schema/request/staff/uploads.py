from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator
from uuid import UUID

from app.schema.internal.uploads import UploadPhotoInput


MAX_UPLOAD_BATCH_SIZE = 20


class CreateUploadRequestPhotoRequest(BaseModel):
    drive_file_id: str = Field(min_length=1, max_length=255)
    taken_at: datetime | None = None
    day_number: int | None = None
    visibility: Literal["private","public"]

    @field_validator("drive_file_id", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("visibility")
    @classmethod
    def _validate_visibility(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if normalized_value not in {"private", "public"}:
            raise ValueError("visibility must be either 'private' or 'public'")
        return normalized_value

    def to_input(self) -> UploadPhotoInput:
        return UploadPhotoInput(
            drive_file_id=self.drive_file_id,
            taken_at=self.taken_at,
            day_number=self.day_number,
            visibility=self.visibility,
        )


class CreateUploadRequestRequest(BaseModel):
    event_id: UUID
    photos: list[CreateUploadRequestPhotoRequest] = Field(
        min_length=1,
        max_length=MAX_UPLOAD_BATCH_SIZE,
    )

    def to_inputs(self) -> list[UploadPhotoInput]:
        return [photo.to_input() for photo in self.photos]


class RejectUploadRequestRequest(BaseModel):
    reason: str | None = None
