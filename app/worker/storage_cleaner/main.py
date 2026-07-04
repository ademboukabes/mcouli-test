from __future__ import annotations

import asyncio
import json
import uuid
from typing import Iterable, Optional, Set

from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

from app.core.logger import logger
from app.infra.database import engine
from app.infra.nats import NatsClient
from app.service.staged_upload_storage import StagedUploadStorageService
from db.generated import upload_request_photos as upload_request_photo_queries
from app.worker.storage_cleaner.settings import settings


class FinalBucketCleanupPayload(BaseModel):
    storage_keys: list[str] = []
    photo_ids: list[str] | None = None
    ids: list[str] | None = None


storage_service = StagedUploadStorageService()


def _parse_payload(raw_data: bytes | str) -> Optional[FinalBucketCleanupPayload]:
    if isinstance(raw_data, bytes):
        try:
            raw_data = raw_data.decode("utf-8")
        except UnicodeDecodeError as exc:
            logger.warning("Final bucket cleanup payload failed to decode: %s", exc)
            return None

    try:
        parsed = json.loads(raw_data)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.warning("Final bucket cleanup payload is invalid JSON: %s", exc)
        return None

    if not isinstance(parsed, dict):
        return None

    try:
        return FinalBucketCleanupPayload.model_validate(parsed)
    except ValidationError as exc:
        logger.warning("Final bucket cleanup payload validation failed: %s", exc)
        return None


async def resolve_final_storage_keys(
    payload: FinalBucketCleanupPayload,
    querier: upload_request_photo_queries.AsyncQuerier,
) -> Set[str]:
    storage_keys: Set[str] = set(payload.storage_keys)
    photo_ids = payload.photo_ids or payload.ids
    if photo_ids:
        storage_keys.update(await _fetch_keys_for_ids(photo_ids, querier))
    return storage_keys


async def _fetch_keys_for_ids(
    photo_ids: Iterable[str],
    querier: upload_request_photo_queries.AsyncQuerier,
) -> Set[str]:
    keys: Set[str] = set()
    for raw_id in photo_ids:
        try:
            photo_id = uuid.UUID(raw_id)
        except ValueError:
            logger.warning("Skipping invalid photo id %s", raw_id)
            continue
        photo = await querier.get_upload_request_photo_by_id(id=photo_id)
        if photo is None:
            logger.warning("No upload request photo found for %s", raw_id)
            continue
        if photo.final_storage_key is None:
            logger.warning("Upload request photo %s has no final storage key", raw_id)
            continue
        keys.add(photo.final_storage_key)
    return keys


async def _delete_storage_key(storage_key: str) -> None:
    try:
        await storage_service.delete_storage_key(storage_key)
        logger.info("Removed finalized storage key %s", storage_key)
    except HTTPException as exc:
        detail = getattr(exc, "detail", exc)
        logger.warning("Skipping cleanup for %s: %s", storage_key, detail)
    except Exception:
        logger.exception("Failed to delete %s, worker will retry", storage_key)
        raise


async def _handle_cleanup_event(
    raw_payload: bytes | str,
    querier: upload_request_photo_queries.AsyncQuerier,
) -> None:
    payload = _parse_payload(raw_payload)
    if payload is None:
        return

    storage_keys = await resolve_final_storage_keys(payload, querier)
    if not storage_keys:
        logger.info("Final bucket cleanup event contained no storage keys")
        return

    logger.info(
        "Cleaning %d finalized storage objects from JetStream schedule",
        len(storage_keys),
    )

    for storage_key in storage_keys:
        await _delete_storage_key(storage_key)


async def main() -> None:
    await NatsClient.connect()
    try:
        async def _jetstream_handler(data: bytes | str) -> None:
            async with engine.begin() as conn:
                querier = upload_request_photo_queries.AsyncQuerier(conn)
                await _handle_cleanup_event(data, querier)

        await NatsClient.js_subscribe(
            subject=settings.subject_enum,
            callback=_jetstream_handler,
            stream_name=settings.stream_name,
            durable_name=settings.durable_name,
        )
        logger.info(
            "Storage cleaner listening on %s for %d-day window",
            settings.subject,
            settings.WINDOW_DAYS,
        )
        await asyncio.Event().wait()
    finally:
        await NatsClient.close()


if __name__ == "__main__":
    asyncio.run(main())