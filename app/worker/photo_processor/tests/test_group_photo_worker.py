import sys
import pytest
import uuid
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

sys.modules['db.generated.user'] = MagicMock()
sys.modules['app.worker.notification.settings'] = MagicMock()
sys.modules['app.worker.notification.notification_queue'] = MagicMock()
sys.modules['app.service.user_notification'] = MagicMock()

from app.worker.photo_processor.main import PhotoGroupProcessWorker  # noqa: E402
from app.worker.photo_processor.schema.event import PhotoGroupProcessEvent  # noqa: E402

sys.modules['db.generated.user'] = MagicMock()



@pytest.fixture
def worker() -> Generator[PhotoGroupProcessWorker, None, None]:
    from unittest.mock import create_autospec
    from app.infra.minio import ImageBucket
    from app.service.face_embedding import FaceEmbeddingService

    w = PhotoGroupProcessWorker()
    w._conn = MagicMock()
    w._bucket = create_autospec(ImageBucket, instance=True)
    w._face_service = create_autospec(FaceEmbeddingService, instance=True)
    w._notification_service = MagicMock()
    w._notification_service.create_notification = AsyncMock()
    yield w


@pytest.fixture
def event() -> Generator[PhotoGroupProcessEvent, None, None]:
    yield PhotoGroupProcessEvent(
        photo_id=uuid.uuid4(),
        storage_key="photos/test.jpg",
        event_id=uuid.uuid4(),
    )


@pytest.mark.asyncio
async def test_no_faces_detected(worker: PhotoGroupProcessWorker, event: PhotoGroupProcessEvent) -> None:
    """If no faces detected, worker should exit early without creating any records."""
    assert worker._bucket is not None
    assert worker._face_service is not None
    worker._bucket.get = AsyncMock(return_value=(b"imagedata", "test.jpg", "image/jpeg"))  # type: ignore
    worker._face_service.compute_event_embedding = AsyncMock(return_value={"test.jpg": []})  # type: ignore

    with patch("app.worker.photo_processor.main.photo_face_queries") as mock_face_q:
        await worker.process(event)
        mock_face_q.AsyncQuerier.return_value.insert_photo_face_with_approval.assert_not_called()


@pytest.mark.asyncio
async def test_creates_photo_face_and_approval_for_matched_user(worker: PhotoGroupProcessWorker, event: PhotoGroupProcessEvent) -> None:
    """For each detected face, insert_photo_face_with_approval should be called once."""
    face_embedding = [0.1] * 512

    assert worker._bucket is not None
    assert worker._face_service is not None
    worker._bucket.get = AsyncMock(return_value=(b"imagedata", "test.jpg", "image/jpeg"))  # type: ignore
    worker._face_service.compute_event_embedding = AsyncMock(  # type: ignore
        return_value={"test.jpg": [face_embedding]}
    )

    with patch("app.worker.photo_processor.main.photo_face_queries") as mock_face_q:
        mock_face_q.AsyncQuerier.return_value.insert_photo_face_with_approval = AsyncMock(return_value=MagicMock())

        await worker.process(event)

        mock_face_q.AsyncQuerier.return_value.insert_photo_face_with_approval.assert_called_once()


@pytest.mark.asyncio
async def test_multiple_faces_calls_insert_for_each(worker: PhotoGroupProcessWorker, event: PhotoGroupProcessEvent) -> None:
    """For each detected face, insert_photo_face_with_approval should be called once per face."""
    face_embeddings = [[0.1] * 512, [0.2] * 512, [0.3] * 512]

    assert worker._bucket is not None
    assert worker._face_service is not None
    worker._bucket.get = AsyncMock(return_value=(b"imagedata", "test.jpg", "image/jpeg"))  # type: ignore
    worker._face_service.compute_event_embedding = AsyncMock(  # type: ignore
        return_value={"test.jpg": face_embeddings}
    )

    with patch("app.worker.photo_processor.main.photo_face_queries") as mock_face_q:
        mock_face_q.AsyncQuerier.return_value.insert_photo_face_with_approval = AsyncMock(return_value=MagicMock())

        await worker.process(event)

        assert mock_face_q.AsyncQuerier.return_value.insert_photo_face_with_approval.call_count == 3
