from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
import json
from typing import Literal
import uuid

from sqlalchemy.exc import IntegrityError

from app.schema.internal.uploads import UploadPhotoInput
from app.core.constant import AuditEventType
from app.core.exceptions import AppException
from app.core.logger import logger
from app.infra.google_drive import (
    GoogleDriveClient,
    GoogleDriveFileDownload,
    GoogleDriveFileMetadata,
)
from app.infra.nats import NatsClient, NatsSubjects
from app.schema.request.staff.uploads import UploadPhotoInput
from app.service.audit import AuditService
from app.service.staged_upload_storage import PreviewObject, StagedUploadStorageService
from app.service.staff_drive import StaffDriveService
from app.service.staff_notifications import StaffNotificationsService
from db.generated import photos as photo_queries
from db.generated import upload_request_groups as upload_request_group_queries
from db.generated import upload_request_photos as upload_request_photo_queries
from db.generated import upload_requests as upload_request_queries
from db.generated.models import (
    Photo,
    StaffRole,
    StaffUser,
    UploadRequest,
    UploadRequestGroup,
    UploadRequestPhoto,
)


@dataclass
class UploadRequestDetails:
    request: UploadRequest
    photos: list[UploadRequestPhoto]


@dataclass
class UploadRequestGroupDetails:
    group: UploadRequestGroup
    requests: list[UploadRequestDetails]


