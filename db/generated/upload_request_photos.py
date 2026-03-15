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
    staging_storage_key,
    taken_at,
    day_number,
    visibility
) VALUES (
    :p1, :p2, :p3, :p4, :p5, :p6
)
RETURNING
    id,
    upload_request_id,
    drive_file_id,
    staging_storage_key,
    taken_at,
    day_number,
    visibility,
    created_at
"""


LIST_UPLOAD_REQUEST_PHOTOS_BY_UPLOAD_REQUEST_ID = """-- name: list_upload_request_photos_by_upload_request_id \\:many
SELECT
    id,
    upload_request_id,
    drive_file_id,
    staging_storage_key,
    taken_at,
    day_number,
    visibility,
    created_at
FROM upload_request_photos
WHERE upload_request_id = :p1
ORDER BY created_at ASC
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
        staging_storage_key: str,
        taken_at: datetime.datetime | None,
        day_number: int | None,
        visibility: str,
    ) -> Optional[models.UploadRequestPhoto]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(CREATE_UPLOAD_REQUEST_PHOTO),
                {
                    "p1": upload_request_id,
                    "p2": drive_file_id,
                    "p3": staging_storage_key,
                    "p4": taken_at,
                    "p5": day_number,
                    "p6": visibility,
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
        staging_storage_key=row[3],
        taken_at=row[4],
        day_number=row[5],
        visibility=row[6],
        created_at=row[7],
    )
