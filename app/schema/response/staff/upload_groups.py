import dataclasses
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.schema.response.staff.uploads import (
    UploadRequestPhotoListResponse,
    UploadRequestPhotoSchema,
    UploadRequestSchema,
)
from app.service.upload_requests import UploadRequestGroupDetails
from db.generated.models import UploadRequestGroup, UploadRequestPhoto


class UploadRequestGroupSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_id: UUID
    folder_id: str
    requested_by: UUID
    approved_by: UUID | None
    status: str
    processing_status: str
    total_photo_count: int
    batch_count: int
    processed_photo_count: int
    failed_photo_count: int
    created_at: datetime
    approved_at: datetime | None
    rejection_reason: str | None
    error_message: str | None
    requests: list[UploadRequestSchema]

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v: object) -> str:
        return getattr(v, "value", str(v))

    @classmethod
    def from_details(cls, details: UploadRequestGroupDetails) -> "UploadRequestGroupSchema":
        data = dataclasses.asdict(details.group)
        data["requests"] = [
            UploadRequestSchema.from_details(req) for req in details.requests
        ]
        return cls.model_validate(data)


class UploadRequestGroupListResponse(BaseModel):
    items: list[UploadRequestGroupSchema]

    @classmethod
    def from_details_list(
        cls,
        details_list: list[UploadRequestGroupDetails],
    ) -> "UploadRequestGroupListResponse":
        return cls(items=[UploadRequestGroupSchema.from_details(d) for d in details_list])


class UploadRequestGroupPhotoListResponse(UploadRequestPhotoListResponse):
    @classmethod
    def from_photos(
        cls,
        photos: list[UploadRequestPhoto],
    ) -> "UploadRequestGroupPhotoListResponse":
        return cls(
            items=[UploadRequestPhotoSchema.model_validate(p) for p in photos]
        )

class UploadRequestGroupSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    event_id: UUID
    folder_id: str
    status: str
    processing_status: str
    total_photo_count: int
    batch_count: int
    processed_photo_count: int
    failed_photo_count: int
    created_at: datetime
    approved_at: datetime | None
    rejection_reason: str | None
    error_message: str | None

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v: object) -> str:
        return getattr(v, "value", str(v))


class UploadRequestGroupSummaryListResponse(BaseModel):
    items: list[UploadRequestGroupSummarySchema]

    @classmethod
    def from_groups(cls, groups: list["UploadRequestGroup"]) -> "UploadRequestGroupSummaryListResponse":
        return cls(items=[UploadRequestGroupSummarySchema.model_validate(g) for g in groups])
