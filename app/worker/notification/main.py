import asyncio
import json
from typing import Any
import sqlalchemy.ext.asyncio
from app.core.constant import NOTIFICATION_EVENT_SUBJECT, NotificationChannel
from app.core.logger import logger
from app.infra.database import engine
from app.infra.nats import NatsClient, NatsSubjects
from app.service.device import DeviceService
from db.generated import devices as device_queries
from app.worker.notification.providers.apn import send_apn_notification
from app.worker.notification.providers.fcm import     send_fcm_notification
from app.worker.notification.providers.webpush import     send_web_push_notification
from app.worker.notification.schema.notification import NotificationEventPayload


async def init_push_integrations() -> None:
    logger.info("Notification worker ready to deliver pushes")


class NotificationDeliveryWorker:
    def __init__(self) -> None:
        self._conn: sqlalchemy.ext.asyncio.AsyncConnection | None = None
        self._device_service: DeviceService | None = None

    async def start(self) -> None:
        if self._conn is not None:
            return
        self._conn = await engine.connect()
        self._device_service = DeviceService()
        self._device_service.init(device_querier=device_queries.AsyncQuerier(self._conn))

    async def stop(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None
            self._device_service = None

    async def deliver(self, payload: NotificationEventPayload) -> None:
        if payload.channel == NotificationChannel.MOBILE:
            await self._deliver_to_mobile(payload)
            return
        if payload.channel == NotificationChannel.WEB:
            await send_web_push_notification(payload)
            return
        logger.warning("Unhandled notification channel %s", payload.channel)

    async def _deliver_to_mobile(self, payload: NotificationEventPayload) -> None:
        if self._device_service is None:
            logger.warning("Device service unavailable for mobile delivery")
            return
        devices, _ = await self._device_service.get_all_devices(user_id=payload.user_id)
        if not devices:
            logger.debug("No devices registered for user %s", payload.user_id)
            return
        for device in devices:
            device_type = (device.device_type or "").lower()
            if device_type == "ios":
                await send_apn_notification(payload)
            else:
                await send_fcm_notification(payload)


def _parse_payload(raw_data: bytes) -> dict[str, Any] | None:
    try:
        parsed = json.loads(raw_data.decode("utf-8"))
        if not isinstance(parsed, dict):
            logger.warning("Notification payload must be an object, got %s", type(parsed))
            return None
        return parsed
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Cannot parse notification payload: %s", exc)
        return None


async def _handle_event(worker: NotificationDeliveryWorker, raw_data: Any) -> None:
    parsed = _parse_payload(raw_data)
    if parsed is None:
        return
    payload = NotificationEventPayload.from_mapping(parsed)
    if payload is None:
        return
    try:
        await worker.deliver(payload)
    except Exception:
        logger.exception("Failed to deliver payload for %s", parsed.get("user_id"))


async def listen_nats_event(worker: NotificationDeliveryWorker) -> None:
    await NatsClient.subscribe(
        NatsSubjects.NOTIFICATION_EVENT,
        lambda data: _handle_event(worker, data),
    )
    logger.info("Listening for notification events on %s", NOTIFICATION_EVENT_SUBJECT)


async def main() -> None:
    await init_push_integrations()
    worker = NotificationDeliveryWorker()
    await worker.start()
    await NatsClient.connect()
    try:
        await listen_nats_event(worker)
        await asyncio.Event().wait()
    finally:
        await worker.stop()
        await NatsClient.close()


if __name__ == "__main__":
    asyncio.run(main())
