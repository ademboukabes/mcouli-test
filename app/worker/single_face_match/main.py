from __future__ import annotations

import asyncio

from app.container import Container
from app.core.config import settings
from app.core.constant import MINIO_URL_PREFIX
from app.core.logger import logger
from app.infra.database import engine
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME, init_minio_client
from app.infra.nats import NatsClient, NatsSubjects
from app.infra.redis import RedisClient
from app.schema.internal.single_face_match import BBoxPayload, SingleFaceMatchJob
from app.service.face_embedding import FaceEmbeddingService, FaceImagePayload
from app.service.face_match import SingleFaceMatchService


class SingleFaceMatchWorker:
    def __init__(self, service: SingleFaceMatchService, face_embedding_service: FaceEmbeddingService) -> None:
        self.service = service
        self.face_embedding_service = face_embedding_service

    async def handle_message(self, data: bytes) -> None:
        try:
            job = SingleFaceMatchJob.model_validate_json(data)
        except Exception as exc:
            logger.warning("Failed to parse single face match job: %s", exc)
            return

        try:
            payload = await self._load_payload(job)
        except Exception as exc:
            logger.warning("Failed to load image payload for photo %s: %s", job.photo_id, exc)
            return

        try:
            faces = await self.face_embedding_service.detect_faces(payload)
        except Exception as exc:
            logger.warning("Face detection failed for photo %s: %s", job.photo_id, exc)
            return

        if len(faces) != 1:
            logger.info(
                "Skipping photo %s: detected %s faces (single-face worker)",
                job.photo_id,
                len(faces),
            )
            return

        face = faces[0]
        bbox_payload = BBoxPayload(
            x1=float(face.bbox[0]),
            y1=float(face.bbox[1]),
            x2=float(face.bbox[2]),
            y2=float(face.bbox[3]),
        )

        try:
            await self.service.process_detected_face(job, face.embedding, bbox_payload)
        except Exception as exc:
            logger.exception("Failed to process single face match job: %s", exc)
            return

    async def _load_payload(self, job: SingleFaceMatchJob) -> FaceImagePayload:
        if not job.image_ref:
            raise ValueError("Missing image_ref in event payload")

        bucket_name, object_name = self._parse_minio_ref(job.image_ref)
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
                    object_name,
                    attempt,
                    settings.MINIO_RETRY_ATTEMPTS,
                    exc,
                )
                if attempt < settings.MINIO_RETRY_ATTEMPTS:
                    await asyncio.sleep(settings.MINIO_RETRY_BASE_SECONDS * attempt)
        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _parse_minio_ref(image_ref: str) -> tuple[str, str]:
        if image_ref.startswith(MINIO_URL_PREFIX):
            raw = image_ref[len(MINIO_URL_PREFIX) :]
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
        service = SingleFaceMatchService(
            conn=conn,
            photo_face_querier=container.photo_face_querier,
            user_match_service=container.auth_service,
            user_notification_service=container.user_notifications_service,
        )
        worker = SingleFaceMatchWorker(service, container.face_embedding_service)

        await NatsClient.js_subscribe(
            subject=NatsSubjects.SINGLE_FACE_MATCH_REQUESTED,
            callback=worker.handle_message,
            stream_name=settings.NATS_SINGLE_FACE_MATCH_STREAM,
            durable_name=settings.NATS_SINGLE_FACE_MATCH_DURABLE,
        )

        logger.info("SingleFaceMatchWorker subscribed; waiting for jobs")
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
