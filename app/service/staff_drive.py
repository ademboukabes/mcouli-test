import asyncio
import base64
import hashlib
import json
import secrets
import urllib.parse
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.constant import IMAGE_ALLOWED_TYPES
from app.core.exceptions import AppException
from app.infra.google_drive import GoogleDriveClient
from app.infra.minio import ImageBucket
from app.infra.redis import RedisClient
from db.generated import staff_drive_connections as drive_queries
from db.generated import stuff_user as staff_queries
from db.generated.models import StaffDriveConnection, StaffUser


DRIVE_BUCKET_PREFIX = "staff-drive"
MAX_IMPORT_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


@dataclass
class SelectedDriveFile:
    id: str
    name: str
    mime_type: str | None


@dataclass
class DriveImportResult:
    drive_file_id: str
    original_file_name: str
    minio_bucket: str
    minio_object_name: str
    minio_object_path: str


class StaffDriveService:
    STATE_PREFIX = "google_drive_oauth_state:{state}"
    STATE_TTL_SECONDS = 600
    PROVIDER = "google_drive"
    TOKEN_REFRESH_BUFFER = timedelta(minutes=5)

    def __init__(
        self,
        staff_user_querier: staff_queries.AsyncQuerier,
        drive_connection_querier: drive_queries.AsyncQuerier,
        redis: RedisClient,
    ):
        self.staff_user_querier = staff_user_querier
        self.drive_connection_querier = drive_connection_querier
        self.redis = redis

    async def create_connect_url(
        self,
        staff_user: StaffUser,
        redirect_url: str | None = None,
    ) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        state_payload: dict[str, str] = {"staff_user_id": str(staff_user.id)}
        if redirect_url is not None:
            state_payload["redirect_url"] = self._validate_redirect_url(redirect_url)

        await self.redis.set(
            self.STATE_PREFIX.format(state=state),
            json.dumps(state_payload),
            expire=self.STATE_TTL_SECONDS,
            nx=True,
        )
        return GoogleDriveClient.build_consent_url(state), state

    async def get_callback_redirect_url(self, state: str) -> str | None:
        state_payload = await self.redis.get(self.STATE_PREFIX.format(state=state))
        if state_payload is None:
            return None
        try:
            payload = json.loads(state_payload)
        except json.JSONDecodeError:
            return None
        redirect_url = payload.get("redirect_url")
        if isinstance(redirect_url, str) and redirect_url:
            return redirect_url
        return None

    async def handle_callback(
        self,
        code: str,
        state: str,
    ) -> tuple[StaffDriveConnection, str | None]:
        state_key = self.STATE_PREFIX.format(state=state)
        state_payload = await self.redis.get(state_key)
        if state_payload is None:
            raise AppException.bad_request("OAuth state is missing or expired")

        await self.redis.delete(state_key)

        try:
            payload = json.loads(state_payload)
            staff_user_id = uuid.UUID(payload["staff_user_id"])
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise AppException.bad_request("Invalid OAuth state payload") from exc

        redirect_url = payload.get("redirect_url")
        if redirect_url is not None and not isinstance(redirect_url, str):
            raise AppException.bad_request("Invalid OAuth redirect URL")

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

        return connection, redirect_url

    async def get_status(self, staff_user_id: uuid.UUID) -> StaffDriveConnection | None:
        return await self.drive_connection_querier.get_active_staff_drive_connection_by_staff_user_id(
            staff_user_id=staff_user_id,
            provider=self.PROVIDER,
        )

    async def get_active_connection_or_raise(
        self,
        staff_user_id: uuid.UUID,
    ) -> StaffDriveConnection:
        connection = await self.get_status(staff_user_id)
        if connection is None:
            raise AppException.bad_request("Staff Google Drive is not connected")
        return connection

    @classmethod
    def _token_needs_refresh(cls, connection: StaffDriveConnection) -> bool:
        if connection.token_expires_at is None:
            return False
        return connection.token_expires_at <= datetime.now(timezone.utc) + cls.TOKEN_REFRESH_BUFFER

    async def _refresh_connection_access_token(
        self,
        connection: StaffDriveConnection,
    ) -> StaffDriveConnection:
        if connection.refresh_token is None:
            raise AppException.bad_request(
                "Google Drive connection expired and must be reconnected"
            )

        refresh_token = self.decrypt(connection.refresh_token)
        token = await GoogleDriveClient.refresh_access_token(refresh_token)

        encrypted_access_token = self._encrypt(token.access_token)
        encrypted_refresh_token = connection.refresh_token
        if token.refresh_token:
            encrypted_refresh_token = self._encrypt(token.refresh_token)

        refreshed_connection = await self.drive_connection_querier.upsert_staff_drive_connection(
            arg=drive_queries.UpsertStaffDriveConnectionParams(
                staff_user_id=connection.staff_user_id,
                provider=connection.provider,
                google_email=connection.google_email,
                google_account_id=connection.google_account_id,
                access_token=encrypted_access_token,
                refresh_token=encrypted_refresh_token,
                token_expires_at=token.expires_at,
                scopes=token.scope,
            )
        )
        if refreshed_connection is None:
            raise AppException.internal_error("Failed to refresh Google Drive connection")

        return refreshed_connection

    async def get_access_token_for_staff_user(self, staff_user_id: uuid.UUID) -> str:
        connection = await self.get_active_connection_or_raise(staff_user_id)
        if self._token_needs_refresh(connection):
            connection = await self._refresh_connection_access_token(connection)
        return self.decrypt(connection.access_token)

    async def get_system_access_token(self) -> str:
        """Get an access token from any active staff Drive connection."""
        connection = await self.drive_connection_querier.get_any_active_staff_drive_connection()
        if connection is None:
            raise AppException.not_found("No active Google Drive connection")
        if self._token_needs_refresh(connection):
            connection = await self._refresh_connection_access_token(connection)
        return self.decrypt(connection.access_token)

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

    async def import_images_from_drive(
        self,
        staff_user: StaffUser,
        selected_files: list[SelectedDriveFile],
    ) -> list[DriveImportResult]:
        """Download selected Drive files and store them in MinIO (images bucket)."""
        if not selected_files:
            return []

        access_token = await self.get_access_token_for_staff_user(staff_user.id)
        bucket = ImageBucket(f"{DRIVE_BUCKET_PREFIX}/{staff_user.id}")
        semaphore = asyncio.Semaphore(10)

        async def process_file(selected: SelectedDriveFile) -> DriveImportResult:
            if selected.mime_type and selected.mime_type not in IMAGE_ALLOWED_TYPES:
                raise AppException.bad_request(
                    f"File '{selected.name}' has unsupported type '{selected.mime_type}'. "
                    f"Allowed: {', '.join(sorted(IMAGE_ALLOWED_TYPES))}"
                )

            async with semaphore:
                download = await GoogleDriveClient.download_file(
                    access_token=access_token,
                    file_id=selected.id,
                )

                if len(download.content) > MAX_IMPORT_FILE_SIZE_BYTES:
                    raise AppException.bad_request(
                        f"File '{selected.name}' exceeds the 20 MB size limit"
                    )

                object_name = self._generate_object_name(selected.name)
                content_type = selected.mime_type or download.metadata.mime_type

                await bucket.put_bytes(
                    data=download.content,
                    object_name=object_name,
                    content_type=content_type,
                    filename=selected.name,
                )

            return DriveImportResult(
                drive_file_id=selected.id,
                original_file_name=selected.name,
                minio_bucket=bucket.bucket_name,
                minio_object_name=object_name,
                minio_object_path=f"{bucket.file_prefix}/{object_name}",
            )

        tasks = [process_file(selected) for selected in selected_files]
        results = await asyncio.gather(*tasks)
        return list(results)

    def _fernet(self) -> Fernet:
        digest = hashlib.sha256(settings.encryption_key.encode("utf-8")).digest()
        return Fernet(base64.urlsafe_b64encode(digest))

    @staticmethod
    def _generate_object_name(filename: str) -> str:
        suffix = filename[filename.rfind("."):] if "." in filename else ""
        return f"{uuid.uuid4()}{suffix}"

    @staticmethod
    def _validate_redirect_url(redirect_url: str) -> str:
        parsed = urllib.parse.urlparse(redirect_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise AppException.bad_request("Invalid redirect URL")
        return redirect_url

    @staticmethod
    def build_frontend_callback_url(
        redirect_url: str,
        *,
        status: str,
        google_email: str | None = None,
        error: str | None = None,
    ) -> str:
        parsed = urllib.parse.urlparse(redirect_url)
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        query.append(("status", status))
        if google_email is not None:
            query.append(("google_email", google_email))
        if error is not None:
            query.append(("error", error))
        return urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))
