from __future__ import annotations

import asyncio

from pydantic import ValidationError

from app.container import Container
from app.core.config import settings as app_settings
from app.core.logger import logger
from app.infra.database import engine
from app.infra.minio import Bucket, init_minio_client
from app.infra.nats import NatsClient
from app.infra.redis import RedisClient
from app.worker.upload_group_worker.schema.event import UploadGroupImportRequestedEvent
from app.worker.upload_group_worker.settings import settings


async def _handle_message(data: bytes) -> None:
    try:
        event = UploadGroupImportRequestedEvent.model_validate_json(data)
    except ValidationError as exc:
        logger.warning("Invalid upload group import payload: %s", exc)
        return

    async with engine.begin() as conn:
        container = Container(conn)
        await container.upload_requests_service.process_group_import(
            group_id=event.group_id,
            visibility=event.visibility,
            day_number=event.day_number,
        )


async def main() -> None:
    try:
        RedisClient.get_instance()
    except RuntimeError:
        RedisClient.init(
            host=app_settings.REDIS_HOST,
            port=app_settings.REDIS_PORT,
            password=app_settings.REDIS_PASSWORD,
        )

    await init_minio_client(
        minio_host=app_settings.MINIO_HOST,
        minio_port=app_settings.MINIO_API_PORT,
        minio_root_user=app_settings.MINIO_ROOT_USER,
        minio_root_password=app_settings.MINIO_ROOT_PASSWORD,
    )

    await NatsClient.connect()
    try:
        await NatsClient.js_subscribe(
            subject=settings.subject_enum,
            callback=_handle_message,
            stream_name=settings.stream_name,
            durable_name=settings.durable_name,
        )
        logger.info("UploadGroupWorker subscribed on %s", settings.subject)
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
    asyncio.run(main())
