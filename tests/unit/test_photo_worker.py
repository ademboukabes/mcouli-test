import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.service.face_embedding import DetectedFace, FaceImagePayload
from app.worker.photo_worker.main import PhotoWorker
from app.worker.photo_worker.schema.event import PhotoProcessEvent
from db.generated import models


@pytest.fixture
def mock_pj_querier():
    querier = AsyncMock()
    job = models.ProcessingJob(
        id=uuid.uuid4(),
        photo_id=uuid.uuid4(),
        job_type="face_detection",
        status="pending",
        attempts=0,
        created_at=None,  # type: ignore
        completed_at=None,  # type: ignore
    )
    querier.create_processing_job.return_value = job
    querier.update_processing_job_status.return_value = job
    return querier


@pytest.fixture
def mock_photo_querier():
    querier = AsyncMock()
    return querier


@pytest.fixture
def mock_photo_face_querier():
    querier = AsyncMock()
    approval = MagicMock()
    approval.user_id = uuid.uuid4()
    approval.photo_id = uuid.uuid4()
    querier.insert_photo_face_with_approval.return_value = approval
    return querier


@pytest.fixture
def mock_face_service():
    service = AsyncMock()
    return service


@pytest.fixture
def mock_single_face_service():
    service = AsyncMock()
    return service


@pytest.fixture
def mock_notification_service():
    service = AsyncMock()
    return service


@pytest.fixture
def photo_worker(
    mock_face_service,
    mock_single_face_service,
    mock_notification_service,
    mock_photo_face_querier,
    mock_photo_querier,
    mock_pj_querier,
):
    conn = AsyncMock()
    return PhotoWorker(
        conn=conn,
        face_embedding_service=mock_face_service,
        single_face_service=mock_single_face_service,
        user_notification_service=mock_notification_service,
        photo_face_querier=mock_photo_face_querier,
        photo_querier=mock_photo_querier,
        processing_job_querier=mock_pj_querier,
    )


@pytest.fixture
def sample_event():
    return PhotoProcessEvent(photo_id=uuid.uuid4(), image_ref="minio://images/test.jpg")


@pytest.mark.asyncio
async def test_handle_message_success_no_faces(
    photo_worker, sample_event, mock_face_service, mock_pj_querier, mock_photo_querier
):
    photo_worker._load_image = AsyncMock(
        return_value=FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"data"
        )
    )
    mock_face_service.detect_faces.return_value = []

    with patch("app.worker.photo_worker.main.NatsClient.js_publish") as mock_publish:
        await photo_worker.handle_message(
            sample_event.model_dump_json().encode("utf-8")
        )

        mock_pj_querier.create_processing_job.assert_called_once()
        mock_pj_querier.update_processing_job_status.assert_any_call(
            id=mock_pj_querier.create_processing_job.return_value.id, status="completed"
        )
        mock_photo_querier.update_photo_status.assert_called_once_with(
            id=sample_event.photo_id, status="approved"
        )
        mock_photo_querier.update_photo_visibility.assert_called_once_with(
            id=sample_event.photo_id, visibility="public"
        )
        # photo_worker no longer schedules immediate MinIO cleanup — that's
        # now threshold-based (event_lifecycle worker, gated on event.end_date
        # + Drive sync confirmation for direct uploads).
        mock_publish.assert_not_called()


@pytest.mark.asyncio
async def test_handle_message_success_single_face(
    photo_worker,
    sample_event,
    mock_face_service,
    mock_single_face_service,
    mock_pj_querier,
):
    photo_worker._load_image = AsyncMock(
        return_value=FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"data"
        )
    )
    face = DetectedFace(bbox=(0, 0, 100, 100), embedding=[0.1] * 512)
    mock_face_service.detect_faces.return_value = [face]

    with patch("app.worker.photo_worker.main.NatsClient.js_publish") as mock_publish:
        await photo_worker.handle_message(
            sample_event.model_dump_json().encode("utf-8")
        )

        mock_pj_querier.update_processing_job_status.assert_any_call(
            id=mock_pj_querier.create_processing_job.return_value.id, status="completed"
        )
        mock_single_face_service.process_detected_face.assert_called_once()
        # Only the audit event — cleanup is no longer scheduled by photo_worker.
        assert mock_publish.call_count == 1


@pytest.mark.asyncio
async def test_handle_message_success_group_face(
    photo_worker,
    sample_event,
    mock_face_service,
    mock_photo_face_querier,
    mock_notification_service,
    mock_pj_querier,
):
    photo_worker._load_image = AsyncMock(
        return_value=FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"data"
        )
    )
    face1 = DetectedFace(bbox=(0, 0, 100, 100), embedding=[0.1] * 512)
    face2 = DetectedFace(bbox=(100, 100, 200, 200), embedding=[0.2] * 512)
    mock_face_service.detect_faces.return_value = [face1, face2]

    with patch("app.worker.photo_worker.main.NatsClient.js_publish"):
        await photo_worker.handle_message(
            sample_event.model_dump_json().encode("utf-8")
        )

        mock_pj_querier.update_processing_job_status.assert_any_call(
            id=mock_pj_querier.create_processing_job.return_value.id, status="completed"
        )
        assert mock_photo_face_querier.insert_photo_face_with_approval.call_count == 2
        assert mock_notification_service.create_notification.call_count == 2


@pytest.mark.asyncio
async def test_handle_message_fails_on_minio_load(
    photo_worker, sample_event, mock_pj_querier
):
    photo_worker._load_image = AsyncMock(side_effect=Exception("MinIO error"))
    with pytest.raises(Exception, match="MinIO error"):
        await photo_worker.handle_message(
            sample_event.model_dump_json().encode("utf-8")
        )
    assert "failed" not in [
        call.kwargs.get("status")
        for call in mock_pj_querier.update_processing_job_status.call_args_list
    ]


@pytest.mark.asyncio
async def test_handle_message_fails_on_ai_detection(
    photo_worker, sample_event, mock_face_service, mock_pj_querier
):
    photo_worker._load_image = AsyncMock(
        return_value=FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"data"
        )
    )
    mock_face_service.detect_faces.side_effect = Exception("InsightFace out of memory")
    with pytest.raises(Exception, match="InsightFace out of memory"):
        await photo_worker.handle_message(
            sample_event.model_dump_json().encode("utf-8")
        )
    assert "failed" not in [
        call.kwargs.get("status")
        for call in mock_pj_querier.update_processing_job_status.call_args_list
    ]


@pytest.mark.asyncio
async def test_minio_retry_logic(photo_worker):
    with (
        patch("app.worker.photo_worker.main.Bucket.get") as mock_bucket_get,
        patch("app.worker.photo_worker.main.settings") as mock_settings,
        patch("app.worker.photo_worker.main.asyncio.sleep") as mock_sleep,
    ):
        mock_settings.MINIO_RETRY_ATTEMPTS = 3
        mock_settings.MINIO_RETRY_BASE_SECONDS = 0
        mock_bucket_get.side_effect = [
            Exception("Network error"),
            Exception("Timeout"),
            (b"image_data", "test.jpg", "image/jpeg"),
        ]

        payload = await photo_worker._load_image("minio://images/test.jpg")

        assert payload["bytes"] == b"image_data"
        assert mock_bucket_get.call_count == 3
        assert mock_sleep.call_count == 2
