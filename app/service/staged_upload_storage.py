from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import uuid

from app.core.exceptions import AppException
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME


@dataclass(frozen=True)
class StoredObject:
    storage_key: str
    content_type: str
    file_name: str


@dataclass(frozen=True)
class PreviewObject:
    data: bytes
    content_type: str
    file_name: str


class StagedUploadStorageService:
    def __init__(self) -> None:
        self.bucket = Bucket(IMAGES_BUCKET_NAME, "")

    @staticmethod
    def build_staging_key(
        *,
        upload_request_id: uuid.UUID,
        photo_id: uuid.UUID,
        file_name: str,
    ) -> str:
        extension = Path(file_name).suffix.lower()
        return f"staging/upload-requests/{upload_request_id}/{photo_id}{extension}"

    @staticmethod
    def build_final_key(
        *,
        event_id: uuid.UUID,
        photo_id: uuid.UUID,
        file_name: str,
    ) -> str:
        extension = Path(file_name).suffix.lower()
        return f"events/{event_id}/{photo_id}{extension}"

    async def store_staging_object(
        self,
        *,
        upload_request_id: uuid.UUID,
        photo_id: uuid.UUID,
        file_name: str,
        content_type: str,
        data: bytes,
    ) -> StoredObject:
        storage_key = self.build_staging_key(
            upload_request_id=upload_request_id,
            photo_id=photo_id,
            file_name=file_name,
        )
        await self.bucket.put_bytes(
            data=data,
            object_name=storage_key,
            content_type=content_type,
            filename=file_name,
        )
        return StoredObject(
            storage_key=storage_key,
            content_type=content_type,
            file_name=file_name,
        )

    async def promote_to_final(
        self,
        *,
        event_id: uuid.UUID,
        photo_id: uuid.UUID,
        file_name: str,
        staging_storage_key: str,
    ) -> str:
        final_key = self.build_final_key(
            event_id=event_id,
            photo_id=photo_id,
            file_name=file_name,
        )
        await self.bucket.copy(
            source_object_name=staging_storage_key,
            target_object_name=final_key,
        )
        return final_key

    async def delete_storage_key(self, storage_key: str) -> None:
        try:
            await self.bucket.delete(storage_key)
        except Exception as exc:
            raise AppException.storage_error("Failed to delete staged image from storage") from exc

    async def get_preview(self, storage_key: str) -> PreviewObject:
        data, file_name, content_type = await self.bucket.get(storage_key)
        return PreviewObject(data=data, file_name=file_name, content_type=content_type)
