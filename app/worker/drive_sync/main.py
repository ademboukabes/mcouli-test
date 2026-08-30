import asyncio
import json
import uuid
import socket


from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.logger import logger
from app.infra.database import engine
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME, init_minio_client
from app.infra.nats import NatsClient, NatsSubjects
from app.infra.redis import RedisClient
from app.service.staff_drive import StaffDriveService
from db.generated import events as event_queries
from db.generated import photos as photo_queries
from db.generated import staff_drive_connections as drive_queries
from db.generated import staff_user as staff_queries
from fastapi import HTTPException

# Force IPv4 to avoid "Network is unreachable" on systems without IPv6 routing
old_getaddrinfo = socket.getaddrinfo


def new_getaddrinfo(*args, **kwargs):  # type: ignore[no-untyped-def]
    args_list = list(args)
    # family is the 3rd positional argument
    if len(args_list) >= 3:
        if args_list[2] == 0:
            args_list[2] = socket.AF_INET
    elif "family" not in kwargs or kwargs["family"] == 0:
        kwargs["family"] = socket.AF_INET
    return old_getaddrinfo(*args_list, **kwargs)


socket.getaddrinfo = new_getaddrinfo


class PhotoDriveSyncEvent(BaseModel):
    photo_id: uuid.UUID
    event_id: uuid.UUID
    storage_key: str
    file_name: str
    mime_type: str


def _parse_payload(raw_data: bytes) -> PhotoDriveSyncEvent | None:
    try:
        parsed = json.loads(raw_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("drive_sync: cannot parse payload: %s", exc)
        return None
    if not isinstance(parsed, dict):
        return None
    try:
        return PhotoDriveSyncEvent.model_validate(parsed)
    except ValidationError as exc:
        logger.warning("drive_sync: payload validation failed: %s", exc)
        return None


async def _handle_event(raw_data: bytes) -> None:
    event = _parse_payload(raw_data)
    if event is None:
        return

    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    try:
        data, _, content_type = await bucket.get(event.storage_key)
    except HTTPException as exc:
        if exc.status_code == 404:
            logger.warning(
                "drive_sync: photo %s not found in storage (404), skipping sync to avoid retry loop",
                event.photo_id,
            )
            return
        logger.warning(
            "drive_sync: failed to read photo %s from storage: %s", event.photo_id, exc
        )
        raise
    except Exception as exc:
        logger.warning(
            "drive_sync: failed to read photo %s from storage: %s", event.photo_id, exc
        )
        raise

    async with engine.begin() as conn:
        staff_drive_service = StaffDriveService(
            staff_user_querier=staff_queries.AsyncQuerier(conn),
            drive_connection_querier=drive_queries.AsyncQuerier(conn),
            redis=RedisClient.get_instance(),
        )
        photo_querier = photo_queries.AsyncQuerier(conn)

        event_querier = event_queries.AsyncQuerier(conn)
        db_event = await event_querier.get_event_by_id(id=event.event_id)
        if db_event is None:
            logger.warning(
                "drive_sync: event %s not found for photo %s",
                event.event_id,
                event.photo_id,
            )
            return

        try:
            drive_file_id = await staff_drive_service.upload_to_system_drive(
                file_name=event.file_name,
                content_type=event.mime_type or content_type,
                data=data,
                event_id=event.event_id,
                event_name=db_event.name,
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                logger.warning(
                    "drive_sync: no active drive connection, pausing for 5 minutes before retry"
                )
                await asyncio.sleep(300)
            else:
                logger.warning(
                    "drive_sync: upload failed for photo %s (HTTP %s): %s",
                    event.photo_id,
                    exc.status_code,
                    exc,
                )
                await asyncio.sleep(15)  # Backoff to avoid fast retry loops
            raise
        except Exception as exc:
            logger.warning(
                "drive_sync: upload failed for photo %s: %s", event.photo_id, exc
            )
            await asyncio.sleep(15)  # Backoff to avoid fast retry loops
            raise

        synced = await photo_querier.mark_photo_drive_synced(
            id=event.photo_id,
            drive_file_id=drive_file_id,
        )
        if synced is None:
            logger.warning(
                "drive_sync: photo %s not found when recording sync", event.photo_id
            )
            return

    logger.info(
        "drive_sync: synced photo %s to Drive as %s", event.photo_id, drive_file_id
    )


async def main() -> None:
    logger.info("Drive sync worker starting")
    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD,
    )
    RedisClient.init(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        password=settings.REDIS_PASSWORD,
    )
    await NatsClient.connect()
    try:
        await NatsClient.js_subscribe(
            NatsSubjects.PHOTO_DRIVE_SYNC_REQUESTED, _handle_event
        )
        await asyncio.Event().wait()
    finally:
        await NatsClient.close()


if __name__ == "__main__":
    asyncio.run(main())