class UploadRequestsService:
    _allowed_mime_types = {"image/jpeg", "image/png", "image/webp"}
    _max_photo_size_bytes = 20 * 1024 * 1024
    _max_request_batch_size = 20

    def __init__(
        self,
        upload_request_group_querier: upload_request_group_queries.AsyncQuerier,
        upload_request_querier: upload_request_queries.AsyncQuerier,
        upload_request_photo_querier: upload_request_photo_queries.AsyncQuerier,
        photo_querier: photo_queries.AsyncQuerier,
        staged_upload_storage: StagedUploadStorageService,
        staff_drive_service: StaffDriveService,
        staff_notifications_service: StaffNotificationsService,
        audit_service: AuditService | None = None,
    ):
        self.upload_request_group_querier = upload_request_group_querier
        self.upload_request_querier = upload_request_querier
        self.upload_request_photo_querier = upload_request_photo_querier
        self.photo_querier = photo_querier
        self.staged_upload_storage = staged_upload_storage
        self.staff_drive_service = staff_drive_service
        self.staff_notifications_service = staff_notifications_service
        self.audit_service = audit_service

    @staticmethod
    def _status_value(status: object) -> str:
        return getattr(status, "value", str(status))

    @staticmethod
    def _role_value(role: object) -> str:
        return getattr(role, "value", str(role))

    @staticmethod
    def _chunk_photo_inputs(
        photos: Sequence[UploadPhotoInput],
        chunk_size: int,
    ) -> list[list[UploadPhotoInput]]:
        return [
            list(photos[index : index + chunk_size])
            for index in range(0, len(photos), chunk_size)
        ]

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

    def _is_supported_image(self, metadata: GoogleDriveFileMetadata) -> bool:
        return metadata.mime_type in self._allowed_mime_types and metadata.size_bytes > 0

    @staticmethod
    def _validate_create_request_inputs(photos: Sequence[UploadPhotoInput]) -> None:
        if not photos:
            raise AppException.bad_request("At least one photo is required")
        if len(photos) > UploadRequestsService._max_request_batch_size:
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

    async def _cleanup_created_group(
        self,
        *,
        upload_group_id: uuid.UUID,
        created_requests: Sequence[UploadRequestDetails],
    ) -> None:
        for request_details in reversed(created_requests):
            try:
                await self.upload_request_querier.delete_upload_request(id=request_details.request.id)
            except Exception as exc:
                logger.warning(
                    "Failed to delete upload request %s during group cleanup: %s",
                    request_details.request.id,
                    exc,
                )

        try:
            await self.upload_request_group_querier.delete_upload_request_group(id=upload_group_id)
        except Exception as exc:
            logger.warning(
                "Failed to delete upload request group %s during cleanup: %s",
                upload_group_id,
                exc,
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

        async for photo in self.upload_request_photo_querier.list_upload_request_photos_by_upload_request_ids(
            upload_request_ids=list(request_ids)
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

    async def _create_request_with_access_token(
        self,
        *,
        event_id: uuid.UUID,
        photos: Sequence[UploadPhotoInput],
        requested_by: StaffUser,
        access_token: str,
        group_id: uuid.UUID | None = None,
        publish_event: bool = True,
    ) -> UploadRequestDetails:
        self._validate_create_request_inputs(photos)
        upload_request = None
        try:
            upload_request = await self.upload_request_querier.create_upload_request(
                event_id=event_id,
                group_id=group_id,
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

        if publish_event:
            await self._publish_event(
                subject=NatsSubjects.STAFF_UPLOAD_REQUEST_CREATED,
                payload={
                    "upload_request_id": str(upload_request.id),
                    "event_id": str(upload_request.event_id),
                    "requested_by": str(requested_by.id),
                    "photo_count": upload_request.photo_count,
                    "group_id": str(group_id) if group_id is not None else None,
                },
            )

        return UploadRequestDetails(request=upload_request, photos=created_photos)

    async def _approve_request_without_side_effects(
        self,
        *,
        request_id: uuid.UUID,
        approved_by: StaffUser,
    ) -> tuple[UploadRequest, list[UploadRequestPhoto], list[str], list[Photo]]:
        existing = await self.upload_request_querier.get_upload_request_by_id(id=request_id)
        if existing is None:
            raise AppException.not_found("Upload request not found")
        if self._status_value(existing.status) != "pending":
            raise AppException.bad_request("Upload request is not pending")

        staged_photos = await self.list_request_photos(request_id)
        if not staged_photos:
            raise AppException.bad_request("No staged photos found for this upload request")

        finalized_storage_keys: list[str] = []
        created_photos: list[Photo] = []
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
                    photo_queries.CreatePhotoParams(
                        event_id=existing.event_id,
                        storage_key=final_storage_key,
                        taken_at=staged_photo.taken_at,
                        day_number=staged_photo.day_number,
                        visibility=staged_photo.visibility,
                    )
                )
                if created_photo is None:
                    raise AppException.internal_error("Failed to finalize staged photo")
                created_photos.append(created_photo)
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
        except Exception:
            await self._cleanup_finalized_objects(finalized_storage_keys)
            raise

        return upload_request, staged_photos, finalized_storage_keys, created_photos

    async def _reject_request_without_side_effects(
        self,
        *,
        request_id: uuid.UUID,
        approved_by: StaffUser,
        reason: str | None,
    ) -> tuple[UploadRequest, list[UploadRequestPhoto], list[UploadRequestPhoto]]:
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

        return upload_request, rejected_photos, staged_photos

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

    def _ensure_group_access(
        self,
        *,
        current_staff_user: StaffUser,
        upload_group: UploadRequestGroup,
    ) -> None:
        if upload_group.requested_by == current_staff_user.id:
            return
        if self._role_value(current_staff_user.role) == StaffRole.MULTI_TEAM_LEAD.value:
            return
        raise AppException.forbidden("You are not allowed to access this upload request group")

    def _ensure_group_is_pending(
        self,
        group: UploadRequestGroup,
    ) -> None:
        if self._status_value(group.status) != "pending":
            raise AppException.bad_request("Upload request group is not pending")

    def _ensure_all_requests_are_pending(
        self,
        requests: Sequence[UploadRequestDetails],
    ) -> None:
        if not requests:
            raise AppException.bad_request("No upload requests found for this group")

        for request_details in requests:
            if self._status_value(request_details.request.status) != "pending":
                raise AppException.bad_request(
                    "Upload request group contains non-pending requests"
                )

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

    async def _audit(self, event_type: AuditEventType, **metadata: object) -> None:
        if self.audit_service is not None:
            await self.audit_service.create_record(
                event_type=event_type,
                metadata={k: str(v) for k, v in metadata.items()},
            )

    async def _publish_photo_process_events(self, photos: list[Photo]) -> None:
        for photo in photos:
            await self._publish_event(
                subject=NatsSubjects.PHOTO_PROCESS,
                payload={
                    "photo_id": str(photo.id),
                    "image_ref": photo.storage_key,
                    "event_id": str(photo.event_id),
                },
            )
        if photos:
            logger.info("Published %d photo process events", len(photos))

    async def create_upload(
        self,
        *,
        event_id: uuid.UUID,
        folder_id: str | None,
        photos: Sequence[UploadPhotoInput],
        visibility: str,
        day_number: int | None,
        requested_by: StaffUser,
    ) -> UploadRequestDetails | UploadRequestGroupDetails:
        if folder_id is not None:
            return await self.create_group_from_folder(
                event_id=event_id,
                folder_id=folder_id,
                visibility=visibility,
                day_number=day_number,
                requested_by=requested_by,
            )
        return await self.create_request(
            event_id=event_id,
            photos=photos,
            requested_by=requested_by,
        )

    async def create_request(
        self,
        *,
        event_id: uuid.UUID,
        photos: Sequence[UploadPhotoInput],
        requested_by: StaffUser,
    ) -> UploadRequestDetails:
        access_token = await self.staff_drive_service.get_access_token_for_staff_user(
            requested_by.id
        )
        return await self._create_request_with_access_token(
            event_id=event_id,
            photos=photos,
            requested_by=requested_by,
            access_token=access_token,
        )

    async def create_group_from_folder(
        self,
        *,
        event_id: uuid.UUID,
        folder_id: str,
        visibility: str,
        day_number: int | None,
        requested_by: StaffUser,
    ) -> UploadRequestGroupDetails:
        upload_group = None
        access_token = await self.staff_drive_service.get_access_token_for_staff_user(
            requested_by.id
        )
        folder_files = await GoogleDriveClient.list_folder_files(
            access_token=access_token,
            folder_id=folder_id,
        )
        folder_files = sorted(folder_files, key=lambda file: (file.name.lower(), file.id))
        photo_inputs = [
            UploadPhotoInput(
                drive_file_id=file.id,
                taken_at=None,
                day_number=day_number,
                visibility=visibility,
            )
            for file in folder_files
            if self._is_supported_image(file)
        ]
        if not photo_inputs:
            raise AppException.bad_request(
                "Selected Google Drive folder does not contain valid images"
            )

        photo_batches = self._chunk_photo_inputs(photo_inputs, self._max_request_batch_size)
        try:
            upload_group = await self.upload_request_group_querier.create_upload_request_group(
                event_id=event_id,
                folder_id=folder_id,
                requested_by=requested_by.id,
                total_photo_count=len(photo_inputs),
                batch_count=len(photo_batches),
            )
        except IntegrityError as exc:
            self._raise_integrity_error(exc)
        if upload_group is None:
            raise AppException.internal_error("Failed to create upload request group")

        created_requests: list[UploadRequestDetails] = []
        try:
            for batch in photo_batches:
                created_requests.append(
                    await self._create_request_with_access_token(
                        event_id=event_id,
                        photos=batch,
                        requested_by=requested_by,
                        access_token=access_token,
                        group_id=upload_group.id,
                        publish_event=False,
                    )
                )
        except Exception:
            created_photos = [
                photo
                for request_details in created_requests
                for photo in request_details.photos
            ]
            await self._cleanup_created_photos(created_photos)
            await self._cleanup_created_group(
                upload_group_id=upload_group.id,
                created_requests=created_requests,
            )
            raise

        for request_details in created_requests:
            await self._publish_event(
                subject=NatsSubjects.STAFF_UPLOAD_REQUEST_CREATED,
                payload={
                    "upload_request_id": str(request_details.request.id),
                    "event_id": str(request_details.request.event_id),
                    "requested_by": str(requested_by.id),
                    "photo_count": request_details.request.photo_count,
                    "group_id": str(upload_group.id),
                },
            )

        await self._publish_event(
            subject=NatsSubjects.STAFF_UPLOAD_GROUP_CREATED,
            payload={
                "group_id": str(upload_group.id),
                "event_id": str(upload_group.event_id),
                "requested_by": str(requested_by.id),
                "total_photo_count": upload_group.total_photo_count,
                "batch_count": upload_group.batch_count,
            },
        )
        return UploadRequestGroupDetails(group=upload_group, requests=created_requests)

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
        request_rows: list[UploadRequest] = []
        async for upload_request in self.upload_request_querier.list_upload_requests(
            requested_by=requested_by,
            status=status,
        ):
            request_rows.append(upload_request)

        photos_by_request_id = await self._list_request_photos_by_request_ids(
            [upload_request.id for upload_request in request_rows]
        )
        return [
            UploadRequestDetails(
                request=upload_request,
                photos=photos_by_request_id.get(upload_request.id, []),
            )
            for upload_request in request_rows
        ]

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

    async def get_group_details(
        self,
        *,
        group_id: uuid.UUID,
        current_staff_user: StaffUser,
    ) -> UploadRequestGroupDetails:
        group = await self.upload_request_group_querier.get_upload_request_group_by_id(id=group_id)
        if group is None:
            raise AppException.not_found("Upload request group not found")
        self._ensure_group_access(
            current_staff_user=current_staff_user,
            upload_group=group,
        )

        requests: list[UploadRequest] = []
        async for upload_request in self.upload_request_querier.list_upload_requests_by_group_id(
            group_id=group_id
        ):
            requests.append(upload_request)

        photos_by_request_id = await self._list_request_photos_by_request_ids(
            [upload_request.id for upload_request in requests]
        )
        return UploadRequestGroupDetails(
            group=group,
            requests=[
                UploadRequestDetails(
                    request=upload_request,
                    photos=photos_by_request_id.get(upload_request.id, []),
                )
                for upload_request in requests
            ],
        )

    async def list_groups(
        self,
        *,
        current_staff_user: StaffUser,
        scope: Literal["my", "all"],
        status: str | None,
    ) -> list[UploadRequestGroupDetails]:
        if scope == "all" and self._role_value(current_staff_user.role) != StaffRole.MULTI_TEAM_LEAD.value:
            raise AppException.forbidden("Multi team lead access required")

        requested_by = current_staff_user.id if scope == "my" else None
        groups: list[UploadRequestGroup] = []
        async for group in self.upload_request_group_querier.list_upload_request_groups(
            requested_by=requested_by,
            status=status,
        ):
            groups.append(group)

        details: list[UploadRequestGroupDetails] = []
        for group in groups:
            details.append(
                await self.get_group_details(
                    group_id=group.id,
                    current_staff_user=current_staff_user,
                )
            )
        return details

    async def list_group_photos(
        self,
        *,
        group_id: uuid.UUID,
        current_staff_user: StaffUser,
    ) -> list[UploadRequestPhoto]:
        group_details = await self.get_group_details(
            group_id=group_id,
            current_staff_user=current_staff_user,
        )
        return [
            photo
            for request_details in group_details.requests
            for photo in request_details.photos
        ]

    async def approve_request(
        self,
        *,
        request_id: uuid.UUID,
        approved_by: StaffUser,
    ) -> UploadRequestDetails:
        upload_request, staged_photos, finalized_storage_keys, created_photos = (
            await self._approve_request_without_side_effects(
                request_id=request_id,
                approved_by=approved_by,
            )
        )
        try:
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
            await self._publish_photo_process_events(created_photos)
            await self._audit(
                AuditEventType.UPLOAD_REQUEST_APPROVED,
                request_id=upload_request.id,
                approved_by=approved_by.id,
            )
        except Exception:
            await self._cleanup_finalized_objects(finalized_storage_keys)
            raise

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
        upload_request, rejected_photos, staged_photos = (
            await self._reject_request_without_side_effects(
                request_id=request_id,
                approved_by=approved_by,
                reason=reason,
            )
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
        await self._audit(
            AuditEventType.UPLOAD_REQUEST_REJECTED,
            request_id=upload_request.id,
            approved_by=approved_by.id,
            reason=reason or "",
        )
        return UploadRequestDetails(request=upload_request, photos=rejected_photos)

    async def approve_group(
        self,
        *,
        group_id: uuid.UUID,
        approved_by: StaffUser,
    ) -> UploadRequestGroupDetails:
        group_details = await self.get_group_details(
            group_id=group_id,
            current_staff_user=approved_by,
        )
        self._ensure_group_is_pending(group_details.group)
        pending_requests = group_details.requests
        self._ensure_all_requests_are_pending(pending_requests)

        approved_requests: list[UploadRequest] = []
        all_staged_photos: list[UploadRequestPhoto] = []
        all_created_photos: list[Photo] = []
        finalized_storage_keys: list[str] = []
        try:
            for request_details in pending_requests:
                approved_request, staged_photos, request_storage_keys, created_photos = (
                    await self._approve_request_without_side_effects(
                        request_id=request_details.request.id,
                        approved_by=approved_by,
                    )
                )
                approved_requests.append(approved_request)
                all_staged_photos.extend(staged_photos)
                all_created_photos.extend(created_photos)
                finalized_storage_keys.extend(request_storage_keys)

            upload_group = await self.upload_request_group_querier.approve_upload_request_group(
                id=group_id,
                approved_by=approved_by.id,
            )
            if upload_group is None:
                raise AppException.internal_error("Failed to approve upload request group")

            for approved_request in approved_requests:
                await self.staff_notifications_service.create_notification(
                    staff_user_id=approved_request.requested_by,
                    type="upload_request_approved",
                    payload={
                        "upload_request_id": str(approved_request.id),
                        "event_id": str(approved_request.event_id),
                        "photo_count": approved_request.photo_count,
                        "approved_by": str(approved_by.id),
                        "status": "approved",
                    },
                )
                await self._publish_event(
                    subject=NatsSubjects.STAFF_UPLOAD_REQUEST_APPROVED,
                    payload={
                        "upload_request_id": str(approved_request.id),
                        "event_id": str(approved_request.event_id),
                        "approved_by": str(approved_by.id),
                        "photo_count": approved_request.photo_count,
                    },
                )

            await self._delete_staging_objects_best_effort(all_staged_photos)
            await self._publish_event(
                subject=NatsSubjects.STAFF_UPLOAD_GROUP_APPROVED,
                payload={
                    "group_id": str(upload_group.id),
                    "event_id": str(upload_group.event_id),
                    "approved_by": str(approved_by.id),
                    "total_photo_count": upload_group.total_photo_count,
                    "batch_count": upload_group.batch_count,
                },
            )
            await self._publish_photo_process_events(all_created_photos)
            await self._audit(
                AuditEventType.UPLOAD_REQUEST_APPROVED,
                group_id=upload_group.id,
                approved_by=approved_by.id,
            )
        except Exception:
            await self._cleanup_finalized_objects(finalized_storage_keys)
            raise

        return await self.get_group_details(
            group_id=group_id,
            current_staff_user=approved_by,
        )

    async def reject_group(
        self,
        *,
        group_id: uuid.UUID,
        approved_by: StaffUser,
        reason: str | None,
    ) -> UploadRequestGroupDetails:
        group_details = await self.get_group_details(
            group_id=group_id,
            current_staff_user=approved_by,
        )
        self._ensure_group_is_pending(group_details.group)
        pending_requests = group_details.requests
        self._ensure_all_requests_are_pending(pending_requests)

        rejected_requests: list[UploadRequest] = []
        all_staged_photos: list[UploadRequestPhoto] = []
        for request_details in pending_requests:
            rejected_request, _rejected_photos, staged_photos = (
                await self._reject_request_without_side_effects(
                    request_id=request_details.request.id,
                    approved_by=approved_by,
                    reason=reason,
                )
            )
            rejected_requests.append(rejected_request)
            all_staged_photos.extend(staged_photos)

        upload_group = await self.upload_request_group_querier.reject_upload_request_group(
            id=group_id,
            approved_by=approved_by.id,
            rejection_reason=reason,
        )
        if upload_group is None:
            raise AppException.internal_error("Failed to reject upload request group")

        for rejected_request in rejected_requests:
            await self.staff_notifications_service.create_notification(
                staff_user_id=rejected_request.requested_by,
                type="upload_request_rejected",
                payload={
                    "upload_request_id": str(rejected_request.id),
                    "event_id": str(rejected_request.event_id),
                    "photo_count": rejected_request.photo_count,
                    "approved_by": str(approved_by.id),
                    "status": "rejected",
                    "reason": reason,
                },
            )
            await self._publish_event(
                subject=NatsSubjects.STAFF_UPLOAD_REQUEST_REJECTED,
                payload={
                    "upload_request_id": str(rejected_request.id),
                    "event_id": str(rejected_request.event_id),
                    "approved_by": str(approved_by.id),
                    "photo_count": rejected_request.photo_count,
                    "reason": reason,
                },
            )

        await self._delete_staging_objects_best_effort(all_staged_photos)
        await self._publish_event(
            subject=NatsSubjects.STAFF_UPLOAD_GROUP_REJECTED,
            payload={
                "group_id": str(upload_group.id),
                "event_id": str(upload_group.event_id),
                "approved_by": str(approved_by.id),
                "total_photo_count": upload_group.total_photo_count,
                "batch_count": upload_group.batch_count,
                "reason": reason,
            },
        )
        return await self.get_group_details(
            group_id=group_id,
            current_staff_user=approved_by,
        )
