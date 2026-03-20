
import asyncio
from typing import Any, Mapping

from app.core.logger import logger
from app.worker.notification.schema.notification import NotificationEventPayload
from firebase_admin import messaging as firebase_messaging


async def send_fcm_notification(payload: NotificationEventPayload) -> None:

    if firebase_messaging is None:
        logger.debug("Firebase Admin not installed; skipping FCM delivery")
        return

    device_info: Mapping[str, Any] | None = payload.device_info
    if device_info is None:
        logger.warning("Payload missing device_info, cannot send FCM message: %s", payload)
        return

    token = device_info.get("fcm_token")
    if not isinstance(token, str):
        logger.warning("Missing FCM token in device_info for payload %s", payload)
        return

    message = firebase_messaging.Message(
        token=token,
        notification=firebase_messaging.Notification(
            title=payload.title, body=payload.body
        ),
        data=payload.data or None,
    )

    try:
        await asyncio.to_thread(firebase_messaging.send, message)
        logger.info("FCM notification queued for user %s token %s", payload.user_id, token)
    except Exception as exc:
        logger.exception("FCM send failed for token %s: %s", token, exc)
