import asyncio
from typing import Any

from app.core.logger import logger
from app.worker.notification.schema.notification import (
    MobileDeviceInfo,
    NotificationEventPayload,
)
from firebase_admin import messaging as firebase_messaging


async def send_fcm_notification(
    payload: NotificationEventPayload,
    device_info: MobileDeviceInfo,
) -> None:
    if firebase_messaging is None:
        logger.debug("Firebase Admin not installed; skipping FCM delivery")
        return
    token = device_info.fcm_token
    if not token:
        logger.warning("Missing FCM token for user %s", payload.user_id)
        return
    message = firebase_messaging.Message(
        token=token,
        notification=firebase_messaging.Notification(
            title=payload.title,
            body=payload.body,
        ),
        data=payload.data or None,
    )
    try:
        await asyncio.to_thread(firebase_messaging.send, message)
        logger.info("FCM notification queued for user %s token %s", payload.user_id, token)
    except Exception as exc:
        logger.exception("FCM send failed for token %s: %s", token, exc)
