import asyncio

from app.core.config import settings
from app.core.logger import logger
from app.infra.database import engine
from db.generated import events as event_queries


async def run_lifecycle_pass() -> None:
    async with engine.begin() as conn:
        querier = event_queries.AsyncQuerier(conn)

        activated = [event_id async for event_id in querier.activate_due_events()]
        if activated:
            logger.info("event_lifecycle: activated %d event(s): %s", len(activated), activated)

        archived = [event_id async for event_id in querier.archive_ended_events()]
        if archived:
            logger.info("event_lifecycle: archived %d event(s): %s", len(archived), archived)


async def main() -> None:
    logger.info(
        "Event lifecycle worker starting, poll_interval=%ds",
        settings.EVENT_LIFECYCLE_POLL_INTERVAL_SECONDS,
    )
    while True:
        try:
            await run_lifecycle_pass()
        except Exception:
            logger.exception("event_lifecycle: pass failed")
        await asyncio.sleep(settings.EVENT_LIFECYCLE_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
