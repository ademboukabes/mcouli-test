# Code generated manually to match the sqlc async querier style used in the repo.
from typing import AsyncIterator, Optional
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

from . import models


CREATE_STAFF_NOTIFICATION = """-- name: create_staff_notification \\:one
INSERT INTO staff_notifications (
    staff_user_id,
    type,
    payload
) VALUES (
    :p1, :p2, :p3
)
RETURNING
    id,
    staff_user_id,
    type,
    payload,
    read_at,
    created_at
"""


LIST_STAFF_NOTIFICATIONS_BY_STAFF_USER_ID = """-- name: list_staff_notifications_by_staff_user_id \\:many
SELECT
    id,
    staff_user_id,
    type,
    payload,
    read_at,
    created_at
FROM staff_notifications
WHERE staff_user_id = :p1
ORDER BY created_at DESC
"""


MARK_STAFF_NOTIFICATION_AS_READ = """-- name: mark_staff_notification_as_read \\:one
UPDATE staff_notifications
SET read_at = NOW()
WHERE id = :p1
  AND staff_user_id = :p2
  AND read_at IS NULL
RETURNING
    id,
    staff_user_id,
    type,
    payload,
    read_at,
    created_at
"""


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def create_staff_notification(
        self,
        *,
        staff_user_id: uuid.UUID,
        type: str,
        payload: dict[str, object],
    ) -> Optional[models.StaffNotification]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(CREATE_STAFF_NOTIFICATION),
                {"p1": staff_user_id, "p2": type, "p3": payload},
            )
        ).first()
        if row is None:
            return None
        return _row_to_staff_notification(row)

    async def list_staff_notifications_by_staff_user_id(
        self,
        *,
        staff_user_id: uuid.UUID,
    ) -> AsyncIterator[models.StaffNotification]:
        result = await self._conn.stream(
            sqlalchemy.text(LIST_STAFF_NOTIFICATIONS_BY_STAFF_USER_ID),
            {"p1": staff_user_id},
        )
        async for row in result:
            yield _row_to_staff_notification(row)

    async def mark_staff_notification_as_read(
        self,
        *,
        id: uuid.UUID,
        staff_user_id: uuid.UUID,
    ) -> Optional[models.StaffNotification]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(MARK_STAFF_NOTIFICATION_AS_READ),
                {"p1": id, "p2": staff_user_id},
            )
        ).first()
        if row is None:
            return None
        return _row_to_staff_notification(row)


def _row_to_staff_notification(
    row: sqlalchemy.Row[tuple[object, ...]],
) -> models.StaffNotification:
    return models.StaffNotification(
        id=row[0],
        staff_user_id=row[1],
        type=row[2],
        payload=row[3],
        read_at=row[4],
        created_at=row[5],
    )
