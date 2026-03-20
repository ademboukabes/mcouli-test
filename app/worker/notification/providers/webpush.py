
import asyncio
import json

from app.core.logger import logger
from app.worker.notification.schema.notification import NotificationEventPayload
from app.worker.notification.settings import settings
from pywebpush import WebPushException, webpush


async def send_web_push_notification(payload: NotificationEventPayload) -> None:
  

    if not payload.device_info:
        logger.warning("Web notification missing subscription info: %s", payload)
        return

    if not settings.webpush_vapid_private_key:
        logger.warning("VAPID private key missing, cannot send web push")
        return

    subscription_info = payload.device_info
    vapid_claims = {"sub": settings.webpush_vapid_claims_subject}
    data = json.dumps({"title": payload.title, "body": payload.body, "data": payload.data})

    try:
        await asyncio.to_thread(
            webpush,
            subscription_info=subscription_info,
            data=data,
            vapid_private_key=settings.webpush_vapid_private_key,
            vapid_claims=vapid_claims,
        )
        logger.info("Web push queued for user %s", payload.user_id)
    except WebPushException as exc:
        logger.exception("Web push failed for user %s: %s", payload.user_id, exc)
