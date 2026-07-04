import json
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, create_autospec

import pytest

_MOCKED_MODULES = (
    "db.generated.user",
    "app.worker.notification.settings",
    "app.worker.notification.notification_queue",
)
_original_modules = {name: sys.modules.get(name) for name in _MOCKED_MODULES}
for _name in _MOCKED_MODULES:
    sys.modules[_name] = MagicMock()

from app.service.face_embedding import DetectedFace, FaceEmbeddingService, FaceImagePayload  # noqa: E402
from app.service.face_match import SingleFaceMatchService  # noqa: E402
from app.service.user_notification import UserNotificationService  # noqa: E402
from app.worker.photo_worker.main import PhotoWorker  # noqa: E402
from app.worker.photo_worker.schema.event import PhotoProcessEvent  # noqa: E402
from db.generated import photo_faces as photo_face_queries  # noqa: E402

# Restore sys.modules so other test files importing these modules
# (e.g. db.generated.user) get the real thing, not this leaked mock.
for _name, _original in _original_modules.items():
    if _original is None:
        sys.modules.pop(_name, None)
    else:
        sys.modules[_name] = _original
        
# ── fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def conn() -> MagicMock:
    return MagicMock()


@pytest.fixture
def face_service() -> AsyncMock:
    return create_autospec(FaceEmbeddingService, instance=True)


@pytest.fixture
def single_face_service() -> AsyncMock:
    svc = create_autospec(SingleFaceMatchService, instance=True)
    svc.process_detected_face = AsyncMock()
    return svc


@pytest.fixture
def notification_service() -> AsyncMock:
    svc = MagicMock(spec=UserNotificationService)
    svc.create_notification = AsyncMock()
    return svc


@pytest.fixture
def photo_face_querier() -> AsyncMock:
    return create_autospec(photo_face_queries.AsyncQuerier, instance=True)


@pytest.fixture
def photo_querier() -> AsyncMock:
    from db.generated import photos as photo_queries_mod
    q = create_autospec(photo_queries_mod.AsyncQuerier, instance=True)
    q.update_photo_status = AsyncMock(return_value=None)
    q.update_photo_visibility = AsyncMock(return_value=None)
    return q


@pytest.fixture
def worker(
    conn: MagicMock,
    face_service: AsyncMock,
    single_face_service: AsyncMock,
    notification_service: AsyncMock,
    photo_face_querier: AsyncMock,
    photo_querier: AsyncMock,
) -> PhotoWorker:
    return PhotoWorker(
        conn=conn,
        face_embedding_service=face_service,
        single_face_service=single_face_service,
        user_notification_service=notification_service,
        photo_face_querier=photo_face_querier,
        photo_querier=photo_querier,
    )


@pytest.fixture
def event() -> PhotoProcessEvent:
    return PhotoProcessEvent(
        photo_id=uuid.uuid4(),
        image_ref="photos/test.jpg",
        event_id=uuid.uuid4(),
    )


def _make_face(embedding: list[float] | None = None) -> DetectedFace:
    return DetectedFace(
        embedding=embedding or [0.1] * 512,
        bbox=(10.0, 20.0, 100.0, 200.0),
    )


def _event_bytes(event: PhotoProcessEvent) -> bytes:
    return event.model_dump_json().encode()


# ── tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invalid_payload_is_skipped(worker: PhotoWorker) -> None:
    """Malformed JSON should be silently skipped."""
    await worker.handle_message(b"not json")
    # No exceptions raised


