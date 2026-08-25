import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.schema.internal.uploads import DirectFileInput
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
    mock.create_presigned_staging_upload.return_value = ("staging/upload-requests/req1/photo1.jpg", "https://minio.local/signed-url")
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
        role="multi",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_group(group_id, event_id, requested_by_id, **overrides):
    defaults = dict(
        id=group_id, event_id=event_id, folder_id=None, requested_by=requested_by_id,
        approved_by=None, status="pending", total_photo_count=0, batch_count=0,
        created_at=datetime.now(timezone.utc), approved_at=None, rejection_reason=None,
        processing_status="completed", processed_photo_count=0, failed_photo_count=0,
        error_message=None, source="direct",
    )
    defaults.update(overrides)
    return UploadRequestGroup(**defaults)


def _make_request(request_id, event_id, requested_by_id, group_id, **overrides):
    defaults = dict(
        id=request_id, event_id=event_id, drive_file_id=None, requested_by=requested_by_id,
        approved_by=None, status="pending", created_at=datetime.now(timezone.utc),
        approved_at=None, photo_count=1, rejection_reason=None, group_id=group_id,
        source="direct",
    )
    defaults.update(overrides)
    return UploadRequest(**defaults)


def _make_photo(photo_id, request_id, **overrides):
    defaults = dict(
        id=photo_id, upload_request_id=request_id, drive_file_id=None, file_name="a.jpg",
        mime_type="image/jpeg", size_bytes=1000, staging_storage_key="staging/x.jpg",
        final_storage_key=None, taken_at=None, day_number=None, visibility="private",
        status="staged", created_at=datetime.now(timezone.utc),
        source="direct", transfer_status="pending_upload",
    )
    defaults.update(overrides)
    return UploadRequestPhoto(**defaults)


@pytest.mark.asyncio
async def test_create_direct_group_sets_source_and_completed_processing(
    upload_requests_service,
    mock_upload_request_group_querier,
    mock_staff_user,
):
    event_id = uuid.uuid4()
    group_id = uuid.uuid4()
    mock_upload_request_group_querier.create_upload_request_group.return_value = _make_group(
        group_id, event_id, mock_staff_user.id,
    )

    group = await upload_requests_service.create_direct_group(
        event_id=event_id, requested_by=mock_staff_user,
    )

    assert group.id == group_id
    call_args = mock_upload_request_group_querier.create_upload_request_group.call_args
    params = call_args.args[0] if call_args.args else call_args.kwargs["arg"]
    assert params.folder_id is None
    assert params.source == "direct"
    assert params.processing_status == "completed"


