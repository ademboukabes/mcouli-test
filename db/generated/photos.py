# Code generated manually to match the sqlc async querier style used in the repo.
from typing import Optional
import datetime
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

from . import models


CREATE_PHOTO = """-- name: create_photo \\:one
INSERT INTO photos (
    event_id,
    storage_key,
    taken_at,
    day_number,
    visibility
) VALUES (
    :p1, :p2, :p3, :p4, :p5
)
RETURNING
    id,
    event_id,
    uploaded_by,
    storage_key,
    taken_at,
    day_number,
    visibility,
    status,
    created_at
"""


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def create_photo(
        self,
        *,
        event_id: uuid.UUID,
        storage_key: str,
        taken_at: datetime.datetime | None,
        day_number: int | None,
        visibility: str,
    ) -> Optional[models.Photo]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(CREATE_PHOTO),
                {
                    "p1": event_id,
                    "p2": storage_key,
                    "p3": taken_at,
                    "p4": day_number,
                    "p5": visibility,
                },
            )
        ).first()
        if row is None:
            return None
        return models.Photo(
            id=row[0],
            event_id=row[1],
            uploaded_by=row[2],
            storage_key=row[3],
            taken_at=row[4],
            day_number=row[5],
            visibility=row[6],
            status=row[7],
            created_at=row[8],
        )
