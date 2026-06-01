import dataclasses
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.service.upload_requests import UploadRequestDetails


class UploadRequestPhotoSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    drive_file_id: str
    file_name: str
    mime_type: str
    size_bytes: int
    taken_at: datetime | None
    day_number: int | None
    visibility: str
    status: str
    created_at: datetime


class UploadRequestSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    group_id: UUID | None
    drive_file_id: str | None
    requested_by: UUID
    approved_by: UUID | None
    status: str
    photo_count: int
    created_at: datetime
    approved_at: datetime | None
    rejection_reason: str | None
    photos: list[UploadRequestPhotoSchema]

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v: object) -> str:
        return getattr(v, "value", str(v))

    @classmethod
    def from_details(cls, details: UploadRequestDetails) -> "UploadRequestSchema":
        data = dataclasses.asdict(details.request)
        data["photos"] = [
            UploadRequestPhotoSchema.model_validate(p) for p in details.photos
        ]
        return cls.model_validate(data)


class UploadRequestListResponse(BaseModel):
    items: list[UploadRequestSchema]


class UploadRequestPhotoListResponse(BaseModel):
    items: list[UploadRequestPhotoSchema]
