from __future__ import annotations

import asyncio
from typing import Sequence

from db.generated import devices as device_queries

from app.core.logger import logger
from app.worker.notification.firebase import (
    NotificationDeliveryError,
    init_firebase_app,
    send_notification,
)
from app.worker.notification.invalid_tokens import (
    DeviceInvalidationStore,
    InvalidTokenStore,
)
from app.worker.notification.notification_queue import NotificationQueue, NotificationQueueEntry
from app.worker.notification.rate_limiter import RateLimiter
from app.worker.notification.settings import NotifSetting
from app.infra.database import engine
from app.infra.redis import RedisClient
from app.infra.nats import NatsClient


async def process_entry(
    entry: NotificationQueueEntry,
    queue: NotificationQueue,
    invalid_tokens: InvalidTokenStore,
    invalid_devices: DeviceInvalidationStore,
) -> None:
    try:
        valid_tokens = [
        t for t in entry.notification.tokens
        if not await invalid_tokens.is_invalid(t)]
        
        
        if not valid_tokens:
            logger.info("All tokens are invalid, skipping notification")
            return
        
        notification = entry.notification.model_copy(update={"tokens": valid_tokens})
        
        
        await asyncio.to_thread(send_notification, notification)

    except NotificationDeliveryError as e:
        if e.invalid_tokens:
            await invalid_tokens.mark_invalid(e.invalid_tokens)
            await invalid_devices.mark_invalid(e.invalid_tokens)
        if e.failed_tokens:
            await retry(entry, queue, tokens=e.failed_tokens)

    except Exception:
        logger.exception("Unexpected error, retrying")
        await retry(entry, queue)



async def retry(
    entry: NotificationQueueEntry,
    queue: NotificationQueue,
    tokens: Sequence[str] | None = None,
) -> None:
    attempts = entry.attempts + 1

    if attempts >= NotifSetting.MAX_SEND_ATTEMPTS:
        logger.warning("Dropping notification after %d attempts", attempts)
        return

    notification = entry.notification

    if tokens is not None:
        notification = notification.model_copy(update={"tokens": list(tokens)})
        if not notification.tokens:
            return

    delay = min(NotifSetting.BASE_RETRY_DELAY * (2 ** attempts), 60)

    await asyncio.sleep(delay)
    await queue.enqueue_notification(notification, attempts=attempts)



async def handle_message(
    raw_payload: bytes | str,
    queue: NotificationQueue,
    invalid_tokens: InvalidTokenStore,
    invalid_devices: DeviceInvalidationStore,
) -> None:
    try:
        if isinstance(raw_payload, bytes):
            raw_payload = raw_payload.decode()

        entry = NotificationQueueEntry.model_validate_json(raw_payload)

    except Exception:
        logger.exception("Invalid message payload")
        return

    await process_entry(entry, queue, invalid_tokens, invalid_devices)



async def run_worker(
    queue: NotificationQueue,
    invalid_tokens: InvalidTokenStore,
    invalid_devices: DeviceInvalidationStore,
) -> None:
    logger.info("Notification worker started")

    semaphore = asyncio.Semaphore(NotifSetting.CONCURRENCY)
    rate_limiter = RateLimiter(NotifSetting.RATE_LIMIT, NotifSetting.RATE_PERIOD)

    async def wrapped_handler(msg: bytes | str) -> None:
        async with semaphore:
            await rate_limiter.acquire()
            await handle_message(msg, queue, invalid_tokens, invalid_devices)

    for subject in queue.priority_subjects():
        await NatsClient.subscribe(subject, wrapped_handler)

    await asyncio.Event().wait()



async def main() -> None:
    init_firebase_app(NotifSetting.firebase_credentials_path)

    await NatsClient.connect(
        host=NotifSetting.nats_host,
        port=NotifSetting.nats_port,
        user=NotifSetting.nats_user,
        password=NotifSetting.nats_password,
    )

    redis = RedisClient(
        host=NotifSetting.redis_host,
        port=NotifSetting.redis_port,
        password=NotifSetting.redis_password,
    )

    queue = NotificationQueue(settings=NotifSetting)
    invalid_tokens = InvalidTokenStore(redis)
    db_conn = await engine.connect()
    device_querier = device_queries.AsyncQuerier(db_conn)
    invalid_devices = DeviceInvalidationStore(device_querier)

    try:
        await run_worker(queue, invalid_tokens, invalid_devices)

    finally:
        await redis.close()
        await db_conn.close()
        logger.info("Worker shutdown")


if __name__ == "__main__":
    asyncio.run(main())
