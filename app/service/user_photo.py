from __future__ import annotations

from uuid import UUID

from app.core.exceptions import AppException
from app.core.logger import logger
from app.infra.google_drive import GoogleDriveClient
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME
from app.service.staff_drive import StaffDriveService
from db.generated import photos as photo_queries
from db.generated.models import Photo
from db.generated.photos import ListEventPhotosForUserParams, ListUserPhotosParams


class UserPhotoService:
    def __init__(
        self,
        *,
        photo_querier: photo_queries.AsyncQuerier,
        staff_drive_service: StaffDriveService,
    ) -> None:
        self._photo_querier = photo_querier
        self._staff_drive_service = staff_drive_service

    async def list_photos(
        self,
        *,
        user_id: UUID,
        event_id: UUID | None = None,
        sort: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Photo]:
        photos: list[Photo] = []
        async for photo in self._photo_querier.list_user_photos(
            ListUserPhotosParams(
                user_id=user_id,
                column_2=event_id,  # type: ignore[arg-type]
                column_3=sort,
                limit=limit,
                offset=offset,
            )
        ):
            photos.append(photo)
        return photos

    async def list_event_photos(
        self,
        *,
        user_id: UUID,
        event_id: UUID,
        sort: str = "desc",
        limit: int = 50,
        offset: int = 0,
    ) -> list[Photo]:
        photos: list[Photo] = []
        async for photo in self._photo_querier.list_event_photos_for_user(
            ListEventPhotosForUserParams(
                user_id=user_id,
                event_id=event_id,
                column_3=sort,
                limit=limit,
                offset=offset,
            )
        ):
            photos.append(photo)
        return photos

    async def get_photo_bytes(
        self,
        *,
        user_id: UUID,
        photo_id: UUID,
    ) -> tuple[bytes, str, str]:
        """Returns (image_bytes, filename, content_type).
        Tries MinIO first, falls back to Google Drive if cleaned up."""

        photo = await self._photo_querier.get_photo_by_id(id=photo_id)
        if photo is None:
            raise AppException.not_found("Photo not found")

        # Try bucket first
        try:
            bucket = Bucket(IMAGES_BUCKET_NAME, "")
            data, filename, content_type = await bucket.get(photo.storage_key)
            return data, filename, content_type
        except Exception:
            logger.info("Photo %s not in bucket, trying Drive fallback", photo_id)

        # Fallback: get drive_file_id from upload_request_photos
        drive_file_id = await self._photo_querier.get_drive_file_id_for_photo(
            final_storage_key=photo.storage_key,
        )
        if drive_file_id is None:
            raise AppException.not_found("Photo no longer available")

        # Get an access token from any active staff Drive connection
        access_token = await self._get_any_drive_token()

        download = await GoogleDriveClient.download_file(
            access_token=access_token,
            file_id=drive_file_id,
        )
        return download.content, download.metadata.name, download.metadata.mime_type

    async def _get_any_drive_token(self) -> str:
        """Get a valid Drive access token from the staff drive service.
        Uses the system/admin drive connection."""
        try:
            return await self._staff_drive_service.get_system_access_token()
        except Exception:
            raise AppException.internal_error(
                "No active Drive connection available to serve this photo"
            )
