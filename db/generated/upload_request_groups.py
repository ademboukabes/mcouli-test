# Code generated manually to match the sqlc async querier style used in the repo.
from typing import AsyncIterator, Optional
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

from . import models


CREATE_UPLOAD_REQUEST_GROUP = """-- name: create_upload_request_group \\:one
INSERT INTO upload_request_groups (
    event_id,
    folder_id,
    requested_by,
    total_photo_count,
    batch_count
) VALUES (
    :p1, :p2, :p3, :p4, :p5
)
RETURNING
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
"""


GET_UPLOAD_REQUEST_GROUP_BY_ID = """-- name: get_upload_request_group_by_id \\:one
SELECT
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_request_groups
WHERE id = :p1
"""


LIST_UPLOAD_REQUEST_GROUPS = """-- name: list_upload_request_groups \\:many
SELECT
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_request_groups
ORDER BY created_at DESC
"""


LIST_UPLOAD_REQUEST_GROUPS_BY_STATUS = """-- name: list_upload_request_groups_by_status \\:many
SELECT
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_request_groups
WHERE status = :p1
ORDER BY created_at DESC
"""


LIST_UPLOAD_REQUEST_GROUPS_BY_REQUESTER = """-- name: list_upload_request_groups_by_requester \\:many
SELECT
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_request_groups
WHERE requested_by = :p1
ORDER BY created_at DESC
"""


LIST_UPLOAD_REQUEST_GROUPS_BY_REQUESTER_AND_STATUS = """-- name: list_upload_request_groups_by_requester_and_status \\:many
SELECT
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
FROM upload_request_groups
WHERE requested_by = :p1
  AND status = :p2
ORDER BY created_at DESC
"""


APPROVE_UPLOAD_REQUEST_GROUP = """-- name: approve_upload_request_group \\:one
UPDATE upload_request_groups
SET status = 'approved',
    approved_by = :p2,
    approved_at = NOW(),
    rejection_reason = NULL
WHERE id = :p1
  AND status = 'pending'
RETURNING
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
"""


REJECT_UPLOAD_REQUEST_GROUP = """-- name: reject_upload_request_group \\:one
UPDATE upload_request_groups
SET status = 'rejected',
    approved_by = :p2,
    approved_at = NOW(),
    rejection_reason = :p3
WHERE id = :p1
  AND status = 'pending'
RETURNING
    id,
    event_id,
    folder_id,
    requested_by,
    approved_by,
    status,
    total_photo_count,
    batch_count,
    created_at,
    approved_at,
    rejection_reason
"""


DELETE_UPLOAD_REQUEST_GROUP = """-- name: delete_upload_request_group \\:exec
DELETE FROM upload_request_groups
WHERE id = :p1
"""


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def create_upload_request_group(
        self,
        *,
        event_id: uuid.UUID,
        folder_id: str,
        requested_by: uuid.UUID,
        total_photo_count: int,
        batch_count: int,
    ) -> Optional[models.UploadRequestGroup]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(CREATE_UPLOAD_REQUEST_GROUP),
                {
                    "p1": event_id,
                    "p2": folder_id,
                    "p3": requested_by,
                    "p4": total_photo_count,
                    "p5": batch_count,
                },
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request_group(row)

    async def get_upload_request_group_by_id(
        self,
        *,
        id: uuid.UUID,
    ) -> Optional[models.UploadRequestGroup]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(GET_UPLOAD_REQUEST_GROUP_BY_ID),
                {"p1": id},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request_group(row)

    async def list_upload_request_groups(
        self,
        *,
        requested_by: uuid.UUID | None,
        status: str | None,
    ) -> AsyncIterator[models.UploadRequestGroup]:
        if requested_by is None and status is None:
            statement = LIST_UPLOAD_REQUEST_GROUPS
            params: dict[str, object] = {}
        elif requested_by is None:
            statement = LIST_UPLOAD_REQUEST_GROUPS_BY_STATUS
            params = {"p1": status}
        elif status is None:
            statement = LIST_UPLOAD_REQUEST_GROUPS_BY_REQUESTER
            params = {"p1": requested_by}
        else:
            statement = LIST_UPLOAD_REQUEST_GROUPS_BY_REQUESTER_AND_STATUS
            params = {"p1": requested_by, "p2": status}
        result = await self._conn.stream(
            sqlalchemy.text(statement),
            params,
        )
        async for row in result:
            yield _row_to_upload_request_group(row)

    async def approve_upload_request_group(
        self,
        *,
        id: uuid.UUID,
        approved_by: uuid.UUID,
    ) -> Optional[models.UploadRequestGroup]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(APPROVE_UPLOAD_REQUEST_GROUP),
                {"p1": id, "p2": approved_by},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request_group(row)

    async def reject_upload_request_group(
        self,
        *,
        id: uuid.UUID,
        approved_by: uuid.UUID,
        rejection_reason: str | None,
    ) -> Optional[models.UploadRequestGroup]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(REJECT_UPLOAD_REQUEST_GROUP),
                {"p1": id, "p2": approved_by, "p3": rejection_reason},
            )
        ).first()
        if row is None:
            return None
        return _row_to_upload_request_group(row)

    async def delete_upload_request_group(
        self,
        *,
        id: uuid.UUID,
    ) -> None:
        await self._conn.execute(
            sqlalchemy.text(DELETE_UPLOAD_REQUEST_GROUP),
            {"p1": id},
        )


def _row_to_upload_request_group(
    row: sqlalchemy.Row[tuple[object, ...]],
) -> models.UploadRequestGroup:
    return models.UploadRequestGroup(
        id=row[0],
        event_id=row[1],
        folder_id=row[2],
        requested_by=row[3],
        approved_by=row[4],
        status=row[5],
        total_photo_count=row[6],
        batch_count=row[7],
        created_at=row[8],
        approved_at=row[9],
        rejection_reason=row[10],
    )
