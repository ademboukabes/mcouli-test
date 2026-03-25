from typing import Any
import uuid

from app.core.exceptions import AppException
from app.schema.internal.notification import UnifiedNotification
from app.worker.notification.notification_queue import NotificationQueue
from db.generated import notifications as notification_queries
from db.generated.models import Notification


class UserNotificationService:
    def __init__(
        self,
        notification_querier: notification_queries.AsyncQuerier,
        notification_queue: NotificationQueue,
    ) -> None:
        self.notification_querier = notification_querier
        self._notification_queue = notification_queue

    async def create_notification(
        self,
        *,
        user_id: uuid.UUID,
        type: str,
        payload: dict[str, Any],
        notification: UnifiedNotification | None = None,
    ) -> Notification:
        notification_record = await self.notification_querier.create_notification(
            user_id=user_id,
            type=type,
            payload=payload,
        )
        if notification_record is None:
            raise AppException.internal_error("Failed to create user notification")

        if notification is not None:
            await self._notification_queue.enqueue_notification(notification)

        return notification_record

    async def get_all_notifications(
        self,
        *,
        user_id: uuid.UUID,
    ) -> list[Notification]:
        notifications: list[Notification] = []
        async for notification in self.notification_querier.list_notifications_by_user_id(
            user_id=user_id
        ):
            notifications.append(notification)
        return notifications

    async def mark_notifications_as_read(
        self,
        *,
        notification_ids: list[uuid.UUID],
        user_id: uuid.UUID,
    ) -> list[Notification]:
        notifications: list[Notification] = []
        seen_notification_ids: set[uuid.UUID] = set()
        for notification_id in notification_ids:
            if notification_id in seen_notification_ids:
                continue
            seen_notification_ids.add(notification_id)
            notification = await self.notification_querier.mark_notification_as_read(
                id=notification_id,
                user_id=user_id,
            )
            if notification is None:
                raise AppException.not_found("Notification not found or already read")
            notifications.append(notification)
        return notifications
