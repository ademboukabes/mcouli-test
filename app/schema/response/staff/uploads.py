from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from db.generated.models import UploadRequest, UploadRequestPhoto

class UploadRequestSchema(BaseModel):
    class UploadRequestPhotoSchema(BaseModel):
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

        @classmethod
        def from_model(
            cls,
            photo: UploadRequestPhoto,
        ) -> "UploadRequestSchema.UploadRequestPhotoSchema":
            return cls(
                id=photo.id,
                drive_file_id=photo.drive_file_id,
                file_name=photo.file_name,
                mime_type=photo.mime_type,
                size_bytes=photo.size_bytes,
                taken_at=photo.taken_at,
                day_number=photo.day_number,
                visibility=photo.visibility,
                status=photo.status,
                created_at=photo.created_at,
            )

    id: UUID
    event_id: UUID
    drive_file_id: str | None
    requested_by: UUID
    approved_by: UUID | None
    status: str
    photo_count: int
    created_at: datetime
    approved_at: datetime | None
    rejection_reason: str | None
    photos: list[UploadRequestPhotoSchema]

    @classmethod
    def from_models(
        cls,
        upload_request: UploadRequest,
        photos: list[UploadRequestPhoto],
    ) -> "UploadRequestSchema":
        return cls(
            id=upload_request.id,
            event_id=upload_request.event_id,
            drive_file_id=upload_request.drive_file_id,
            requested_by=upload_request.requested_by,
            approved_by=upload_request.approved_by,
            status=getattr(upload_request.status, "value", str(upload_request.status)),
            photo_count=upload_request.photo_count,
            created_at=upload_request.created_at,
            approved_at=upload_request.approved_at,
            rejection_reason=upload_request.rejection_reason,
            photos=[UploadRequestSchema.UploadRequestPhotoSchema.from_model(photo) for photo in photos],
        )


class UploadRequestListResponse(BaseModel):
    items: list[UploadRequestSchema]

    @classmethod
    def from_models(
        cls,
        items: list[tuple[UploadRequest, list[UploadRequestPhoto]]],
    ) -> "UploadRequestListResponse":
        return cls(
            items=[
                UploadRequestSchema.from_models(upload_request, photos)
                for upload_request, photos in items
            ]
        )


class UploadRequestPhotoListResponse(BaseModel):
    items: list[UploadRequestSchema.UploadRequestPhotoSchema]

    @classmethod
    def from_models(
        cls,
        photos: list[UploadRequestPhoto],
    ) -> "UploadRequestPhotoListResponse":
        return cls(
            items=[UploadRequestSchema.UploadRequestPhotoSchema.from_model(photo) for photo in photos]
        )
