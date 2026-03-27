# Code generated manually to match the sqlc async querier style used in the repo.
from typing import AsyncIterator, Optional
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

from . import models


CREATE_UPLOAD_REQUEST = """-- name: create_upload_request \\:one
INSERT INTO upload_requests (
    event_id,
    group_id,
    drive_file_id,
    requested_by,
    photo_count
) VALUES (
    :p1, :p2, :p3, :p4, :p5
)
RETURNING
    id,
    event_id,
    group_id,
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
    group_id,
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


LIST_UPLOAD_REQUESTS_BY_GROUP_ID = """-- name: list_upload_requests_by_group_id \\:many
SELECT
    id,
    event_id,
    group_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_requests
WHERE group_id = :p1
ORDER BY created_at ASC
"""


LIST_UPLOAD_REQUESTS = """-- name: list_upload_requests \\:many
SELECT
    id,
    event_id,
    group_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_requests
ORDER BY created_at DESC
"""


LIST_UPLOAD_REQUESTS_BY_STATUS = """-- name: list_upload_requests_by_status \\:many
SELECT
    id,
    event_id,
    group_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_requests
WHERE status = :p1
ORDER BY created_at DESC
"""


LIST_UPLOAD_REQUESTS_BY_REQUESTER_AND_STATUS = """-- name: list_upload_requests_by_requester_and_status \\:many
SELECT
    id,
    event_id,
    group_id,
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
  AND status = :p2
ORDER BY created_at DESC
"""


LIST_UPLOAD_REQUESTS_BY_REQUESTER = """-- name: list_upload_requests_by_requester \\:many
SELECT
    id,
    event_id,
    group_id,
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
    group_id,
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
    group_id,
    drive_file_id,
    requested_by,
    approved_by,
    status,
    photo_count,
    created_at,
    approved_at,
    rejection_reason
"""


DELETE_UPLOAD_REQUEST = """-- name: delete_upload_request \\:exec
DELETE FROM upload_requests
WHERE id = :p1
"""


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def create_upload_request(
        self,
        *,
        event_id: uuid.UUID,
        group_id: uuid.UUID | None,
        drive_file_id: str | None,
        requested_by: uuid.UUID,
        photo_count: int,
    ) -> Optional[models.UploadRequest]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(CREATE_UPLOAD_REQUEST),
                {
                    "p1": event_id,
                    "p2": group_id,
                    "p3": drive_file_id,
                    "p4": requested_by,
                    "p5": photo_count,
                },
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request(row)

    async def list_upload_requests_by_group_id(
        self,
        *,
        group_id: uuid.UUID,
    ) -> AsyncIterator[models.UploadRequest]:
        result = await self._conn.stream(
            sqlalchemy.text(LIST_UPLOAD_REQUESTS_BY_GROUP_ID),
            {"p1": group_id},
        )
        async for row in result:
            yield _row_to_upload_request(row)

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

    async def list_upload_requests(
        self,
        *,
        requested_by: uuid.UUID | None,
        status: str | None,
    ) -> AsyncIterator[models.UploadRequest]:
        if requested_by is None and status is None:
            statement = LIST_UPLOAD_REQUESTS
            params: dict[str, object] = {}
        elif requested_by is None:
            statement = LIST_UPLOAD_REQUESTS_BY_STATUS
            params = {"p1": status}
        elif status is None:
            statement = LIST_UPLOAD_REQUESTS_BY_REQUESTER
            params = {"p1": requested_by}
        else:
            statement = LIST_UPLOAD_REQUESTS_BY_REQUESTER_AND_STATUS
            params = {"p1": requested_by, "p2": status}
        result = await self._conn.stream(
            sqlalchemy.text(statement),
            params,
        )
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

    async def delete_upload_request(
        self,
        *,
        id: uuid.UUID,
    ) -> None:
        await self._conn.execute(
            sqlalchemy.text(DELETE_UPLOAD_REQUEST),
            {"p1": id},
        )


def _row_to_upload_request(row: sqlalchemy.Row[tuple[object, ...]]) -> models.UploadRequest:
    return models.UploadRequest(
        id=row[0],
        event_id=row[1],
        group_id=row[2],
        drive_file_id=row[3],
        requested_by=row[4],
        approved_by=row[5],
        status=row[6],
        photo_count=row[7],
        created_at=row[8],
        approved_at=row[9],
        rejection_reason=row[10],
    )
