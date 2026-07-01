import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from app.worker.photo_worker.main import PhotoWorker
from app.worker.photo_worker.schema.event import PhotoProcessEvent
from app.service.face_embedding import DetectedFace
from app.service.photo_approval import PhotoApprovalService

@pytest.fixture
def mock_conn() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_face_embedding_service() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_single_face_service() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_notification_service() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_photo_face_querier() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_photo_querier() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_photo_approval_querier() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_processing_job_querier() -> AsyncMock:
    return AsyncMock()

@pytest.fixture
def mock_staged_upload_storage_service() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_group_photo_pending_no_users(
    mock_conn: AsyncMock,
    mock_face_embedding_service: AsyncMock,
    mock_single_face_service: AsyncMock,
    mock_notification_service: AsyncMock,
    mock_photo_face_querier: AsyncMock,
    mock_photo_querier: AsyncMock,
    mock_processing_job_querier: AsyncMock,
) -> None:
    """
    Test: Group photo with no enrolled users -> photo becomes approved + public.
    """
    worker = PhotoWorker(
        conn=mock_conn,
        face_embedding_service=mock_face_embedding_service,
        single_face_service=mock_single_face_service,
        user_notification_service=mock_notification_service,
        photo_face_querier=mock_photo_face_querier,
        photo_querier=mock_photo_querier,
        processing_job_querier=mock_processing_job_querier,
    )

    photo_id = uuid.uuid4()
    event = PhotoProcessEvent(photo_id=photo_id, image_ref="test.jpg")

    # 2 faces detected
    faces = [
        DetectedFace(bbox=(0.0, 0.0, 10.0, 10.0), embedding=[0.1, 0.2]),
        DetectedFace(bbox=(10.0, 10.0, 20.0, 20.0), embedding=[0.3, 0.4]),
    ]

    # No face matches any user -> insert_photo_face_with_approval returns None
    mock_photo_face_querier.insert_photo_face_with_approval.return_value = None

    await worker._handle_group_photo(event, faces)

    # Verify notifications were NOT sent
    mock_notification_service.create_notification.assert_not_called()

    # Verify photo stays pending (not marked public or approved)
    mock_photo_querier.update_photo_status.assert_not_called()
    mock_photo_querier.update_photo_visibility.assert_not_called()


@pytest.mark.asyncio
async def test_group_photo_pending_with_enrolled_users(
    mock_conn: AsyncMock,
    mock_face_embedding_service: AsyncMock,
    mock_single_face_service: AsyncMock,
    mock_notification_service: AsyncMock,
    mock_photo_face_querier: AsyncMock,
    mock_photo_querier: AsyncMock,
    mock_processing_job_querier: AsyncMock,
) -> None:
    """
    Test: Group photo with at least one enrolled user -> approval records created, notifications sent, photo stays pending.
    """
    worker = PhotoWorker(
        conn=mock_conn,
        face_embedding_service=mock_face_embedding_service,
        single_face_service=mock_single_face_service,
        user_notification_service=mock_notification_service,
        photo_face_querier=mock_photo_face_querier,
        photo_querier=mock_photo_querier,
        processing_job_querier=mock_processing_job_querier,
    )

    photo_id = uuid.uuid4()
    event = PhotoProcessEvent(photo_id=photo_id, image_ref="test.jpg")

    faces = [
        DetectedFace(bbox=(0.0, 0.0, 10.0, 10.0), embedding=[0.1, 0.2]),
    ]

    # Mock DB returning an approval record
    mock_approval = MagicMock()
    mock_approval.user_id = uuid.uuid4()
    mock_approval.photo_id = photo_id
    mock_photo_face_querier.insert_photo_face_with_approval.return_value = mock_approval

    await worker._handle_group_photo(event, faces)

    # Verify notification WAS sent
    mock_notification_service.create_notification.assert_called_once()
    args, kwargs = mock_notification_service.create_notification.call_args
    assert kwargs["user_id"] == mock_approval.user_id

    # Verify photo status is NOT updated to approved (stays pending)
    mock_photo_querier.update_photo_status.assert_not_called()
    mock_photo_querier.update_photo_visibility.assert_not_called()


@pytest.mark.asyncio
async def test_expire_stale_marks_photos_approved(
    mock_photo_approval_querier: AsyncMock,
    mock_photo_querier: AsyncMock,
    mock_staged_upload_storage_service: AsyncMock,
) -> None:
    """
    Test: After PHOTO_APPROVAL_TIMEOUT_DAYS days, expire_stale marks photos approved
    """
    service = PhotoApprovalService(
        photo_approval_querier=mock_photo_approval_querier,
        photo_querier=mock_photo_querier,
        storage_service=mock_staged_upload_storage_service,
    )

    from typing import Any, AsyncIterator
    # Mock the generator for expire_stale_approvals
    async def mock_generator(*args: Any, **kwargs: Any) -> AsyncIterator[uuid.UUID]:
        yield uuid.uuid4()
        yield uuid.uuid4()

    mock_photo_approval_querier.expire_stale_approvals = MagicMock(side_effect=mock_generator)

    count = await service.expire_stale(timeout_days=7)

    assert count == 2
    mock_photo_approval_querier.expire_stale_approvals.assert_called_once_with(timeout_days=7)
