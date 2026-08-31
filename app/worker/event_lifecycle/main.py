import asyncio
import json

from app.core.config import settings
from app.core.logger import logger
from app.infra.database import engine
from app.infra.nats import NatsClient, NatsSubjects
from db.generated import events as event_queries
from db.generated import photos as photo_queries


async def run_lifecycle_pass() -> None:
    async with engine.begin() as conn:
        querier = event_queries.AsyncQuerier(conn)

        activated = [event_id async for event_id in querier.activate_due_events()]
        if activated:
            logger.info(
                "event_lifecycle: activated %d event(s): %s", len(activated), activated
            )

        archived = [event_id async for event_id in querier.archive_ended_events()]
        if archived:
            logger.info(
                "event_lifecycle: archived %d event(s): %s", len(archived), archived
            )


async def run_storage_cleanup_pass() -> None:
    async with engine.begin() as conn:
        querier = photo_queries.AsyncQuerier(conn)

        due_photos = [
            photo
            async for photo in querier.list_photos_due_for_storage_cleanup(
                dollar_1=str(settings.PHOTO_STORAGE_RETENTION_DAYS_AFTER_EVENT_END)
            )
        ]
        if not due_photos:
            return

        cleaned = 0
        for photo in due_photos:
            try:
                await NatsClient.js_publish(
                    NatsSubjects.FINAL_BUCKET_CLEANUP,
                    json.dumps({"storage_keys": [photo.storage_key]}).encode("utf-8"),
                )
            except Exception as exc:
                logger.warning(
                    "storage_cleanup: failed to schedule cleanup for photo %s: %s",
                    photo.id,
                    exc,
                )
                continue
            marked = await querier.mark_photo_storage_cleaned(id=photo.id)
            if marked is not None:
                cleaned += 1

        logger.info("storage_cleanup: scheduled cleanup for %d photo(s)", cleaned)


async def main() -> None:
    logger.info(
        "Event lifecycle worker starting, poll_interval=%ds, storage_retention=%dd after event end",
        settings.EVENT_LIFECYCLE_POLL_INTERVAL_SECONDS,
        settings.PHOTO_STORAGE_RETENTION_DAYS_AFTER_EVENT_END,
    )
    while True:
        try:
            await run_lifecycle_pass()
        except Exception:
            logger.exception("event_lifecycle: pass failed")
        try:
            await run_storage_cleanup_pass()
        except Exception:
            logger.exception("storage_cleanup: pass failed")
        await asyncio.sleep(settings.EVENT_LIFECYCLE_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
