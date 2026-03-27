from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID

from app.schema.internal.uploads import UploadPhotoInput


MAX_UPLOAD_BATCH_SIZE = 20


class CreateUploadRequestPhotoRequest(BaseModel):
    drive_file_id: str = Field(min_length=1, max_length=255)
    taken_at: datetime | None = None
    day_number: int | None = None
    visibility: str = "private"

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
    folder_id: str | None = Field(default=None, min_length=1, max_length=255)
    photos: list[CreateUploadRequestPhotoRequest] | None = Field(
        default=None,
        min_length=1,
        max_length=MAX_UPLOAD_BATCH_SIZE,
    )
    visibility: str = "private"
    day_number: int | None = None

    @field_validator("folder_id", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped_value = value.strip()
            return stripped_value or None
        return value

    @field_validator("visibility")
    @classmethod
    def _validate_request_visibility(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if normalized_value not in {"private", "public"}:
            raise ValueError("visibility must be either 'private' or 'public'")
        return normalized_value

    @model_validator(mode="after")
    def _validate_source(self) -> "CreateUploadRequestRequest":
        has_folder = self.folder_id is not None
        has_photos = self.photos is not None
        if has_folder == has_photos:
            raise ValueError("Exactly one of folder_id or photos must be provided")
        return self

    def to_inputs(self) -> list[UploadPhotoInput]:
        if self.photos is None:
            return []
        return [photo.to_input() for photo in self.photos]


class RejectUploadRequestRequest(BaseModel):
    reason: str | None = None
