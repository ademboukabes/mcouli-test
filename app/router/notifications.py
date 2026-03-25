from fastapi import APIRouter, status

from app.core.logger import logger
from app.infra.notification_queue import NotificationQueue
from app.schema.notification import UnifiedNotification
from app.worker.notification.settings import NotifSetting


queue = NotificationQueue(settings=NotifSetting)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/enqueue", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_notification(notification: UnifiedNotification) -> dict[str, str]:
    await queue.enqueue(notification)
    logger.debug("Enqueued notification priority=%s tokens=%d", notification.priority, len(notification.tokens))
    return {"status": "queued"}
