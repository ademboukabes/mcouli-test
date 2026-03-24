from __future__ import annotations

import asyncio
from functools import partial
from typing import Sequence

from app.core.config import settings
from app.core.logger import logger
from app.infra.firebase import (
    NotificationDeliveryError,
    init_firebase_app,
    send_notification,
)
from app.infra.invalid_tokens import InvalidTokenStore
from app.infra.notification_queue import NotificationQueue, NotificationQueueEntry
from app.infra.redis import RedisClient
from app.infra.nats import NatsClient
from app.worker.notification.settings import NotifSettings, NotificationWorkerSettings


MAX_SEND_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 2


async def _process_loop(
    queue: NotificationQueue,
    invalid_tokens: InvalidTokenStore,
    pending: asyncio.PriorityQueue[tuple[int, NotificationQueueEntry]],
) -> None:
    while True:
        try:
            _, entry = await pending.get()
            await _process_entry(entry, queue, invalid_tokens)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Notification worker encountered unexpected error")
            await asyncio.sleep(RETRY_DELAY_SECONDS)


def _parse_entry(raw_payload: bytes | str) -> NotificationQueueEntry | None:
    if isinstance(raw_payload, bytes):
        raw_payload = raw_payload.decode("utf-8")
    try:
        return NotificationQueueEntry.model_validate_json(raw_payload)
    except Exception:
        logger.exception("Failed to deserialize notification entry")
        return None


async def _enqueue_from_nats(
    raw_payload: bytes | str,
    queue: NotificationQueue,
    pending: asyncio.PriorityQueue[tuple[int, NotificationQueueEntry]],
) -> None:
    entry = _parse_entry(raw_payload)
    if entry is None:
        return
    priority = entry.notification.priority
    index = queue.priority_index(priority)
    await pending.put((index, entry))


async def _subscribe(
    queue: NotificationQueue,
    pending: asyncio.PriorityQueue[tuple[int, NotificationQueueEntry]],
) -> None:
    subjects = queue.priority_subjects()
    for subject in subjects:
        handler = partial(_enqueue_from_nats, queue=queue, pending=pending)
        await NatsClient.subscribe(subject, handler)


async def _process_entry(
    entry: NotificationQueueEntry,
    queue: NotificationQueue,
    invalid_tokens: InvalidTokenStore,
) -> None:
    try:
        await asyncio.to_thread(send_notification, entry.notification)
    except NotificationDeliveryError as exc:
        await _handle_partial_failure(entry, invalid_tokens, queue, exc)
    except Exception:
        logger.exception("Failed to deliver notification, will retry")
        await _retry(entry, queue)


async def _handle_partial_failure(
    entry: NotificationQueueEntry,
    invalid_tokens: InvalidTokenStore,
    queue: NotificationQueue,
    error: NotificationDeliveryError,
) -> None:
    if error.invalid_tokens:
        await invalid_tokens.mark_invalid(error.invalid_tokens)
        logger.warning("Detected %d invalid tokens", len(error.invalid_tokens))
    if error.failed_tokens:
        await _retry(entry, queue, tokens=error.failed_tokens)


async def _retry(
    entry: NotificationQueueEntry,
    queue: NotificationQueue,
    tokens: Sequence[str] | None = None,
) -> None:
    attempts = entry.attempts + 1
    if attempts >= MAX_SEND_ATTEMPTS:
        logger.warning(
            "Dropping notification after %d attempts (tokens=%d)",
            attempts,
            len(tokens or entry.notification.tokens),
        )
        return
    notification = entry.notification
    if tokens is not None:
        notification = entry.notification.model_copy(update={"tokens": list(tokens)})
        if not notification.tokens:
            return
    await asyncio.sleep(RETRY_DELAY_SECONDS)
    await queue.enqueue(notification, attempts=attempts)
    logger.info("Requeued notification attempt=%d", attempts)


async def run_worker(queue: NotificationQueue, invalid_tokens: InvalidTokenStore) -> None:
    logger.info("Notification worker started")
    pending: asyncio.PriorityQueue[tuple[int, NotificationQueueEntry]] = (
        asyncio.PriorityQueue()
    )
    await _subscribe(queue, pending)
    try:
        await _process_loop(queue, invalid_tokens, pending)
    finally:
        logger.info("Notification worker shutting down")


def _setup_notification_queue() -> NotificationQueue:
    return NotificationQueue(settings=NotifSettings)


def _setup_redis() -> RedisClient:
    return RedisClient(
        host=NotifSettings.REDIS_HOST,
        port=NotifSettings.REDIS_PORT,
        password=NotifSettings.REDIS_PASSWORD,
    )


def _setup_invalid_token_store(redis_client: RedisClient) -> InvalidTokenStore:
    return InvalidTokenStore(redis_client.client)


async def _initialize_infrastructure() -> tuple[NotificationQueue, InvalidTokenStore]:
    init_firebase_app()
    await NatsClient.connect()
    redis_client = _setup_redis()
    queue = _setup_notification_queue()
    invalid_tokens = _setup_invalid_token_store(redis_client)
    return queue, invalid_tokens


async def main() -> None:
    queue, invalid_tokens = await _initialize_infrastructure()
    try:
        await run_worker(queue, invalid_tokens)
    except asyncio.CancelledError:
        logger.info("Notification worker cancelled")
    finally:
        logger.info("Notification worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
