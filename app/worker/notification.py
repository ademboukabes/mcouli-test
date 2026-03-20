"""Forward notifications coming from NATS to the configured push providers."""
from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from typing import Any

import sqlalchemy.ext.asyncio

from app.core.constant import NotificationChannel, NOTIFICATION_EVENT_SUBJECT
from app.core.logger import logger
from app.infra.database import engine
from app.infra.nats import NatsClient, NatsSubjects
from app.service.device import DeviceService
from db.generated import devices as device_queries
from db.generated.models import UserDevice

try:
    from firebase_admin import messaging as firebase_messaging 
except ImportError:  # pragma: no cover - optional dependency
    firebase_messaging = None

try:
    from apns2.client import APNsClient 
    from apns2.payload import Payload as APNPayload 
except ImportError:  # pragma: no cover - optional dependency
    APNsClient = None
    APNPayload = None

try:
    from pywebpush import webpush, WebPushException
except ImportError:  # pragma: no cover - optional dependency
    webpush = None
    WebPushException = None


@dataclasses.dataclass
class NotificationEventPayload:
    user_id: uuid.UUID
    channel: NotificationChannel
    title: str | None = None
    body: str | None = None
    data: dict[str, str] = dataclasses.field(default_factory=dict)
    device_info: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "NotificationEventPayload" | None:
        raw_user_id = payload.get("user_id")
        raw_channel = payload.get("channel")
        if not isinstance(raw_user_id, str) or not isinstance(raw_channel, str):
            logger.warning("Notification payload missing user_id or channel: %s", payload)
            return None
        try:
            user_id = uuid.UUID(raw_user_id)
        except ValueError as exc:
            logger.warning("Invalid user_id %s: %s", raw_user_id, exc)
            return None
        try:
            channel = NotificationChannel(raw_channel)
        except ValueError:
            logger.warning("Unsupported notification channel %s", raw_channel)
            return None

        data = payload.get("data")
        data_dict: dict[str, str] = {}
        if isinstance(data, dict):
            data_dict = {str(k): str(v) for k, v in data.items()}

        device_info = payload.get("device_info")
        if device_info is not None and not isinstance(device_info, dict):
            logger.warning("device_info must be an object: %s", payload)
            device_info = None

        metadata = payload.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            metadata = None

        return cls(
            user_id=user_id,
            channel=channel,
            title=payload.get("title"),
            body=payload.get("body"),
            data=data_dict,
            device_info=device_info,
            metadata=metadata,
        )


async def init_push_integrations() -> None:
    """Initialize third-party push clients and perform early validation."""
    if firebase_messaging:
        logger.info("Firebase Admin available for FCM delivery")
    else:
        logger.warning("Firebase Admin not installed; mobile push disabled")

    if APNsClient and APNPayload:
        logger.info("APNs client available for iOS delivery")
    else:
        logger.warning("APNs client not installed; iOS push disabled")

    if webpush:
        logger.info("pywebpush available for web push delivery")
    else:
        logger.warning("pywebpush not installed; web push disabled")


async def send_fcm_notification(device: UserDevice, payload: NotificationEventPayload) -> None:
    if firebase_messaging is None:
        logger.debug("Skipping FCM delivery because firebase_admin is not installed")
        return

    token = payload.device_info and payload.device_info.get("fcm_token")
    if token is None:
        logger.warning("Missing FCM token for payload %s", payload)
        return

    message = firebase_messaging.Message(
        token=token,
        notification=firebase_messaging.Notification(
            title=payload.title, body=payload.body
        ),
        data=payload.data,
    )

    try:
        firebase_messaging.send(message)
        logger.info("FCM notification queued for user %s token %s", payload.user_id, token)
    except Exception as exc:
        logger.exception("FCM send failed for token %s: %s", token, exc)


async def send_apn_notification(device: UserDevice, payload: NotificationEventPayload) -> None:
    if APNsClient is None or APNPayload is None:
        logger.debug("Skipping APN delivery because APNs client is unavailable")
        return

    token = payload.device_info and payload.device_info.get("apn_token")
    if token is None:
        logger.warning("Missing APN token for payload %s", payload)
        return

    apn_payload = APNPayload(alert={"title": payload.title, "body": payload.body})
    client = APNsClient(
        credentials="/path/to/certificate.pem",
        use_sandbox=True,
        use_alternative_port=False,
    )
    try:
        client.send_notification(token, apn_payload)
        logger.info("APN notification queued for user %s token %s", payload.user_id, token)
    except Exception as exc:
        logger.exception("APN send failed for %s: %s", token, exc)


async def send_web_push_notification(payload: NotificationEventPayload) -> None:
    if webpush is None or WebPushException is None:
        logger.debug("Skipping WebPush delivery because pywebpush is unavailable")
        return

    if not payload.device_info:
        logger.warning("Web notification missing subscription info: %s", payload)
        return

    subscription_info = payload.device_info
    vapid_claims = {"sub": "mailto:alerts@example.com"}
    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps({"title": payload.title, "body": payload.body, "data": payload.data}),
            vapid_private_key="/path/to/vapid-private.key",
            vapid_claims=vapid_claims,
        )
        logger.info("Web push queued for user %s", payload.user_id)
    except WebPushException as exc:
        logger.exception("Web push failed for user %s: %s", payload.user_id, exc)


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
        if payload.channel is NotificationChannel.MOBILE:
            await self._deliver_to_mobile(payload)
        elif payload.channel is NotificationChannel.WEB:
            await send_web_push_notification(payload)
        else:
            logger.warning("Unsupported channel %s for payload %s", payload.channel, payload)

    async def _deliver_to_mobile(self, payload: NotificationEventPayload) -> None:
        if self._device_service is None:
            logger.warning("Device service missing for mobile delivery")
            return
        devices, _ = await self._device_service.get_all_devices(user_id=payload.user_id)
        if not devices:
            logger.debug("No registered devices for user %s", payload.user_id)
            return
        for device in devices:
            device_type = (device.device_type or "").lower()
            if device_type == "ios":
                await send_apn_notification(device, payload)
            elif device_type == "android":
                await send_fcm_notification(device, payload)
            else:
                await send_fcm_notification(device, payload)


async def _parse_payload(raw_data: bytes) -> dict[str, Any] | None:
    try:
        return json.loads(raw_data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.error("Cannot parse notification payload: %s", exc)
        return None


async def _handle_event(worker: NotificationDeliveryWorker, raw_data: bytes) -> None:
    raw_payload = await _parse_payload(raw_data)
    if raw_payload is None:
        return
    payload = NotificationEventPayload.from_dict(raw_payload)
    if payload is None:
        return
    try:
        await worker.deliver(payload)
    except Exception:
        logger.exception("Failed to deliver notification payload %s", raw_payload)


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
