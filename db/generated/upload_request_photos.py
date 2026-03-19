# Code generated manually to match the sqlc async querier style used in the repo.
from typing import AsyncIterator, Optional
import datetime
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

from . import models


CREATE_UPLOAD_REQUEST_PHOTO = """-- name: create_upload_request_photo \\:one
INSERT INTO upload_request_photos (
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    taken_at,
    day_number,
    visibility,
    status
) VALUES (
    :p1, :p2, :p3, :p4, :p5, :p6, :p7, :p8, :p9, :p10
)
RETURNING
    id,
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    final_storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    created_at
"""


LIST_UPLOAD_REQUEST_PHOTOS_BY_UPLOAD_REQUEST_ID = """-- name: list_upload_request_photos_by_upload_request_id \\:many
SELECT
    id,
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    final_storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    created_at
FROM upload_request_photos
WHERE upload_request_id = :p1
ORDER BY created_at ASC
"""


LIST_UPLOAD_REQUEST_PHOTOS_BY_UPLOAD_REQUEST_IDS = """-- name: list_upload_request_photos_by_upload_request_ids \\:many
SELECT
    id,
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    final_storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    created_at
FROM upload_request_photos
WHERE upload_request_id = ANY(:p1)
ORDER BY created_at ASC
"""


GET_UPLOAD_REQUEST_PHOTO_BY_ID = """-- name: get_upload_request_photo_by_id \\:one
SELECT
    id,
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    final_storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    created_at
FROM upload_request_photos
WHERE id = :p1
"""


UPDATE_UPLOAD_REQUEST_PHOTO_APPROVAL = """-- name: update_upload_request_photo_approval \\:one
UPDATE upload_request_photos
SET status = :p2,
    final_storage_key = :p3
WHERE id = :p1
RETURNING
    id,
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    final_storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    created_at
"""


UPDATE_UPLOAD_REQUEST_PHOTO_STATUS_BY_UPLOAD_REQUEST_ID = """-- name: update_upload_request_photo_status_by_upload_request_id \\:many
UPDATE upload_request_photos
SET status = :p2
WHERE upload_request_id = :p1
RETURNING
    id,
    upload_request_id,
    drive_file_id,
    file_name,
    mime_type,
    size_bytes,
    staging_storage_key,
    final_storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    created_at
"""


DELETE_UPLOAD_REQUEST_PHOTOS_BY_UPLOAD_REQUEST_ID = """-- name: delete_upload_request_photos_by_upload_request_id \\:exec
DELETE FROM upload_request_photos
WHERE upload_request_id = :p1
"""


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def create_upload_request_photo(
        self,
        *,
        upload_request_id: uuid.UUID,
        drive_file_id: str,
        file_name: str,
        mime_type: str,
        size_bytes: int,
        staging_storage_key: str,
        taken_at: datetime.datetime | None,
        day_number: int | None,
        visibility: str,
        status: str,
    ) -> Optional[models.UploadRequestPhoto]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(CREATE_UPLOAD_REQUEST_PHOTO),
                {
                    "p1": upload_request_id,
                    "p2": drive_file_id,
                    "p3": file_name,
                    "p4": mime_type,
                    "p5": size_bytes,
                    "p6": staging_storage_key,
                    "p7": taken_at,
                    "p8": day_number,
                    "p9": visibility,
                    "p10": status,
                },
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request_photo(row)

    async def list_upload_request_photos_by_upload_request_id(
        self,
        *,
        upload_request_id: uuid.UUID,
    ) -> AsyncIterator[models.UploadRequestPhoto]:
        result = await self._conn.stream(
            sqlalchemy.text(LIST_UPLOAD_REQUEST_PHOTOS_BY_UPLOAD_REQUEST_ID),
            {"p1": upload_request_id},
        )
        async for row in result:
            yield _row_to_upload_request_photo(row)

    async def list_upload_request_photos_by_upload_request_ids(
        self,
        *,
        upload_request_ids: list[uuid.UUID],
    ) -> AsyncIterator[models.UploadRequestPhoto]:
        statement = sqlalchemy.text(LIST_UPLOAD_REQUEST_PHOTOS_BY_UPLOAD_REQUEST_IDS).bindparams(
            sqlalchemy.bindparam("p1", type_=sqlalchemy.ARRAY(sqlalchemy.Uuid))
        )
        result = await self._conn.stream(statement, {"p1": upload_request_ids})
        async for row in result:
            yield _row_to_upload_request_photo(row)

    async def get_upload_request_photo_by_id(
        self,
        *,
        id: uuid.UUID,
    ) -> Optional[models.UploadRequestPhoto]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(GET_UPLOAD_REQUEST_PHOTO_BY_ID),
                {"p1": id},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request_photo(row)

    async def update_upload_request_photo_approval(
        self,
        *,
        id: uuid.UUID,
        status: str,
        final_storage_key: str | None,
    ) -> Optional[models.UploadRequestPhoto]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(UPDATE_UPLOAD_REQUEST_PHOTO_APPROVAL),
                {"p1": id, "p2": status, "p3": final_storage_key},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request_photo(row)

    async def update_upload_request_photo_status_by_upload_request_id(
        self,
        *,
        upload_request_id: uuid.UUID,
        status: str,
    ) -> AsyncIterator[models.UploadRequestPhoto]:
        result = await self._conn.stream(
            sqlalchemy.text(UPDATE_UPLOAD_REQUEST_PHOTO_STATUS_BY_UPLOAD_REQUEST_ID),
            {"p1": upload_request_id, "p2": status},
        )
        async for row in result:
            yield _row_to_upload_request_photo(row)

    async def delete_upload_request_photos_by_upload_request_id(
        self,
        *,
        upload_request_id: uuid.UUID,
    ) -> None:
        await self._conn.execute(
            sqlalchemy.text(DELETE_UPLOAD_REQUEST_PHOTOS_BY_UPLOAD_REQUEST_ID),
            {"p1": upload_request_id},
        )


def _row_to_upload_request_photo(
    row: sqlalchemy.Row[tuple[object, ...]],
) -> models.UploadRequestPhoto:
    return models.UploadRequestPhoto(
        id=row[0],
        upload_request_id=row[1],
        drive_file_id=row[2],
        file_name=row[3],
        mime_type=row[4],
        size_bytes=row[5],
        staging_storage_key=row[6],
        final_storage_key=row[7],
        taken_at=row[8],
        day_number=row[9],
        visibility=row[10],
        status=row[11],
        created_at=row[12],
    )
