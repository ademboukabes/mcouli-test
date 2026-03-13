# Code generated manually to match the sqlc async querier style used in the repo.
from typing import Optional
import datetime
import uuid

import sqlalchemy
import sqlalchemy.ext.asyncio

from . import models


UPSERT_STAFF_DRIVE_CONNECTION = """-- name: upsert_staff_drive_connection \\:one
INSERT INTO staff_drive_connections (
    staff_user_id,
    provider,
    google_email,
    google_account_id,
    access_token,
    refresh_token,
    token_expires_at,
    scopes,
    connected_at,
    revoked_at,
    updated_at
) VALUES (
    :p1, :p2, :p3, :p4, :p5, :p6, :p7, :p8, NOW(), NULL, NOW()
)
ON CONFLICT (staff_user_id, provider)
DO UPDATE SET
    google_email = EXCLUDED.google_email,
    google_account_id = EXCLUDED.google_account_id,
    access_token = EXCLUDED.access_token,
    refresh_token = EXCLUDED.refresh_token,
    token_expires_at = EXCLUDED.token_expires_at,
    scopes = EXCLUDED.scopes,
    connected_at = NOW(),
    revoked_at = NULL,
    updated_at = NOW()
RETURNING
    id,
    staff_user_id,
    provider,
    google_email,
    google_account_id,
    access_token,
    refresh_token,
    token_expires_at,
    scopes,
    connected_at,
    revoked_at,
    created_at,
    updated_at
"""


GET_ACTIVE_STAFF_DRIVE_CONNECTION_BY_STAFF_USER_ID = """-- name: get_active_staff_drive_connection_by_staff_user_id \\:one
SELECT
    id,
    staff_user_id,
    provider,
    google_email,
    google_account_id,
    access_token,
    refresh_token,
    token_expires_at,
    scopes,
    connected_at,
    revoked_at,
    created_at,
    updated_at
FROM staff_drive_connections
WHERE staff_user_id = :p1
  AND provider = :p2
  AND revoked_at IS NULL
"""


REVOKE_STAFF_DRIVE_CONNECTION_BY_STAFF_USER_ID = """-- name: revoke_staff_drive_connection_by_staff_user_id \\:exec
UPDATE staff_drive_connections
SET revoked_at = NOW(),
    updated_at = NOW()
WHERE staff_user_id = :p1
  AND provider = :p2
  AND revoked_at IS NULL
"""


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def upsert_staff_drive_connection(
        self,
        *,
        staff_user_id: uuid.UUID,
        provider: str,
        google_email: str,
        google_account_id: str,
        access_token: str,
        refresh_token: Optional[str],
        token_expires_at: Optional[datetime.datetime],
        scopes: str,
    ) -> Optional[models.StaffDriveConnection]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(UPSERT_STAFF_DRIVE_CONNECTION),
                {
                    "p1": staff_user_id,
                    "p2": provider,
                    "p3": google_email,
                    "p4": google_account_id,
                    "p5": access_token,
                    "p6": refresh_token,
                    "p7": token_expires_at,
                    "p8": scopes,
                },
            )
        ).first()
        if row is None:
            return None
        return models.StaffDriveConnection(
            id=row[0],
            staff_user_id=row[1],
            provider=row[2],
            google_email=row[3],
            google_account_id=row[4],
            access_token=row[5],
            refresh_token=row[6],
            token_expires_at=row[7],
            scopes=row[8],
            connected_at=row[9],
            revoked_at=row[10],
            created_at=row[11],
            updated_at=row[12],
        )

    async def get_active_staff_drive_connection_by_staff_user_id(
        self,
        *,
        staff_user_id: uuid.UUID,
        provider: str,
    ) -> Optional[models.StaffDriveConnection]:
        row = (
            await self._conn.execute(
                sqlalchemy.text(GET_ACTIVE_STAFF_DRIVE_CONNECTION_BY_STAFF_USER_ID),
                {"p1": staff_user_id, "p2": provider},
            )
        ).first()
        if row is None:
            return None
        return models.StaffDriveConnection(
            id=row[0],
            staff_user_id=row[1],
            provider=row[2],
            google_email=row[3],
            google_account_id=row[4],
            access_token=row[5],
            refresh_token=row[6],
            token_expires_at=row[7],
            scopes=row[8],
            connected_at=row[9],
            revoked_at=row[10],
            created_at=row[11],
            updated_at=row[12],
        )

    async def revoke_staff_drive_connection_by_staff_user_id(
        self,
        *,
        staff_user_id: uuid.UUID,
        provider: str,
    ) -> None:
        await self._conn.execute(
            sqlalchemy.text(REVOKE_STAFF_DRIVE_CONNECTION_BY_STAFF_USER_ID),
            {"p1": staff_user_id, "p2": provider},
        )
