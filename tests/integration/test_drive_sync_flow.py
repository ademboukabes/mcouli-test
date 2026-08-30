"""
Integration tests for the Drive Sync worker flow.
"""

import uuid
import json
import datetime
from unittest.mock import AsyncMock, patch, MagicMock
import contextlib

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from fastapi import HTTPException

from app.core.config import settings
from app.worker.drive_sync.main import _handle_event

from db.generated import staff_user as staff_queries
from db.generated import events as event_queries
from db.generated import photos as photo_queries
from db.generated import staff_drive_connections as drive_queries

pytestmark = pytest.mark.integration

@pytest.fixture
async def db_conn():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()

@pytest.fixture
async def setup_data(db_conn):
    sq = staff_queries.AsyncQuerier(db_conn)
    eq = event_queries.AsyncQuerier(db_conn)
    pq = photo_queries.AsyncQuerier(db_conn)
    dq = drive_queries.AsyncQuerier(db_conn)

    staff = await sq.create_admin(email=f"admin-{uuid.uuid4()}@test.com", password="hash")

    event = await eq.create_event(
        event_queries.CreateEventParams(
            name="Drive Sync Test Event",
            event_code=f"DS{str(uuid.uuid4())[:4]}",
            event_date=datetime.datetime.now(datetime.timezone.utc),
            end_date=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            status="scheduled",
            created_by=staff.id,
        )
    )

    photo = await pq.create_photo(
        photo_queries.CreatePhotoParams(
            event_id=event.id,
            storage_key="test/sync_photo.jpg",
            source="direct",
            taken_at=None,
            day_number=None,
            visibility="public",
        )
    )

    conn = await dq.upsert_staff_drive_connection(
        drive_queries.UpsertStaffDriveConnectionParams(
            staff_user_id=staff.id,
            provider="google_drive",
            google_email="test@google.com",
            google_account_id="12345",
            access_token="encrypted_access_token",
            refresh_token="encrypted_refresh_token",
            token_expires_at=datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1),
            scopes="scopes",
        )
    )

    return {
        "staff": staff,
        "event": event,
        "photo": photo,
        "connection": conn,
    }

@pytest.mark.asyncio
@patch("app.worker.drive_sync.main.Bucket")
@patch("app.worker.drive_sync.main.StaffDriveService")
async def test_successful_drive_sync(mock_staff_drive_service_class, mock_bucket_class, db_conn, setup_data):
    """Test that a photo sync event successfully triggers the drive upload."""
    mock_bucket = AsyncMock()
    mock_bucket.get.return_value = (b"fake_image_data", None, "image/jpeg")
    mock_bucket_class.return_value = mock_bucket

    mock_service = AsyncMock()
    mock_service.upload_to_system_drive.return_value = "google_drive_file_id_123"
    mock_staff_drive_service_class.return_value = mock_service

    @contextlib.asynccontextmanager
    async def mock_begin():
        yield db_conn

    mock_engine = MagicMock()
    mock_engine.begin = mock_begin

    payload = {
        "photo_id": str(setup_data["photo"].id),
        "event_id": str(setup_data["event"].id),
        "storage_key": setup_data["photo"].storage_key,
        "file_name": "sync_photo.jpg",
        "mime_type": "image/jpeg",
    }
    raw_data = json.dumps(payload).encode("utf-8")

    with patch("app.worker.drive_sync.main.engine", mock_engine), \
         patch("app.worker.drive_sync.main.RedisClient.get_instance", return_value=AsyncMock()):
        await _handle_event(raw_data)

    mock_service.upload_to_system_drive.assert_called_once_with(
        file_name="sync_photo.jpg",
        content_type="image/jpeg",
        data=b"fake_image_data",
        event_id=setup_data["event"].id,
        event_name="Drive Sync Test Event"
    )

    pq = photo_queries.AsyncQuerier(db_conn)
    updated_photo = await pq.get_photo_by_id(id=setup_data["photo"].id)
    assert updated_photo.drive_file_id == "google_drive_file_id_123"

@pytest.mark.asyncio
@patch("app.worker.drive_sync.main.Bucket")
@patch("app.worker.drive_sync.main.StaffDriveService")
async def test_drive_sync_pauses_on_revoked_token(mock_staff_drive_service_class, mock_bucket_class, db_conn, setup_data):
    """Test that the worker gracefully pauses when the token is revoked."""
    mock_bucket = AsyncMock()
    mock_bucket.get.return_value = (b"fake_image_data", None, "image/jpeg")
    mock_bucket_class.return_value = mock_bucket

    mock_service = AsyncMock()
    mock_service.upload_to_system_drive.side_effect = HTTPException(status_code=404, detail="Drive connection revoked")
    mock_staff_drive_service_class.return_value = mock_service

    @contextlib.asynccontextmanager
    async def mock_begin():
        yield db_conn

    mock_engine = MagicMock()
    mock_engine.begin = mock_begin

    payload = {
        "photo_id": str(setup_data["photo"].id),
        "event_id": str(setup_data["event"].id),
        "storage_key": setup_data["photo"].storage_key,
        "file_name": "sync_photo.jpg",
        "mime_type": "image/jpeg",
    }
    raw_data = json.dumps(payload).encode("utf-8")

    with patch("app.worker.drive_sync.main.asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("app.worker.drive_sync.main.engine", mock_engine), \
         patch("app.worker.drive_sync.main.RedisClient.get_instance", return_value=AsyncMock()):
        with pytest.raises(HTTPException):
            await _handle_event(raw_data)

        mock_sleep.assert_called_once_with(300)
