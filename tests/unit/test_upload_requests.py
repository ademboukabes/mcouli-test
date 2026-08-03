import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError
from fastapi.exceptions import HTTPException

from app.infra.google_drive import GoogleDriveFileDownload, GoogleDriveFileMetadata
from app.infra.nats import NatsSubjects
from app.schema.internal.uploads import UploadPhotoInput
from app.service.staged_upload_storage import StoredObject
from app.service.upload_requests import UploadRequestsService
from db.generated.models import (
    StaffUser,
    UploadRequest,
    UploadRequestGroup,
    UploadRequestPhoto,
)


@pytest.fixture
def mock_upload_request_group_querier():
    return AsyncMock()

@pytest.fixture
def mock_upload_request_querier():
    return AsyncMock()

@pytest.fixture
def mock_upload_request_photo_querier():
    return AsyncMock()

@pytest.fixture
def mock_photo_querier():
    return AsyncMock()

@pytest.fixture
def mock_staged_upload_storage():
    mock = AsyncMock()
    mock.store_staging_object.return_value = StoredObject(storage_key="test_storage_key", content_type="image/jpeg", file_name="photo.jpg")
    return mock

@pytest.fixture
def mock_staff_drive_service():
    mock = AsyncMock()
    mock.get_access_token_for_staff_user.return_value = "fake_access_token"
    mock.staff_user_querier = AsyncMock()
    return mock

@pytest.fixture
def mock_staff_notifications_service():
    return AsyncMock()

@pytest.fixture
def mock_audit_service():
    return AsyncMock()


@pytest.fixture
def upload_requests_service(
    mock_upload_request_group_querier,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_photo_querier,
    mock_staged_upload_storage,
    mock_staff_drive_service,
    mock_staff_notifications_service,
    mock_audit_service,
):
    return UploadRequestsService(
        upload_request_group_querier=mock_upload_request_group_querier,
        upload_request_querier=mock_upload_request_querier,
        upload_request_photo_querier=mock_upload_request_photo_querier,
        photo_querier=mock_photo_querier,
        staged_upload_storage=mock_staged_upload_storage,
        staff_drive_service=mock_staff_drive_service,
        staff_notifications_service=mock_staff_notifications_service,
        audit_service=mock_audit_service,
    )


