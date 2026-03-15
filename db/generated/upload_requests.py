# Code generated manually to match the sqlc async querier style used in the repo.
from typing import AsyncIterator, Optional
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

from . import models


CREATE_UPLOAD_REQUEST = """-- name: create_upload_request \\:one
INSERT INTO upload_requests (
    event_id,
    drive_file_id,
    requested_by,
    photo_count
) VALUES (
    :p1, :p2, :p3, :p4
)
RETURNING
    id,
    event_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
"""


GET_UPLOAD_REQUEST_BY_ID = """-- name: get_upload_request_by_id \\:one
SELECT
    id,
    event_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_requests
WHERE id = :p1
"""


LIST_UPLOAD_REQUESTS_BY_REQUESTER = """-- name: list_upload_requests_by_requester \\:many
SELECT
    id,
    event_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_requests
WHERE requested_by = :p1
ORDER BY created_at DESC
"""


LIST_PENDING_UPLOAD_REQUESTS = """-- name: list_pending_upload_requests \\:many
SELECT
    id,
    event_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_requests
WHERE status = 'pending'
ORDER BY created_at ASC
"""


APPROVE_UPLOAD_REQUEST = """-- name: approve_upload_request \\:one
UPDATE upload_requests
SET status = 'approved',
    approved_by = :p2,
    approved_at = NOW(),
    rejection_reason = NULL
WHERE id = :p1
  AND status = 'pending'
RETURNING
    id,
    event_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
"""


REJECT_UPLOAD_REQUEST = """-- name: reject_upload_request \\:one
UPDATE upload_requests
SET status = 'rejected',
    approved_by = :p2,
    approved_at = NOW(),
    rejection_reason = :p3
WHERE id = :p1
  AND status = 'pending'
RETURNING
    id,
    event_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
"""


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def create_upload_request(
        self,
        *,
        event_id: uuid.UUID,
        drive_file_id: str | None,
        requested_by: uuid.UUID,
        photo_count: int,
    ) -> Optional[models.UploadRequest]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(CREATE_UPLOAD_REQUEST),
                {
                    "p1": event_id,
                    "p2": drive_file_id,
                    "p3": requested_by,
                    "p4": photo_count,
                },
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request(row)

    async def get_upload_request_by_id(
        self,
        *,
        id: uuid.UUID,
    ) -> Optional[models.UploadRequest]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(GET_UPLOAD_REQUEST_BY_ID),
                {"p1": id},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request(row)

    async def list_upload_requests_by_requester(
        self,
        *,
        requested_by: uuid.UUID,
    ) -> AsyncIterator[models.UploadRequest]:
        result = await self._conn.stream(
            sqlalchemy.text(LIST_UPLOAD_REQUESTS_BY_REQUESTER),
            {"p1": requested_by},
        )
        async for row in result:
            yield _row_to_upload_request(row)

    async def list_pending_upload_requests(self) -> AsyncIterator[models.UploadRequest]:
        result = await self._conn.stream(sqlalchemy.text(LIST_PENDING_UPLOAD_REQUESTS))
        async for row in result:
            yield _row_to_upload_request(row)

    async def approve_upload_request(
        self,
        *,
        id: uuid.UUID,
        approved_by: uuid.UUID,
    ) -> Optional[models.UploadRequest]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(APPROVE_UPLOAD_REQUEST),
                {"p1": id, "p2": approved_by},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request(row)

    async def reject_upload_request(
        self,
        *,
        id: uuid.UUID,
        approved_by: uuid.UUID,
        rejection_reason: str | None,
    ) -> Optional[models.UploadRequest]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(REJECT_UPLOAD_REQUEST),
                {"p1": id, "p2": approved_by, "p3": rejection_reason},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request(row)


def _row_to_upload_request(row: sqlalchemy.Row[tuple[object, ...]]) -> models.UploadRequest:
    return models.UploadRequest(
        id=row[0],
        event_id=row[1],
        drive_file_id=row[2],
        requested_by=row[3],
        approved_by=row[4],
        status=row[5],
        photo_count=row[6],
        created_at=row[7],
        approved_at=row[8],
        rejection_reason=row[9],
    )
