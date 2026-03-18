from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal
import uuid

from app.core.exceptions import AppException
from sqlalchemy.exc import IntegrityError

from app.schema.dto.staff.uploads import UploadPhotoInput
from app.service.staff_notifications import StaffNotificationsService
from db.generated import photos as photo_queries
from db.generated import upload_request_photos as upload_request_photo_queries
from db.generated import upload_requests as upload_request_queries
from db.generated.models import (
    StaffRole,
    StaffUser,
    UploadRequest,
    UploadRequestPhoto,
)


@dataclass
class UploadRequestDetails:
    request: UploadRequest
    photos: list[UploadRequestPhoto]


class UploadRequestsService:
    _mime_type_extensions = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    def __init__(
        self,
        upload_request_querier: upload_request_queries.AsyncQuerier,
        upload_request_photo_querier: upload_request_photo_queries.AsyncQuerier,
        photo_querier: photo_queries.AsyncQuerier,
        staff_notifications_service: StaffNotificationsService,
    ):
        self.upload_request_querier = upload_request_querier
        self.upload_request_photo_querier = upload_request_photo_querier
        self.photo_querier = photo_querier
        self.staff_notifications_service = staff_notifications_service

    @staticmethod
    def _status_value(status: object) -> str:
        return getattr(status, "value", str(status))

    @staticmethod
    def _role_value(role: object) -> str:
        return getattr(role, "value", str(role))

    def _build_staging_storage_key(
        self,
        upload_request_id: uuid.UUID,
        photo: UploadPhotoInput,
    ) -> str:
        extension = self._mime_type_extensions[photo.mime_type]
        return f"staging/upload-requests/{upload_request_id}/{uuid.uuid4()}{extension}"

    @staticmethod
    def _raise_integrity_error(exc: IntegrityError) -> None:
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)

        if sqlstate == "23503":
            raise AppException.bad_request("Invalid event reference") from exc
        if sqlstate == "23505":
            raise AppException.conflict("Duplicate photo in upload request batch") from exc

        raise AppException.internal_error("Failed to persist upload request") from exc

    async def create_request(
        self,
        *,
        event_id: uuid.UUID,
        photos: Sequence[UploadPhotoInput],
        requested_by: StaffUser,
    ) -> UploadRequestDetails:
        if not photos:
            raise AppException.bad_request("At least one photo is required")
        if len(photos) > 20:
            raise AppException.bad_request("A batch can contain at most 20 photos")
        drive_file_ids = [photo.drive_file_id for photo in photos]
        if len(drive_file_ids) != len(set(drive_file_ids)):
            raise AppException.conflict("Duplicate drive_file_id found in upload request batch")

        try:
            upload_request = await self.upload_request_querier.create_upload_request(
                event_id=event_id,
                drive_file_id=None,
                requested_by=requested_by.id,
                photo_count=len(photos),
            )
        except IntegrityError as exc:
            self._raise_integrity_error(exc)
        if upload_request is None:
            raise AppException.internal_error("Failed to create upload request")

        created_photos: list[UploadRequestPhoto] = []
        try:
            for photo in photos:
                created_photo = await self.upload_request_photo_querier.create_upload_request_photo(
                    upload_request_id=upload_request.id,
                    drive_file_id=photo.drive_file_id,
                    staging_storage_key=self._build_staging_storage_key(upload_request.id, photo),
                    taken_at=photo.taken_at,
                    day_number=photo.day_number,
                    visibility=photo.visibility,
                )
                if created_photo is None:
                    raise AppException.internal_error("Failed to create staged upload photo")
                created_photos.append(created_photo)
        except IntegrityError as exc:
            self._raise_integrity_error(exc)

        return UploadRequestDetails(request=upload_request, photos=created_photos)

    async def list_requests(
        self,
        *,
        current_staff_user: StaffUser,
        scope: Literal["my", "all"],
        status: str | None,
    ) -> list[UploadRequestDetails]:
        if scope == "all" and self._role_value(current_staff_user.role) != StaffRole.MULTI_TEAM_LEAD.value:
            raise AppException.forbidden("Multi team lead access required")

        requested_by = current_staff_user.id if scope == "my" else None

        requests: list[UploadRequestDetails] = []
        async for upload_request in self.upload_request_querier.list_upload_requests(
            requested_by=requested_by,
            status=status,
        ):
            requests.append(
                UploadRequestDetails(
                    request=upload_request,
                    photos=await self.list_request_photos(upload_request.id),
                )
            )
        return requests

    async def list_request_photos(
        self,
        upload_request_id: uuid.UUID,
    ) -> list[UploadRequestPhoto]:
        photos: list[UploadRequestPhoto] = []
        async for photo in self.upload_request_photo_querier.list_upload_request_photos_by_upload_request_id(
            upload_request_id=upload_request_id
        ):
            photos.append(photo)
        return photos

    async def approve_request(
        self,
        *,
        request_id: uuid.UUID,
        approved_by: StaffUser,
    ) -> UploadRequestDetails:
        existing = await self.upload_request_querier.get_upload_request_by_id(id=request_id)
        if existing is None:
            raise AppException.not_found("Upload request not found")
        if self._status_value(existing.status) != "pending":
            raise AppException.bad_request("Upload request is not pending")

        staged_photos = await self.list_request_photos(request_id)
        if not staged_photos:
            raise AppException.bad_request("No staged photos found for this upload request")

        upload_request = await self.upload_request_querier.approve_upload_request(
            id=request_id,
            approved_by=approved_by.id,
        )
        if upload_request is None:
            raise AppException.internal_error("Failed to approve upload request")

        for staged_photo in staged_photos:
            created_photo = await self.photo_querier.create_photo(
                event_id=upload_request.event_id,
                storage_key=staged_photo.staging_storage_key,
                taken_at=staged_photo.taken_at,
                day_number=staged_photo.day_number,
                visibility=staged_photo.visibility,
            )
            if created_photo is None:
                raise AppException.internal_error("Failed to finalize staged photo")

        await self.upload_request_photo_querier.delete_upload_request_photos_by_upload_request_id(
            upload_request_id=request_id
        )

        await self.staff_notifications_service.create_notification(
            staff_user_id=upload_request.requested_by,
            type="upload_request_approved",
            payload={
                "upload_request_id": str(upload_request.id),
                "event_id": str(upload_request.event_id),
                "photo_count": upload_request.photo_count,
                "approved_by": str(approved_by.id),
                "status": "approved",
            },
        )
        return UploadRequestDetails(request=upload_request, photos=[])

    async def reject_request(
        self,
        *,
        request_id: uuid.UUID,
        approved_by: StaffUser,
        reason: str | None,
    ) -> UploadRequestDetails:
        existing = await self.upload_request_querier.get_upload_request_by_id(id=request_id)
        if existing is None:
            raise AppException.not_found("Upload request not found")
        if self._status_value(existing.status) != "pending":
            raise AppException.bad_request("Upload request is not pending")

        upload_request = await self.upload_request_querier.reject_upload_request(
            id=request_id,
            approved_by=approved_by.id,
            rejection_reason=reason,
        )
        if upload_request is None:
            raise AppException.internal_error("Failed to reject upload request")

        await self.upload_request_photo_querier.delete_upload_request_photos_by_upload_request_id(
            upload_request_id=request_id
        )

        await self.staff_notifications_service.create_notification(
            staff_user_id=upload_request.requested_by,
            type="upload_request_rejected",
            payload={
                "upload_request_id": str(upload_request.id),
                "event_id": str(upload_request.event_id),
                "photo_count": upload_request.photo_count,
                "approved_by": str(approved_by.id),
                "status": "rejected",
                "reason": reason,
            },
        )
        return UploadRequestDetails(request=upload_request, photos=[])