@pytest.fixture
def mock_staff_user():
    return StaffUser(
        id=uuid.uuid4(),
        email="test@multai.com",
        password="hash",
        role="PHOTOGRAPHER",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def create_integrity_error(sqlstate: str) -> IntegrityError:
    orig = MagicMock()
    orig.sqlstate = sqlstate
    return IntegrityError("statement", "params", orig)


@pytest.mark.asyncio
async def test_create_request_success(
    upload_requests_service,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    event_id = uuid.uuid4()
    request_id = uuid.uuid4()

    # Setup mocks
    mock_upload_request_querier.create_upload_request.return_value = UploadRequest(
        id=request_id,
        event_id=event_id,
        group_id=None,
        drive_file_id=None,
        requested_by=mock_staff_user.id,
        photo_count=1,
        status="pending",
        approved_by=None,
        rejection_reason=None,
        created_at=datetime.now(timezone.utc),
        approved_at=None,
    )

    mock_upload_request_photo_querier.create_upload_request_photo.return_value = UploadRequestPhoto(
        id=uuid.uuid4(),
        upload_request_id=request_id,
        drive_file_id="drive_id_1",
        file_name="photo.jpg",
        mime_type="image/jpeg",
        size_bytes=1024,
        staging_storage_key="test_storage_key",
        final_storage_key=None,
        taken_at=None,
        day_number=None,
        visibility="public",
        status="staged",
        created_at=datetime.now(timezone.utc),
    )

    photos = [
        UploadPhotoInput(
            drive_file_id="drive_id_1",
            taken_at=None,
            day_number=None,
            visibility="public",
        )
    ]

    mock_download = GoogleDriveFileDownload(
        metadata=GoogleDriveFileMetadata(
            id="drive_id_1", name="photo.jpg", mime_type="image/jpeg", size_bytes=1024
        ),
        content=b"content",
    )

    with patch("app.service.upload_requests.GoogleDriveClient.download_file", return_value=mock_download) as mock_drive, \
         patch("app.service.upload_requests.NatsClient.publish") as mock_publish:

        details = await upload_requests_service.create_request(
            event_id=event_id,
            photos=photos,
            requested_by=mock_staff_user,
        )

        assert details.request.id == request_id
        assert len(details.photos) == 1
        assert details.photos[0].drive_file_id == "drive_id_1"

        mock_drive.assert_called_once()
        mock_staged_upload_storage.store_staging_object.assert_called_once()
        mock_upload_request_querier.create_upload_request.assert_called_once()
        mock_upload_request_photo_querier.create_upload_request_photo.assert_called_once()
        mock_publish.assert_called_once()

        # Verify NATS event subject
        assert mock_publish.call_args[0][0] == NatsSubjects.STAFF_UPLOAD_REQUEST_CREATED


@pytest.mark.asyncio
async def test_create_request_duplicate_conflict(
    upload_requests_service,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    event_id = uuid.uuid4()
    request_id = uuid.uuid4()

    mock_upload_request_querier.create_upload_request.return_value = UploadRequest(
            id=request_id, event_id=event_id, group_id=None, drive_file_id=None, requested_by=mock_staff_user.id, photo_count=1, status="pending", approved_by=None, rejection_reason=None, created_at=datetime.now(timezone.utc), approved_at=None
        )

    # Simulate DB Conflict (Duplicate) on photo insert
    mock_upload_request_photo_querier.create_upload_request_photo.side_effect = create_integrity_error("23505")

    photos = [UploadPhotoInput(drive_file_id="drive_id_1", taken_at=None, day_number=None, visibility="public")]

    mock_download = GoogleDriveFileDownload(
        metadata=GoogleDriveFileMetadata(id="drive_id_1", name="photo.jpg", mime_type="image/jpeg", size_bytes=1024),
        content=b"content",
    )

    with patch("app.service.upload_requests.GoogleDriveClient.download_file", return_value=mock_download):
        with pytest.raises(HTTPException) as exc:
            await upload_requests_service.create_request(event_id=event_id, photos=photos, requested_by=mock_staff_user)

        assert exc.value.status_code == 409
        assert "Duplicate photo" in exc.value.detail

        # Verify cleanup was called on StagedUploadStorageService
        mock_staged_upload_storage.delete_storage_key.assert_called_once_with("test_storage_key")


@pytest.mark.asyncio
async def test_create_group_from_folder(
    upload_requests_service,
    mock_upload_request_group_querier,
    mock_staff_user,
):
    event_id = uuid.uuid4()
    group_id = uuid.uuid4()

    mock_upload_request_group_querier.create_upload_request_group.return_value = UploadRequestGroup(
            id=group_id, event_id=event_id, folder_id="folder_123", requested_by=mock_staff_user.id, total_photo_count=0, batch_count=0, processed_photo_count=0, failed_photo_count=0, processing_status="pending", error_message=None, created_at=datetime.now(timezone.utc), status="pending", approved_by=None, approved_at=None, rejection_reason=None
        )

    with patch("app.service.upload_requests.NatsClient.publish") as mock_publish:
        details = await upload_requests_service.create_group_from_folder(
            event_id=event_id, folder_id="folder_123", visibility="public", day_number=None, requested_by=mock_staff_user
        )

        assert details.group.id == group_id
        mock_upload_request_group_querier.create_upload_request_group.assert_called_once()
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][0] == NatsSubjects.STAFF_UPLOAD_GROUP_IMPORT_REQUESTED


@pytest.mark.asyncio
async def test_process_group_import_no_images(
    upload_requests_service,
    mock_upload_request_group_querier,
    mock_upload_request_querier,
    mock_staff_drive_service,
    mock_staff_user,
):
    group_id = uuid.uuid4()
    mock_upload_request_group_querier.start_upload_request_group_processing.return_value = UploadRequestGroup(
            id=group_id, event_id=uuid.uuid4(), folder_id="folder_123", requested_by=mock_staff_user.id, total_photo_count=0, batch_count=0, processed_photo_count=0, failed_photo_count=0, processing_status="processing", error_message=None, created_at=datetime.now(timezone.utc), status="pending", approved_by=None, approved_at=None, rejection_reason=None
        )
    mock_staff_drive_service.staff_user_querier.get_staff_user_by_id.return_value = mock_staff_user

    # Return 0 images
    with patch("app.service.upload_requests.GoogleDriveClient.list_folder_files", return_value=[]):
        async def mock_get_group(*args, **kwargs):
            yield UploadRequestGroup(
                    id=group_id, event_id=uuid.uuid4(), folder_id="folder_123", requested_by=mock_staff_user.id, total_photo_count=0, batch_count=0, processed_photo_count=0, failed_photo_count=0, processing_status="processing", error_message=None, created_at=datetime.now(timezone.utc), status="pending", approved_by=None, approved_at=None, rejection_reason=None
                )
        mock_upload_request_querier.list_upload_requests_by_group_id = mock_get_group

        async def mock_list_photos_by_ids(*args, **kwargs):
            if False:
                yield # Empty generator
        upload_requests_service.upload_request_photo_querier.list_upload_request_photos_by_upload_request_ids = mock_list_photos_by_ids

        mock_upload_request_group_querier.get_upload_request_group_by_id.return_value = UploadRequestGroup(
                id=group_id, event_id=uuid.uuid4(), folder_id="folder_123", requested_by=mock_staff_user.id, total_photo_count=0, batch_count=0, processed_photo_count=0, failed_photo_count=0, processing_status="processing", error_message=None, created_at=datetime.now(timezone.utc), status="pending", approved_by=None, approved_at=None, rejection_reason=None
            )

        await upload_requests_service.process_group_import(
            group_id=group_id, visibility="public", day_number=None
        )

        # Verify it marked group as failed
        mock_upload_request_group_querier.fail_upload_request_group_processing.assert_called_once()
        kwargs = mock_upload_request_group_querier.fail_upload_request_group_processing.call_args[0][0]
        assert "does not contain valid images" in kwargs.error_message


@pytest.mark.asyncio
async def test_approve_request_without_side_effects(
    upload_requests_service,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_photo_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    request_id = uuid.uuid4()
    photo_id = uuid.uuid4()
    event_id = uuid.uuid4()

    mock_upload_request_querier.get_upload_request_by_id.return_value = UploadRequest(
            id=request_id, event_id=event_id, group_id=None, drive_file_id=None, requested_by=uuid.uuid4(), photo_count=1, status="pending", approved_by=None, rejection_reason=None, created_at=datetime.now(timezone.utc), approved_at=None
        )

    async def mock_list_photos(*args, **kwargs):
        yield UploadRequestPhoto(
            id=photo_id, upload_request_id=request_id, drive_file_id="drive_1", file_name="p.jpg", mime_type="image/jpeg", size_bytes=100, staging_storage_key="stage_key", final_storage_key=None, taken_at=None, day_number=None, visibility="public", status="staged", created_at=datetime.now(timezone.utc)
        )
    mock_upload_request_photo_querier.list_upload_request_photos_by_upload_request_id = mock_list_photos

    mock_staged_upload_storage.promote_to_final.return_value = "final_key"
    mock_photo_querier.create_photo.return_value = MagicMock()
    mock_upload_request_photo_querier.update_upload_request_photo_approval.return_value = MagicMock()
    mock_upload_request_querier.approve_upload_request.return_value = MagicMock()

    upload_req, staged_photos, final_keys, created_photos = await upload_requests_service._approve_request_without_side_effects(
        request_id=request_id, approved_by=mock_staff_user
    )

    assert len(staged_photos) == 1
    assert final_keys == ["final_key"]
    assert len(created_photos) == 1

    mock_staged_upload_storage.promote_to_final.assert_called_once()
    mock_photo_querier.create_photo.assert_called_once()
    mock_upload_request_querier.approve_upload_request.assert_called_once()
