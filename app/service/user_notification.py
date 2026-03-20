from typing import Any
import uuid

from app.core.exceptions import AppException
from db.generated import notifications as notification_queries
from db.generated.models import Notification


class UserNotificationService:
    def __init__(
        self,
        notification_querier: notification_queries.AsyncQuerier,
    ) -> None:
        self.notification_querier = notification_querier

    async def create_notification(
        self,
        *,
        user_id: uuid.UUID,
        type: str,
        payload: dict[str, Any],
    ) -> Notification:
        notification = await self.notification_querier.create_notification(
            user_id=user_id,
            type=type,
            payload=payload,
        )
        if notification is None:
            raise AppException.internal_error("Failed to create user notification")
        return notification

    async def list_notifications(
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

    async def mark_as_read(
        self,
        *,
        notification_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Notification:
        notification = await self.notification_querier.mark_notification_as_read(
            id=notification_id,
            user_id=user_id,
        )
        if notification is None:
            raise AppException.not_found("Notification not found or already read")
        return notification

    async def mark_many_as_read(
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
            notifications.append(
                await self.mark_as_read(
                    notification_id=notification_id,
                    user_id=user_id,
                )
            )
        return notifications
