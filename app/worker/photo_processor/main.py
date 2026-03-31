import asyncio
import json
from typing import Any
import sqlalchemy.ext.asyncio
from enum import Enum
from app.core.logger import logger
from app.infra.database import engine
from app.infra.nats import NatsClient, NatsSubjects
from app.infra.minio import ImageBucket
from app.service.face_embedding import FaceEmbeddingService, FaceImagePayload
from app.worker.photo_processor.schema.event import PhotoGroupProcessEvent
from db.generated import photo_faces as photo_face_queries
from db.generated.photo_faces import InsertPhotoFaceWithApprovalParams
from app.service.user_notification import UserNotificationService
from app.worker.notification.notification_queue import NotificationQueue
from app.worker.notification.settings import NotificationWorkerSettings
from app.schema.notification import UnifiedNotification, NotificationPriority
from db.generated import notifications as notification_queries

SIMILARITY_THRESHOLD = 0.5
STREAM_NAME = "photos"
DURABLE_NAME = "photo-group-processor"

class PhotoApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class PhotoGroupProcessWorker:
    def __init__(self) -> None:
        self._conn: sqlalchemy.ext.asyncio.AsyncConnection | None = None
        self._face_service: FaceEmbeddingService | None = None
        self._bucket: ImageBucket | None = None
        self._notification_service: UserNotificationService | None = None

    async def start(self) -> None:
        if self._conn is not None:
            return
        self._conn = await engine.connect()
        self._face_service = FaceEmbeddingService()
        self._bucket = ImageBucket(file_prefix="photos")
        notification_queue = NotificationQueue(NotificationWorkerSettings()) # type: ignore
        self._notification_service = UserNotificationService(
            notification_querier=notification_queries.AsyncQuerier(self._conn),
            notification_queue=notification_queue,
        )

    async def stop(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._face_service = None
            self._bucket = None
            self._notification_service = None

    async def process(self, event: PhotoGroupProcessEvent) -> None:
        if self._conn is None or self._face_service is None or self._bucket is None or self._notification_service is None:
            raise RuntimeError("Worker not started")

        # 1. fetch photo from MinIO
        image_bytes, filename, content_type = await self._bucket.get(event.storage_key)

        payload: FaceImagePayload = {
            "filename": filename,
            "content_type": content_type,
            "bytes": image_bytes,
        }

        # 2. get embeddings for all faces in the photo
        results = await self._face_service.compute_event_embedding([payload])
        face_embeddings = results.get(filename, [])

        if not face_embeddings:
            logger.info("No faces detected in photo %s", event.photo_id)
            return

        face_querier = photo_face_queries.AsyncQuerier(self._conn)

        for face_index, face_embedding in enumerate(face_embeddings):
         approval = await face_querier.insert_photo_face_with_approval(
           InsertPhotoFaceWithApprovalParams(
            photo_id=event.photo_id,
            face_index=face_index,
            column_3=face_embedding,
            face_embedding=SIMILARITY_THRESHOLD,
            bbox="",
            decision=PhotoApprovalDecision.PENDING.value,
            )
        )
         if approval is None:
                logger.info("No match found for face %s in photo %s", face_index, event.photo_id)
                continue
         assert approval is not None
    # notify the matched user
         await self._notification_service.create_notification(
            user_id=approval.user_id,
            type="photo_approval",
            payload={"photo_id": str(approval.photo_id)},
            notification=UnifiedNotification(
                title="You were found in a photo",
                body="Tap to review and approve or reject",
                data={
                    "photo_id": str(approval.photo_id),
                    "type": "photo_approval",
                },
                tokens=[],
                priority=NotificationPriority.NORMAL,
            ),
         )
        logger.info("Notified user %s for photo %s", approval.user_id, approval.photo_id) # type: ignore


def _parse_payload(raw_data: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_data.decode("utf-8"))
        if not isinstance(parsed, dict):
            logger.warning("Photo group process payload must be an object, got %s", type(parsed))
            return None
        return parsed
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Cannot parse photo group process payload: %s", exc)
        return None


async def _handle_event(worker: PhotoGroupProcessWorker, raw_data: bytes) -> None:
    parsed = _parse_payload(raw_data)
    if parsed is None:
        return
    try:
        event = PhotoGroupProcessEvent.model_validate(parsed)
    except Exception as exc:
        logger.warning("Photo group process payload validation failed: %s", exc)
        return
    try:
        await worker.process(event)
    except Exception:
        logger.exception("Failed to process photo group event for photo %s", parsed.get("photo_id"))


async def listen_nats_event(worker: PhotoGroupProcessWorker) -> None:
    await NatsClient.js_subscribe(
        subject=NatsSubjects.PHOTO_GROUP_PROCESS,
        callback=lambda data: _handle_event(worker, data),
        stream_name=STREAM_NAME,
        durable_name=DURABLE_NAME,
    )
    logger.info("Listening for photo group process events on %s", NatsSubjects.PHOTO_GROUP_PROCESS.value)


async def main() -> None:
    worker = PhotoGroupProcessWorker()
    await worker.start()
    await NatsClient.connect()
    try:
        await listen_nats_event(worker)
        await asyncio.Event().wait()
    finally:
        await worker.stop()
        await NatsClient.close()


if __name__ == "__main__":
    asyncio.run(main())
