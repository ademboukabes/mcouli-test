from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schema.response.staff.uploads import UploadRequestPhotoListResponse, UploadRequestSchema
from app.service.upload_requests import UploadRequestGroupDetails
from db.generated.models import UploadRequestPhoto


class UploadRequestGroupSchema(BaseModel):
    id: UUID
    event_id: UUID
    folder_id: str
    requested_by: UUID
    approved_by: UUID | None
    status: str
    total_photo_count: int
    batch_count: int
    created_at: datetime
    approved_at: datetime | None
    rejection_reason: str | None
    requests: list[UploadRequestSchema]

    @classmethod
    def from_details(
        cls,
        details: UploadRequestGroupDetails,
    ) -> "UploadRequestGroupSchema":
        return cls(
            id=details.group.id,
            event_id=details.group.event_id,
            folder_id=details.group.folder_id,
            requested_by=details.group.requested_by,
            approved_by=details.group.approved_by,
            status=getattr(details.group.status, "value", str(details.group.status)),
            total_photo_count=details.group.total_photo_count,
            batch_count=details.group.batch_count,
            created_at=details.group.created_at,
            approved_at=details.group.approved_at,
            rejection_reason=details.group.rejection_reason,
            requests=[
                UploadRequestSchema.from_models(request_details.request, request_details.photos)
                for request_details in details.requests
            ],
        )


class UploadRequestGroupListResponse(BaseModel):
    items: list[UploadRequestGroupSchema]

    @classmethod
    def from_details_list(
        cls,
        details_list: list[UploadRequestGroupDetails],
    ) -> "UploadRequestGroupListResponse":
        return cls(items=[UploadRequestGroupSchema.from_details(details) for details in details_list])


class UploadRequestGroupPhotoListResponse(UploadRequestPhotoListResponse):
    @classmethod
    def from_photos(
        cls,
        photos: list[UploadRequestPhoto],
    ) -> "UploadRequestGroupPhotoListResponse":
        base_response = UploadRequestPhotoListResponse.from_models(photos)
        return cls(items=base_response.items)
