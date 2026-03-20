import asyncio

from apns2.client import APNsClient
from apns2.payload import Payload as APNPayload, PayloadAlert

from app.core.logger import logger
from app.worker.notification.schema.notification import (
    MobileDeviceInfo,
    NotificationEventPayload,
)
from app.worker.notification.settings import settings


async def send_apn_notification(
    payload: NotificationEventPayload,
    device_info: MobileDeviceInfo,
) -> None:
    token = device_info.apn_token
    if not token:
        logger.warning("Missing APN token for user %s", payload.user_id)
        return
    alert = PayloadAlert(title=payload.title or "", body=payload.body)
    apn_payload = APNPayload(
        alert=alert,
        custom=payload.data or None,
    )
    client = APNsClient(
        credentials=settings.apn_certificate_path,
        use_sandbox=settings.apn_use_sandbox,
        use_alternative_port=settings.apn_use_alternative_port,
    )
    send_kwargs: dict[str, object] = {}
    if settings.apn_topic:
        send_kwargs["topic"] = settings.apn_topic
    try:
        await asyncio.to_thread(client.send_notification, token, apn_payload, **send_kwargs)
        logger.info("APN notification queued for user %s token %s", payload.user_id, token)
    except Exception as exc:
        logger.exception("APN send failed for token %s: %s", token, exc)
