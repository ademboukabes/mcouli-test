from __future__ import annotations

import asyncio
import json
from enum import Enum

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.container import Container
from app.core.config import settings
from app.core.constant import MINIO_URL_PREFIX
from app.core.logger import logger
from app.infra.database import engine
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME, init_minio_client
from app.infra.nats import NatsClient, NatsSubjects
from app.infra.redis import RedisClient
from app.schema.internal.notification import NotificationPriority, UnifiedNotification
from app.schema.internal.single_face_match import BBoxPayload
from app.service.face_embedding import DetectedFace, FaceEmbeddingService, FaceImagePayload
from app.service.face_match import SingleFaceMatchService
from app.service.user_notification import UserNotificationService
from app.worker.photo_worker.schema.event import PhotoProcessEvent
from app.worker.photo_worker.settings import settings as worker_settings
from db.generated import photo_faces as photo_face_queries
from db.generated import photos as photo_queries
from db.generated import processing_jobs as processing_job_queries
from db.generated.photo_faces import InsertPhotoFaceWithApprovalParams


class PhotoApprovalDecision(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class PhotoWorker:
    
    def __init__(
        self,
        conn: AsyncConnection,
        face_embedding_service: FaceEmbeddingService,
        single_face_service: SingleFaceMatchService,
        user_notification_service: UserNotificationService,
        photo_face_querier: photo_face_queries.AsyncQuerier,
        photo_querier: photo_queries.AsyncQuerier,
        processing_job_querier: processing_job_queries.AsyncQuerier | None = None,
    ) -> None:
        self._conn = conn
        self._face_service = face_embedding_service
        self._single_face_service = single_face_service
        self._notification_service = user_notification_service
        self._photo_face_querier = photo_face_querier
        self._photo_querier = photo_querier
        self._pj_querier = processing_job_querier

    async def handle_message(self, data: bytes) -> None:
        event = self._parse_event(data)
        if event is None:
            return

        job = await self._create_job(event)

        try:
            payload = await self._load_image(event.image_ref)
        except Exception as exc:
            logger.warning("Failed to load image for photo %s: %s", event.photo_id, exc)
            await self._update_job(job, "failed")
            return

        await self._update_job(job, "running")

        try:
            faces = await self._face_service.detect_faces(payload)
        except Exception as exc:
            logger.warning("Face detection failed for photo %s: %s", event.photo_id, exc)
            await self._update_job(job, "failed")
            return

        if not faces:
            logger.info("No faces detected in photo %s, marking as public", event.photo_id)
            await self._photo_querier.update_photo_status(id=event.photo_id, status="approved")
            await self._photo_querier.update_photo_visibility(id=event.photo_id, visibility="public")
            await self._update_job(job, "completed")
            await self._schedule_cleanup(event.image_ref)
            return

        if len(faces) == 1:
            await self._handle_single_face(event, faces[0])
        else:
            await self._handle_group_photo(event, faces)

        await self._update_job(job, "completed")
        await self._publish_audit(event, len(faces))
        await self._schedule_cleanup(event.image_ref)

   

    async def _handle_single_face(self, event: PhotoProcessEvent, face: DetectedFace) -> None:
        from app.schema.internal.single_face_match import SingleFaceMatchJob

        bbox = BBoxPayload(
            x1=float(face.bbox[0]),
            y1=float(face.bbox[1]),
            x2=float(face.bbox[2]),
            y2=float(face.bbox[3]),
        )

        job = SingleFaceMatchJob(
            photo_id=event.photo_id,
            face_index=0,
            image_ref=event.image_ref,
            bbox=bbox,
            faces_detected=1,
        )

        try:
            await self._single_face_service.process_detected_face(job, face.embedding, bbox)
        except Exception as exc:
            logger.exception("Single face match failed for photo %s: %s", event.photo_id, exc)

   

    async def _handle_group_photo(self, event: PhotoProcessEvent, faces: list[DetectedFace]) -> None:
        logger.info("Processing group photo %s with %d faces", event.photo_id, len(faces))

        for face_index, face in enumerate(faces):
            bbox_json = json.dumps({
                "x1": float(face.bbox[0]),
                "y1": float(face.bbox[1]),
                "x2": float(face.bbox[2]),
                "y2": float(face.bbox[3]),
            })

            embedding_literal = "[" + ", ".join(str(x) for x in face.embedding) + "]"

            try:
                approval = await self._photo_face_querier.insert_photo_face_with_approval(
                    InsertPhotoFaceWithApprovalParams(
                        photo_id=event.photo_id,
                        face_index=face_index,
                        column_3=embedding_literal,
                        face_embedding=worker_settings.similarity_threshold,
                        bbox=bbox_json,
                        decision=PhotoApprovalDecision.PENDING.value,
                    )
                )
            except (DBAPIError, SQLAlchemyError) as exc:
                logger.warning(
                    "DB error inserting face %d for photo %s: %s",
                    face_index, event.photo_id, exc,
                )
                continue

            if approval is None:
                logger.info("No match for face %d in photo %s", face_index, event.photo_id)
                continue

            try:
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
                logger.info("Notified user %s for group photo %s", approval.user_id, approval.photo_id)
            except Exception as exc:
                logger.warning(
                    "Failed to notify user %s for photo %s: %s",
                    approval.user_id, event.photo_id, exc,
                )


    async def _create_job(self, event: PhotoProcessEvent) -> object | None:
        if self._pj_querier is None:
            return None
        try:
            return await self._pj_querier.create_processing_job(
                photo_id=event.photo_id, job_type="face_detection",
            )
        except Exception as exc:
            logger.warning("Failed to create processing job for photo %s: %s", event.photo_id, exc)
            return None

    async def _update_job(self, job: object | None, status: str) -> None:
        if job is None or self._pj_querier is None:
            return
        try:
            await self._pj_querier.update_processing_job_status(id=job.id, status=status)  # type: ignore[union-attr]
        except Exception as exc:
            logger.warning("Failed to update processing job: %s", exc)

    @staticmethod
    async def _publish_audit(event: PhotoProcessEvent, faces_count: int) -> None:
        from app.core.constant import AuditEventType
        from app.worker.audit.schema.audit import AuditEventMessage
        msg = AuditEventMessage(
            event_type=AuditEventType.PHOTO_PROCESSED,
            metadata={"photo_id": str(event.photo_id), "faces_count": faces_count},
        )
        try:
            await NatsClient.publish(NatsSubjects.AUDIT_EVENT, msg.model_dump_json().encode("utf-8"))
        except Exception as exc:
            logger.warning("Failed to publish audit for photo %s: %s", event.photo_id, exc)

    @staticmethod
    async def _schedule_cleanup(image_ref: str) -> None:
        payload = json.dumps({"storage_keys": [image_ref]}).encode("utf-8")
        try:
            await NatsClient.publish(NatsSubjects.FINAL_BUCKET_CLEANUP, payload)
            logger.info("Scheduled cleanup for %s", image_ref)
        except Exception as exc:
            logger.warning("Failed to schedule cleanup for %s: %s", image_ref, exc)

    @staticmethod
    def _parse_event(raw_data: bytes) -> PhotoProcessEvent | None:
        try:
            return PhotoProcessEvent.model_validate_json(raw_data)
        except Exception as exc:
            logger.warning("Failed to parse photo process event: %s", exc)
            return None

    async def _load_image(self, image_ref: str) -> FaceImagePayload:
        bucket_name, object_name = self._parse_minio_ref(image_ref)
        bucket = Bucket(bucket_name, "")

        last_exc: Exception | None = None
        for attempt in range(1, settings.MINIO_RETRY_ATTEMPTS + 1):
            try:
                data, filename, content_type = await bucket.get(object_name)
                return FaceImagePayload(
                    filename=filename,
                    content_type=content_type,
                    bytes=data,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "MinIO fetch failed for %s (attempt %s/%s): %s",
                    object_name, attempt, settings.MINIO_RETRY_ATTEMPTS, exc,
                )
                if attempt < settings.MINIO_RETRY_ATTEMPTS:
                    await asyncio.sleep(settings.MINIO_RETRY_BASE_SECONDS * attempt)

        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _parse_minio_ref(image_ref: str) -> tuple[str, str]:
        if image_ref.startswith(MINIO_URL_PREFIX):
            raw = image_ref[len(MINIO_URL_PREFIX):]
            parts = raw.split("/", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise ValueError("Invalid MinIO image_ref format")
            return parts[0], parts[1]
        return IMAGES_BUCKET_NAME, image_ref


async def run_worker() -> None:
    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD,
    )
    RedisClient(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
    )

    async with engine.connect() as conn:
        container = Container(conn)

        single_face_service = SingleFaceMatchService(
            conn=conn,
            photo_face_querier=container.photo_face_querier,
            photo_querier=container.photo_querier,
            user_match_service=container.auth_service,
            user_notification_service=container.user_notifications_service,
        )

        worker = PhotoWorker(
            conn=conn,
            face_embedding_service=container.face_embedding_service,
            single_face_service=single_face_service,
            user_notification_service=container.user_notifications_service,
            photo_face_querier=container.photo_face_querier,
            photo_querier=container.photo_querier,
            processing_job_querier=container.processing_job_querier,
        )

        await NatsClient.js_subscribe(
            subject=NatsSubjects.PHOTO_PROCESS,
            callback=worker.handle_message,
            stream_name=worker_settings.stream_name,
            durable_name=worker_settings.durable_name,
        )

        logger.info("PhotoWorker subscribed on %s; waiting for jobs", NatsSubjects.PHOTO_PROCESS.value)
        try:
            await asyncio.Event().wait()
        finally:
            await _close_minio()
            await NatsClient.close()


async def _close_minio() -> None:
    client = getattr(Bucket, "client", None)
    if client is None:
        return
    close_session = getattr(client, "close_session", None)
    if close_session is None:
        return
    try:
        await close_session()
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(run_worker())
