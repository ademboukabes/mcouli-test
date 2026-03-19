from collections.abc import Sequence
from dataclasses import dataclass
from collections import defaultdict
import json
from typing import Literal
import uuid

from app.core.exceptions import AppException
from app.core.logger import logger
from app.infra.google_drive import GoogleDriveClient, GoogleDriveFileDownload
from app.infra.nats import NatsClient, NatsSubjects
from sqlalchemy.exc import IntegrityError

from app.schema.dto.staff.uploads import UploadPhotoInput
from app.service.staged_upload_storage import PreviewObject, StagedUploadStorageService
from app.service.staff_drive import StaffDriveService
from app.service.staff_notifications import StaffNotificationsService
from db.generated import photos as photo_queries
from db.generated import upload_request_photos as upload_request_photo_queries
from db.generated import upload_requests as upload_request_queries
from db.generated.models import (
    StaffRole,
    StaffUser,
    UploadRequest,
    UploadRequestPhoto,
    UploadRequestStatus,
)


@dataclass
class UploadRequestDetails:
    request: UploadRequest
    photos: list[UploadRequestPhoto]


class UploadRequestsService:
    _allowed_mime_types = {"image/jpeg", "image/png", "image/webp"}
    _max_photo_size_bytes = 20 * 1024 * 1024

    def __init__(
        self,
        upload_request_querier: upload_request_queries.AsyncQuerier,
        upload_request_photo_querier: upload_request_photo_queries.AsyncQuerier,
        photo_querier: photo_queries.AsyncQuerier,
        staged_upload_storage: StagedUploadStorageService,
        staff_drive_service: StaffDriveService,
        staff_notifications_service: StaffNotificationsService,
    ):
        self.upload_request_querier = upload_request_querier
        self.upload_request_photo_querier = upload_request_photo_querier
        self.photo_querier = photo_querier
        self.staged_upload_storage = staged_upload_storage
        self.staff_drive_service = staff_drive_service
        self.staff_notifications_service = staff_notifications_service

    @staticmethod
    def _status_value(status: object) -> str:
        return getattr(status, "value", str(status))

    @staticmethod
    def _role_value(role: object) -> str:
        return getattr(role, "value", str(role))

    @staticmethod
    def _raise_integrity_error(exc: IntegrityError) -> None:
        orig = getattr(exc, "orig", None)
        sqlstate = getattr(orig, "sqlstate", None)

        if sqlstate == "23503":
            raise AppException.bad_request("Invalid event reference") from exc
        if sqlstate == "23505":
            raise AppException.conflict("Duplicate photo in upload request batch") from exc

        raise AppException.internal_error("Failed to persist upload request") from exc

    def _validate_downloaded_photo(self, downloaded_photo: GoogleDriveFileDownload) -> None:
        metadata = downloaded_photo.metadata
        if metadata.mime_type not in self._allowed_mime_types:
            raise AppException.image_format_error("Unsupported image format from Google Drive")
        if metadata.size_bytes <= 0 or metadata.size_bytes > self._max_photo_size_bytes:
            raise AppException.bad_request("Google Drive image exceeds maximum allowed size")

    @staticmethod
    def _validate_create_request_inputs(photos: Sequence[UploadPhotoInput]) -> None:
        if not photos:
            raise AppException.bad_request("At least one photo is required")
        if len(photos) > 20:
            raise AppException.bad_request("A batch can contain at most 20 photos")

        drive_file_ids = [photo.drive_file_id for photo in photos]
        if len(drive_file_ids) != len(set(drive_file_ids)):
            raise AppException.conflict("Duplicate drive_file_id found in upload request batch")

    async def _cleanup_created_photos(self, created_photos: Sequence[UploadRequestPhoto]) -> None:
        for created_photo in created_photos:
            try:
                await self.staged_upload_storage.delete_storage_key(created_photo.staging_storage_key)
            except Exception:
                logger.warning(
                    "Failed to clean staged object %s after create failure",
                    created_photo.staging_storage_key,
                )

    async def _cleanup_finalized_objects(self, storage_keys: Sequence[str]) -> None:
        for storage_key in storage_keys:
            try:
                await self.staged_upload_storage.delete_storage_key(storage_key)
            except Exception:
                logger.warning(
                    "Failed to clean finalized object %s after approval failure",
                    storage_key,
                )

    async def _delete_staging_objects_best_effort(
        self,
        staged_photos: Sequence[UploadRequestPhoto],
    ) -> None:
        for staged_photo in staged_photos:
            try:
                await self.staged_upload_storage.delete_storage_key(staged_photo.staging_storage_key)
            except Exception as exc:
                logger.warning(
                    "Failed to delete staging object %s: %s",
                    staged_photo.staging_storage_key,
                    exc,
                )

    async def _list_request_photos_by_request_ids(
        self,
        request_ids: Sequence[uuid.UUID],
    ) -> dict[uuid.UUID, list[UploadRequestPhoto]]:
        photos_by_request_id: dict[uuid.UUID, list[UploadRequestPhoto]] = defaultdict(list)
        if not request_ids:
            return photos_by_request_id

        async for photo in self.upload_request_photo_querier.list_upload_request_photos_by_upload_request_i_ds(
            dollar_1=list(request_ids)
        ):
            photos_by_request_id[photo.upload_request_id].append(photo)

        return photos_by_request_id

    async def _create_staged_photo(
        self,
        *,
        upload_request_id: uuid.UUID,
        photo: UploadPhotoInput,
        access_token: str,
    ) -> UploadRequestPhoto:
        downloaded_photo = await GoogleDriveClient.download_file(
            access_token=access_token,
            file_id=photo.drive_file_id,
        )
        self._validate_downloaded_photo(downloaded_photo)

        stored_object = await self.staged_upload_storage.store_staging_object(
            upload_request_id=upload_request_id,
            photo_id=uuid.uuid4(),
            file_name=downloaded_photo.metadata.name,
            content_type=downloaded_photo.metadata.mime_type,
            data=downloaded_photo.content,
        )

        try:
            created_photo = await self.upload_request_photo_querier.create_upload_request_photo(
                arg=upload_request_photo_queries.CreateUploadRequestPhotoParams(
                upload_request_id=upload_request_id,
                drive_file_id=photo.drive_file_id,
                file_name=downloaded_photo.metadata.name,
                mime_type=downloaded_photo.metadata.mime_type,
                size_bytes=downloaded_photo.metadata.size_bytes,
                staging_storage_key=stored_object.storage_key,
                taken_at=photo.taken_at,
                day_number=photo.day_number,
                visibility=photo.visibility,
                status="staged",
                )     
            )
        except IntegrityError:
            try:
                await self.staged_upload_storage.delete_storage_key(stored_object.storage_key)
            except Exception:
                logger.warning(
                    "Failed to clean staged object %s after photo insert conflict",
                    stored_object.storage_key,
                )
            raise

        if created_photo is None:
            try:
                await self.staged_upload_storage.delete_storage_key(stored_object.storage_key)
            except Exception:
                logger.warning(
                    "Failed to clean staged object %s after empty photo insert result",
                    stored_object.storage_key,
                )
            raise AppException.internal_error("Failed to create staged upload photo")

        return created_photo

    def _ensure_request_access(
        self,
        *,
        current_staff_user: StaffUser,
        upload_request: UploadRequest,
    ) -> None:
        if upload_request.requested_by == current_staff_user.id:
            return
        if self._role_value(current_staff_user.role) == StaffRole.MULTI_TEAM_LEAD.value:
            return
        raise AppException.forbidden("You are not allowed to access this upload request")

    async def _publish_event(
        self,
        *,
        subject: NatsSubjects,
        payload: dict[str, object],
    ) -> None:
        try:
            await NatsClient.publish(subject, json.dumps(payload).encode("utf-8"))
        except Exception as exc:
            logger.warning("Failed to publish upload request event %s: %s", subject.value, exc)

    async def get_request_details(
        self,
        *,
        request_id: uuid.UUID,
        current_staff_user: StaffUser,
    ) -> UploadRequestDetails:
        upload_request = await self.upload_request_querier.get_upload_request_by_id(id=request_id)
        if upload_request is None:
            raise AppException.not_found("Upload request not found")
        self._ensure_request_access(
            current_staff_user=current_staff_user,
            upload_request=upload_request,
        )
        return UploadRequestDetails(
            request=upload_request,
            photos=await self.list_request_photos(upload_request.id),
        )

    async def get_request_photo_preview(
        self,
        *,
        request_id: uuid.UUID,
        photo_id: uuid.UUID,
        current_staff_user: StaffUser,
    ) -> PreviewObject:
        upload_request = await self.upload_request_querier.get_upload_request_by_id(id=request_id)
        if upload_request is None:
            raise AppException.not_found("Upload request not found")
        self._ensure_request_access(
            current_staff_user=current_staff_user,
            upload_request=upload_request,
        )
        photo = await self.upload_request_photo_querier.get_upload_request_photo_by_id(id=photo_id)
        if photo is None or photo.upload_request_id != request_id:
            raise AppException.not_found("Upload request photo not found")
        storage_key = photo.final_storage_key or photo.staging_storage_key
        return await self.staged_upload_storage.get_preview(storage_key)

    async def create_request(
        self,
        *,
        event_id: uuid.UUID,
        photos: Sequence[UploadPhotoInput],
        requested_by: StaffUser,
    ) -> UploadRequestDetails:
        self._validate_create_request_inputs(photos)

        access_token = await self.staff_drive_service.get_access_token_for_staff_user(
            requested_by.id
        )
        upload_request: UploadRequest | None = None


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
                created_photos.append(
                    await self._create_staged_photo(
                        upload_request_id=upload_request.id,
                        photo=photo,
                        access_token=access_token,
                    )
                )
        except IntegrityError as exc:
            await self._cleanup_created_photos(created_photos)
            self._raise_integrity_error(exc)
        except Exception:
            await self._cleanup_created_photos(created_photos)
            raise

        await self._publish_event(
            subject=NatsSubjects.STAFF_UPLOAD_REQUEST_CREATED,
            payload={
                "upload_request_id": str(upload_request.id),
                "event_id": str(upload_request.event_id),
                "requested_by": str(requested_by.id),
                "photo_count": upload_request.photo_count,
            },
        )

        return UploadRequestDetails(request=upload_request, photos=created_photos)

    async def list_requests(
        self,
        *,
        current_staff_user: StaffUser,
        scope: Literal["my", "all"],
        status: UploadRequestStatus | None,
    ) -> list[UploadRequestDetails]:
        if scope == "all" and self._role_value(current_staff_user.role) != StaffRole.MULTI_TEAM_LEAD.value:
            raise AppException.forbidden("Multi team lead access required")

        requested_by = current_staff_user.id if scope == "my" else None
        if requested_by is None:
            logger.info("hello")
            raise AppException.not_found("not requests")
        else :
            request_rows: list[UploadRequest] = []
            async for upload_request in self.upload_request_querier.list_upload_requests(
                dollar_1=requested_by,
                p2=status,
            ):
                request_rows.append(upload_request)

            photos_by_request_id = await self._list_request_photos_by_request_ids(
                [upload_request.id for upload_request in request_rows]
            )

            requests: list[UploadRequestDetails] = []
            for upload_request in request_rows:
                requests.append(
                    UploadRequestDetails(
                        request=upload_request,
                        photos=photos_by_request_id.get(upload_request.id, []),
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

        finalized_storage_keys: list[str] = []
        try:
            for staged_photo in staged_photos:
                final_storage_key = await self.staged_upload_storage.promote_to_final(
                    event_id=existing.event_id,
                    photo_id=staged_photo.id,
                    file_name=staged_photo.file_name,
                    staging_storage_key=staged_photo.staging_storage_key,
                )
                finalized_storage_keys.append(final_storage_key)
                created_photo = await self.photo_querier.create_photo(
                    arg=photo_queries.CreatePhotoParams(
                    event_id=existing.event_id,
                    storage_key=final_storage_key,
                    taken_at=staged_photo.taken_at,
                    day_number=staged_photo.day_number,
                    visibility=staged_photo.visibility,
                    )
                    
                )
                if created_photo is None:
                    raise AppException.internal_error("Failed to finalize staged photo")
                updated_photo = await self.upload_request_photo_querier.update_upload_request_photo_approval(
                    id=staged_photo.id,
                    status="approved",
                    final_storage_key=final_storage_key,
                )
                if updated_photo is None:
                    raise AppException.internal_error("Failed to update staged photo approval state")

            upload_request = await self.upload_request_querier.approve_upload_request(
                id=request_id,
                approved_by=approved_by.id,
            )
            if upload_request is None:
                raise AppException.internal_error("Failed to approve upload request")
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
        except Exception:
            await self._cleanup_finalized_objects(finalized_storage_keys)
            raise

        await self._delete_staging_objects_best_effort(staged_photos)
        await self._publish_event(
            subject=NatsSubjects.STAFF_UPLOAD_REQUEST_APPROVED,
            payload={
                "upload_request_id": str(upload_request.id),
                "event_id": str(upload_request.event_id),
                "approved_by": str(approved_by.id),
                "photo_count": upload_request.photo_count,
            },
        )
        return UploadRequestDetails(
            request=upload_request,
            photos=await self.list_request_photos(request_id),
        )

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

        staged_photos = await self.list_request_photos(request_id)
        rejected_photos: list[UploadRequestPhoto] = []
        async for staged_photo in self.upload_request_photo_querier.update_upload_request_photo_status_by_upload_request_id(
            upload_request_id=request_id,
            status="rejected",
        ):
            rejected_photos.append(staged_photo)

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
        await self._publish_event(
            subject=NatsSubjects.STAFF_UPLOAD_REQUEST_REJECTED,
            payload={
                "upload_request_id": str(upload_request.id),
                "event_id": str(upload_request.event_id),
                "approved_by": str(approved_by.id),
                "photo_count": upload_request.photo_count,
                "reason": reason,
            },
        )
        await self._delete_staging_objects_best_effort(staged_photos)
        return UploadRequestDetails(request=upload_request, photos=rejected_photos)
