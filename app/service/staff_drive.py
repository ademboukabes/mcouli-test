import base64
import hashlib
import json
import secrets
import uuid

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.exceptions import AppException
from app.infra.google_drive import GoogleDriveClient
from app.infra.redis import RedisClient
from db.generated import staff_drive_connections as drive_queries
from db.generated import stuff_user as staff_queries
from db.generated.models import StaffDriveConnection, StaffUser


class StaffDriveService:
    STATE_PREFIX = "google_drive_oauth_state:{state}"
    STATE_TTL_SECONDS = 600
    PROVIDER = "google_drive"

    def __init__(
        self,
        staff_user_querier: staff_queries.AsyncQuerier,
        drive_connection_querier: drive_queries.AsyncQuerier,
        redis: RedisClient,
    ):
        self.staff_user_querier = staff_user_querier
        self.drive_connection_querier = drive_connection_querier
        self.redis = redis

    async def create_connect_url(self, staff_user: StaffUser) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        await self.redis.set(
            self.STATE_PREFIX.format(state=state),
            json.dumps({"staff_user_id": str(staff_user.id)}),
            expire=self.STATE_TTL_SECONDS,
            nx=True,
        )
        return GoogleDriveClient.build_consent_url(state), state

    async def handle_callback(self, code: str, state: str) -> StaffDriveConnection:
        state_key = self.STATE_PREFIX.format(state=state)
        state_payload = await self.redis.get(state_key)
        if state_payload is None:
            raise AppException.bad_request("OAuth state is missing or expired")

        await self.redis.delete(state_key)

        try:
            staff_user_id = uuid.UUID(json.loads(state_payload)["staff_user_id"])
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise AppException.bad_request("Invalid OAuth state payload") from exc

        staff_user = await self.staff_user_querier.get_staff_user_by_id(id=staff_user_id)
        if staff_user is None:
            raise AppException.not_found("Staff user not found")

        token = await GoogleDriveClient.exchange_code(code)
        user_info = await GoogleDriveClient.get_user_info(token.access_token)

        encrypted_access_token = self._encrypt(token.access_token)
        encrypted_refresh_token = (
            self._encrypt(token.refresh_token) if token.refresh_token else None
        )

        connection = await self.drive_connection_querier.upsert_staff_drive_connection(
            arg=drive_queries.UpsertStaffDriveConnectionParams(
            staff_user_id=staff_user.id,
            provider=self.PROVIDER,
            google_email=user_info.email,
            google_account_id=user_info.id,
            access_token=encrypted_access_token,
            refresh_token=encrypted_refresh_token,
            token_expires_at=token.expires_at,
            scopes=token.scope,

            )

        )
        if connection is None:
            raise AppException.internal_error("Failed to save Google Drive connection")

        return connection

    async def get_status(self, staff_user_id: uuid.UUID) -> StaffDriveConnection | None:
        return await self.drive_connection_querier.get_active_staff_drive_connection_by_staff_user_id(
            staff_user_id=staff_user_id,
            provider=self.PROVIDER,
        )

    async def disconnect(self, staff_user_id: uuid.UUID) -> None:
        connection = await self.get_status(staff_user_id)
        if connection is None:
            raise AppException.not_found("No Google Drive connection found")

        await self.drive_connection_querier.revoke_staff_drive_connection_by_staff_user_id(
            staff_user_id=staff_user_id,
            provider=self.PROVIDER,
        )

    def _encrypt(self, raw_value: str) -> str:
        return self._fernet().encrypt(raw_value.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted_value: str) -> str:
        try:
            return self._fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise AppException.internal_error("Stored Google Drive token cannot be decrypted") from exc

    def _fernet(self) -> Fernet:
        digest = hashlib.sha256(settings.encryption_key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))