@pytest.mark.asyncio
async def test_no_faces_skips_processing(
    worker: PhotoWorker,
    face_service: AsyncMock,
    single_face_service: AsyncMock,
    photo_face_querier: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """If no faces detected, neither single nor group path runs."""
    face_service.detect_faces = AsyncMock(return_value=[])

    with patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    single_face_service.process_detected_face.assert_not_called()
    photo_face_querier.insert_photo_face_with_approval.assert_not_called()


@pytest.mark.asyncio
async def test_single_face_takes_single_path(
    worker: PhotoWorker,
    face_service: AsyncMock,
    single_face_service: AsyncMock,
    photo_face_querier: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """Exactly 1 face -> single face match path."""
    face_service.detect_faces = AsyncMock(return_value=[_make_face()])

    with patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    single_face_service.process_detected_face.assert_called_once()
    photo_face_querier.insert_photo_face_with_approval.assert_not_called()


@pytest.mark.asyncio
async def test_multiple_faces_takes_group_path(
    worker: PhotoWorker,
    face_service: AsyncMock,
    single_face_service: AsyncMock,
    photo_face_querier: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """Multiple faces -> group photo approval path."""
    faces = [_make_face([0.1] * 512), _make_face([0.2] * 512), _make_face([0.3] * 512)]
    face_service.detect_faces = AsyncMock(return_value=faces)
    photo_face_querier.insert_photo_face_with_approval = AsyncMock(return_value=None)

    with patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    single_face_service.process_detected_face.assert_not_called()
    assert photo_face_querier.insert_photo_face_with_approval.call_count == 3


@pytest.mark.asyncio
async def test_group_photo_sends_notification_on_match(
    worker: PhotoWorker,
    face_service: AsyncMock,
    notification_service: AsyncMock,
    photo_face_querier: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """When a group face matches a user, a notification is sent."""
    faces = [_make_face(), _make_face()]
    face_service.detect_faces = AsyncMock(return_value=faces)

    matched_approval = MagicMock()
    matched_approval.user_id = uuid.uuid4()
    matched_approval.photo_id = event.photo_id

    # First face matches, second doesn't
    photo_face_querier.insert_photo_face_with_approval = AsyncMock(
        side_effect=[matched_approval, None]
    )

    with patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    notification_service.create_notification.assert_called_once()
    call_kwargs = notification_service.create_notification.call_args.kwargs
    assert call_kwargs["type"] == "photo_approval"
    assert call_kwargs["user_id"] == matched_approval.user_id


@pytest.mark.asyncio
async def test_group_photo_stores_bbox(
    worker: PhotoWorker,
    face_service: AsyncMock,
    photo_face_querier: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """Group path should pass bbox JSON to the DB query."""
    face = _make_face()
    face_service.detect_faces = AsyncMock(return_value=[face, face])
    photo_face_querier.insert_photo_face_with_approval = AsyncMock(return_value=None)

    with patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    call_args = photo_face_querier.insert_photo_face_with_approval.call_args_list[0]
    params = call_args.args[0]
    bbox = json.loads(params.bbox)
    assert bbox == {"x1": 10.0, "y1": 20.0, "x2": 100.0, "y2": 200.0}


@pytest.mark.asyncio
async def test_single_face_passes_correct_bbox(
    worker: PhotoWorker,
    face_service: AsyncMock,
    single_face_service: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """Single path should construct BBoxPayload from detected face."""
    face = _make_face()
    face_service.detect_faces = AsyncMock(return_value=[face])

    with patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load:
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    call_args = single_face_service.process_detected_face.call_args
    bbox = call_args.args[2]
    assert bbox.x1 == 10.0
    assert bbox.y1 == 20.0
    assert bbox.x2 == 100.0
    assert bbox.y2 == 200.0


@pytest.mark.asyncio
async def test_image_load_failure_is_handled(
    worker: PhotoWorker,
    face_service: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """If image fetch fails, worker should not crash."""
    with patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load:
        mock_load.side_effect = RuntimeError("MinIO down")
        await worker.handle_message(_event_bytes(event))

    face_service.detect_faces.assert_not_called()


# ── cleanup scheduling tests ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_cleanup_scheduled_after_single_face(
    worker: PhotoWorker,
    face_service: AsyncMock,
    single_face_service: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """After single face processing, both audit and cleanup events should be published."""
    face_service.detect_faces = AsyncMock(return_value=[_make_face()])

    with (
        patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load,
        patch("app.worker.photo_worker.main.NatsClient") as mock_nats,
    ):
        mock_nats.publish = AsyncMock()
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    from app.infra.nats import NatsSubjects
    assert mock_nats.publish.call_count == 2
    audit_call = mock_nats.publish.call_args_list[0]
    assert audit_call.args[0] == NatsSubjects.AUDIT_EVENT
    cleanup_call = mock_nats.publish.call_args_list[1]
    assert cleanup_call.args[0] == NatsSubjects.FINAL_BUCKET_CLEANUP
    cleanup_payload = json.loads(cleanup_call.args[1])
    assert event.image_ref in cleanup_payload["storage_keys"]


@pytest.mark.asyncio
async def test_cleanup_scheduled_after_group_photo(
    worker: PhotoWorker,
    face_service: AsyncMock,
    photo_face_querier: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """After group photo processing, both audit and cleanup events should be published."""
    faces = [_make_face(), _make_face()]
    face_service.detect_faces = AsyncMock(return_value=faces)
    photo_face_querier.insert_photo_face_with_approval = AsyncMock(return_value=None)

    with (
        patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load,
        patch("app.worker.photo_worker.main.NatsClient") as mock_nats,
    ):
        mock_nats.publish = AsyncMock()
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    from app.infra.nats import NatsSubjects
    assert mock_nats.publish.call_count == 2
    cleanup_call = mock_nats.publish.call_args_list[1]
    assert cleanup_call.args[0] == NatsSubjects.FINAL_BUCKET_CLEANUP
    cleanup_payload = json.loads(cleanup_call.args[1])
    assert event.image_ref in cleanup_payload["storage_keys"]


@pytest.mark.asyncio
async def test_cleanup_scheduled_when_no_faces(
    worker: PhotoWorker,
    face_service: AsyncMock,
    event: PhotoProcessEvent,
) -> None:
    """Even if no faces detected, cleanup should still be scheduled."""
    face_service.detect_faces = AsyncMock(return_value=[])

    with (
        patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load,
        patch("app.worker.photo_worker.main.NatsClient") as mock_nats,
    ):
        mock_nats.publish = AsyncMock()
        mock_load.return_value = FaceImagePayload(
            filename="test.jpg", content_type="image/jpeg", bytes=b"img"
        )
        await worker.handle_message(_event_bytes(event))

    mock_nats.publish.assert_called_once()
    cleanup_payload = json.loads(mock_nats.publish.call_args.args[1])
    assert event.image_ref in cleanup_payload["storage_keys"]


@pytest.mark.asyncio
async def test_no_cleanup_on_image_load_failure(
    worker: PhotoWorker,
    event: PhotoProcessEvent,
) -> None:
    """If image fails to load, no cleanup should be scheduled."""
    with (
        patch.object(worker, "_load_image", new_callable=AsyncMock) as mock_load,
        patch("app.worker.photo_worker.main.NatsClient") as mock_nats,
    ):
        mock_nats.publish = AsyncMock()
        mock_load.side_effect = RuntimeError("MinIO down")
        await worker.handle_message(_event_bytes(event))

    mock_nats.publish.assert_not_called()
