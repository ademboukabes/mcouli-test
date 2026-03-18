from datetime import datetime
from pathlib import PurePath
from typing import ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID

from app.schema.dto.staff.uploads import UploadPhotoInput


MAX_UPLOAD_BATCH_SIZE = 20
MAX_UPLOAD_PHOTO_SIZE_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_MIME_TYPES: dict[str, tuple[str, ...]] = {
    "image/jpeg": (".jpg", ".jpeg"),
    "image/png": (".png",),
    "image/webp": (".webp",),
}


class CreateUploadRequestPhotoRequest(BaseModel):
    drive_file_id: str = Field(min_length=1, max_length=255)
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str
    size_bytes: int = Field(gt=0, le=MAX_UPLOAD_PHOTO_SIZE_BYTES)
    taken_at: datetime | None = None
    day_number: int | None = None
    visibility: str = "private"

    _allowed_mime_types: ClassVar[dict[str, tuple[str, ...]]] = ALLOWED_IMAGE_MIME_TYPES

    @field_validator("drive_file_id", "file_name", mode="before")
    @classmethod
    def _strip_required_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("mime_type")
    @classmethod
    def _validate_mime_type(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if normalized_value not in cls._allowed_mime_types:
            raise ValueError("Unsupported image format")
        return normalized_value

    @field_validator("visibility")
    @classmethod
    def _validate_visibility(cls, value: str) -> str:
        normalized_value = value.strip().lower()
        if normalized_value not in {"private", "public"}:
            raise ValueError("visibility must be either 'private' or 'public'")
        return normalized_value

    @model_validator(mode="after")
    def _validate_file_extension(self) -> "CreateUploadRequestPhotoRequest":
        extension = PurePath(self.file_name).suffix.lower()
        allowed_extensions = self._allowed_mime_types[self.mime_type]
        if extension not in allowed_extensions:
            raise ValueError("file_name extension does not match mime_type")
        return self

    def to_input(self) -> UploadPhotoInput:
        return UploadPhotoInput(
            drive_file_id=self.drive_file_id,
            file_name=self.file_name,
            mime_type=self.mime_type,
            size_bytes=self.size_bytes,
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
