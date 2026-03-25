from app.schema.notification import UnifiedNotification
from app.worker.notification.notification_queue import NotificationQueue
from app.worker.notification.settings import NotifSetting


class NotificationGatewayService:
    def __init__(self, queue: NotificationQueue | None = None) -> None:
        self._queue = queue or NotificationQueue(settings=NotifSetting)

    async def send_notification(self, notification: UnifiedNotification) -> None:
        await self._queue.enqueue_notification(notification)
