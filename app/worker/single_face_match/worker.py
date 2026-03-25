from __future__ import annotations

import asyncio

from app.container import Container
from app.core.config import settings
from app.core.logger import logger
from app.infra.database import engine
from app.infra.minio import Bucket, init_minio_client
from app.infra.nats import NatsClient, NatsSubjects
from app.infra.redis import RedisClient
from app.schema.dto.single_face_match import SingleFaceMatchJob
from app.service.single_face_match import SingleFaceMatchService


class SingleFaceMatchWorker:
    def __init__(self, service: SingleFaceMatchService) -> None:
        self.service = service

    async def handle_message(self, data: bytes) -> None:
        try:
            job = SingleFaceMatchJob.model_validate_json(data)
        except Exception as exc:
            logger.warning("Failed to parse single face match job: %s", exc)
            return

        try:
            await self.service.process_job(job)
        except Exception as exc:
            logger.exception("Failed to process single face match job: %s", exc)
            return


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
            face_embedding_service=container.face_embedding_service,
            photo_face_querier=container.photo_face_querier,
        )
        worker = SingleFaceMatchWorker(service)

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