@pytest.mark.asyncio
async def test_register_direct_batch_creates_pending_photos_and_returns_urls(
    upload_requests_service,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_upload_request_group_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    group_id = uuid.uuid4()
    event_id = uuid.uuid4()
    request_id = uuid.uuid4()
    photo_id = uuid.uuid4()

    mock_upload_request_group_querier.get_upload_request_group_by_id.return_value = _make_group(
        group_id, event_id, mock_staff_user.id,
    )
    mock_upload_request_querier.create_upload_request.return_value = _make_request(
        request_id, event_id, mock_staff_user.id, group_id,
    )
    mock_upload_request_photo_querier.create_direct_upload_request_photo.return_value = _make_photo(
        photo_id, request_id, staging_storage_key="staging/upload-requests/req1/photo1.jpg",
    )

    results = await upload_requests_service.register_direct_batch(
        group_id=group_id,
        files=[DirectFileInput(
            file_name="a.jpg", mime_type="image/jpeg", size_bytes=1000,
            taken_at=None, day_number=None, visibility="private",
        )],
        requested_by=mock_staff_user,
    )

    assert len(results) == 1
    photo, url = results[0]
    assert photo.id == photo_id
    assert url == "https://minio.local/signed-url"
    mock_staged_upload_storage.create_presigned_staging_upload.assert_awaited()
    mock_upload_request_group_querier.increment_upload_request_group_counts.assert_awaited_once_with(
        id=group_id, total_photo_count=1,
    )


@pytest.mark.asyncio
async def test_register_direct_batch_rejects_oversized_batch(
    upload_requests_service,
    mock_upload_request_group_querier,
    mock_staff_user,
):
    group_id = uuid.uuid4()
    from app.core.exceptions import AppException

    files = [
        DirectFileInput(file_name=f"{i}.jpg", mime_type="image/jpeg", size_bytes=1000, taken_at=None, day_number=None, visibility="private")
        for i in range(201)
    ]

    with pytest.raises(Exception):
        await upload_requests_service.register_direct_batch(
            group_id=group_id, files=files, requested_by=mock_staff_user,
        )
    mock_upload_request_group_querier.get_upload_request_group_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_direct_upload_success_updates_transfer_status(
    upload_requests_service,
    mock_upload_request_photo_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    from app.infra.minio import ObjectStat

    photo_id = uuid.uuid4()
    request_id = uuid.uuid4()
    existing_photo = _make_photo(photo_id, request_id, transfer_status="pending_upload")
    mock_upload_request_photo_querier.get_upload_request_photo_by_id.return_value = existing_photo
    mock_staged_upload_storage.stat_staging_object.return_value = ObjectStat(size=1000, content_type="image/jpeg")
    mock_upload_request_photo_querier.confirm_upload_request_photo_transfer.return_value = _make_photo(
        photo_id, request_id, transfer_status="uploaded",
    )

    result = await upload_requests_service.confirm_direct_upload(
        photo_id=photo_id, requested_by=mock_staff_user,
    )

    assert result.id == photo_id
    mock_upload_request_photo_querier.confirm_upload_request_photo_transfer.assert_awaited_once_with(
        id=photo_id, size_bytes=1000, mime_type="image/jpeg",
    )


@pytest.mark.asyncio
async def test_confirm_direct_upload_marks_failed_when_object_missing(
    upload_requests_service,
    mock_upload_request_photo_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    photo_id = uuid.uuid4()
    request_id = uuid.uuid4()
    existing_photo = _make_photo(photo_id, request_id, transfer_status="pending_upload")
    mock_upload_request_photo_querier.get_upload_request_photo_by_id.return_value = existing_photo
    mock_staged_upload_storage.stat_staging_object.return_value = None
    mock_upload_request_photo_querier.fail_upload_request_photo_transfer.return_value = _make_photo(
        photo_id, request_id, transfer_status="failed",
    )

    with pytest.raises(Exception):
        await upload_requests_service.confirm_direct_upload(
            photo_id=photo_id, requested_by=mock_staff_user,
        )

    mock_upload_request_photo_querier.fail_upload_request_photo_transfer.assert_awaited_once_with(id=photo_id)


@pytest.mark.asyncio
async def test_approve_request_blocked_when_photo_not_fully_uploaded(
    upload_requests_service,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_staff_user,
):
    request_id = uuid.uuid4()
    photo_id = uuid.uuid4()

    mock_upload_request_querier.get_upload_request_by_id.return_value = _make_request(
        request_id, uuid.uuid4(), mock_staff_user.id, None,
    )
    not_uploaded_photo = _make_photo(photo_id, request_id, transfer_status="pending_upload")

    async def _photos_iter(upload_request_id):
        yield not_uploaded_photo

    mock_upload_request_photo_querier.list_upload_request_photos_by_upload_request_id = _photos_iter

    with pytest.raises(Exception) as exc_info:
        await upload_requests_service.approve_request(
            request_id=request_id, approved_by=mock_staff_user,
        )
    assert "have not finished uploading" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resume_direct_group_reissues_urls_for_pending_and_failed_only(
    upload_requests_service,
    mock_upload_request_group_querier,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    group_id = uuid.uuid4()
    event_id = uuid.uuid4()
    request_id = uuid.uuid4()
    failed_photo_id = uuid.uuid4()
    uploaded_photo_id = uuid.uuid4()

    mock_upload_request_group_querier.get_upload_request_group_by_id.return_value = _make_group(
        group_id, event_id, mock_staff_user.id, total_photo_count=2, batch_count=1, failed_photo_count=1,
    )

    async def _requests_iter(group_id):
        yield _make_request(request_id, event_id, mock_staff_user.id, group_id, photo_count=2)

    mock_upload_request_querier.list_upload_requests_by_group_id = _requests_iter

    failed_photo = _make_photo(failed_photo_id, request_id, file_name="fail.jpg", staging_storage_key="staging/fail.jpg", transfer_status="failed")
    uploaded_photo = _make_photo(uploaded_photo_id, request_id, file_name="ok.jpg", staging_storage_key="staging/ok.jpg", transfer_status="uploaded")

    async def _photos_iter(dollar_1):
        for p in [failed_photo, uploaded_photo]:
            yield p

    mock_upload_request_photo_querier.list_upload_request_photos_by_upload_request_ids = _photos_iter
    mock_staged_upload_storage.create_presigned_staging_upload.return_value = ("staging/fail.jpg", "https://minio.local/resumed")
    mock_upload_request_photo_querier.reset_upload_request_photo_transfer_to_pending.return_value = _make_photo(
        failed_photo_id, request_id, file_name="fail.jpg", transfer_status="pending_upload",
    )

    results = await upload_requests_service.resume_direct_group(
        group_id=group_id, requested_by=mock_staff_user,
    )

    assert len(results) == 1
    photo, url = results[0]
    assert photo.id == failed_photo_id
    assert url == "https://minio.local/resumed"


@pytest.mark.asyncio
async def test_approve_request_publishes_drive_sync_event_for_direct_photo_only(
    upload_requests_service,
    mock_upload_request_querier,
    mock_upload_request_photo_querier,
    mock_photo_querier,
    mock_staged_upload_storage,
    mock_staff_user,
):
    from db.generated.models import Photo

    request_id = uuid.uuid4()
    event_id = uuid.uuid4()
    photo_id = uuid.uuid4()

    mock_upload_request_querier.get_upload_request_by_id.return_value = _make_request(
        request_id, event_id, mock_staff_user.id, None,
    )

    async def _photos_iter(upload_request_id):
        yield _make_photo(photo_id, request_id, transfer_status="uploaded", source="direct")

    mock_upload_request_photo_querier.list_upload_request_photos_by_upload_request_id = _photos_iter
    mock_staged_upload_storage.promote_to_final.return_value = "events/e1/p1.jpg"
    mock_photo_querier.create_photo.return_value = Photo(
        id=photo_id, event_id=event_id, uploaded_by=None, storage_key="events/e1/p1.jpg",
        taken_at=None, day_number=None, visibility="private", status="pending",
        created_at=datetime.now(timezone.utc), drive_file_id=None, drive_synced_at=None,
        source="direct", storage_cleaned_at=None,
    )
    mock_upload_request_photo_querier.update_upload_request_photo_approval.return_value = _make_photo(
        photo_id, request_id, source="direct", transfer_status="uploaded",
    )
    mock_upload_request_querier.approve_upload_request.return_value = _make_request(
        request_id, event_id, mock_staff_user.id, None,
    )

    with patch("app.service.upload_requests.NatsClient.publish") as mock_publish:
        await upload_requests_service.approve_request(
            request_id=request_id, approved_by=mock_staff_user,
        )

    published_subjects = [call.args[0] for call in mock_publish.call_args_list]
    from app.infra.nats import NatsSubjects
    assert NatsSubjects.PHOTO_DRIVE_SYNC_REQUESTED in published_subjects


@pytest.mark.asyncio
async def test_fail_direct_upload_marks_transfer_failed(
    upload_requests_service,
    mock_upload_request_photo_querier,
    mock_staff_user,
):
    photo_id = uuid.uuid4()
    request_id = uuid.uuid4()
    existing_photo = _make_photo(photo_id, request_id, transfer_status="pending_upload")
    mock_upload_request_photo_querier.get_upload_request_photo_by_id.return_value = existing_photo
    mock_upload_request_photo_querier.fail_upload_request_photo_transfer.return_value = _make_photo(
        photo_id, request_id, transfer_status="failed",
    )

    result = await upload_requests_service.fail_direct_upload(
        photo_id=photo_id, requested_by=mock_staff_user,
    )

    assert result.id == photo_id
    mock_upload_request_photo_querier.fail_upload_request_photo_transfer.assert_awaited_once_with(id=photo_id)
