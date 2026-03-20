import asyncio
from typing import Any, Mapping

from apns2.payload import PayloadAlert
from app.core.logger import logger
from app.worker.notification.schema.notification import NotificationEventPayload
from app.worker.notification.settings import settings
from apns2.client import APNsClient
from apns2.payload import Payload as APNPayload


async def send_apn_notification(payload: NotificationEventPayload) -> None:
   
    device_info: Mapping[str, Any] | None = payload.device_info
    if device_info is None:
        logger.warning("Payload missing device_info, cannot send APN message: %s", payload)
        return

    token = device_info.get("apn_token")
    if not isinstance(token, str):
        logger.warning("Missing APN token in device_info for payload %s", payload)
        return

    apn_payload = APNPayload(alert=PayloadAlert(title=))
    client = APNsClient(
        credentials=settings.apn_certificate_path,
        use_sandbox=settings.apn_use_sandbox,
        use_alternative_port=settings.apn_use_alternative_port,
    )

    send_args = (token, apn_payload)
    send_kwargs: dict[str, Any] = {}
    if settings.apn_topic is not None:
        send_kwargs["topic"] = settings.apn_topic

    try:
        await asyncio.to_thread(client.send_notification, *send_args, **send_kwargs)
        logger.info("APN notification queued for user %s token %s", payload.user_id, token)
    except Exception as exc:
        logger.exception("APN send failed for token %s: %s", token, exc)
