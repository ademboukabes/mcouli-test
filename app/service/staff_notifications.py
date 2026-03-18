from typing import Any
import uuid

from app.core.exceptions import AppException
from db.generated import staff_notifications as staff_notification_queries
from db.generated.models import StaffNotification


class StaffNotificationsService:
    def __init__(
        self,
        notification_querier: staff_notification_queries.AsyncQuerier,
    ):
        self.notification_querier = notification_querier

    async def create_notification(
        self,
        *,
        staff_user_id: uuid.UUID,
        type: str,
        payload: dict[str, Any],
    ) -> StaffNotification:
        notification = await self.notification_querier.create_staff_notification(
            staff_user_id=staff_user_id,
            type=type,
            payload=payload,
        )
        if notification is None:
            raise AppException.internal_error("Failed to create staff notification")
        return notification

    async def list_notifications(
        self,
        *,
        staff_user_id: uuid.UUID,
    ) -> list[StaffNotification]:
        notifications: list[StaffNotification] = []
        async for notification in self.notification_querier.list_staff_notifications_by_staff_user_id(
            staff_user_id=staff_user_id
        ):
            notifications.append(notification)
        return notifications

    async def mark_as_read(
        self,
        *,
        notification_id: uuid.UUID,
        staff_user_id: uuid.UUID,
    ) -> StaffNotification:
        notification = await self.notification_querier.mark_staff_notification_as_read(
            id=notification_id,
            staff_user_id=staff_user_id,
        )
        if notification is None:
            raise AppException.not_found("Staff notification not found or already read")
        return notification

    async def mark_many_as_read(
        self,
        *,
        notification_ids: list[uuid.UUID],
        staff_user_id: uuid.UUID,
    ) -> list[StaffNotification]:
        notifications: list[StaffNotification] = []
        seen_notification_ids: set[uuid.UUID] = set()
        for notification_id in notification_ids:
            if notification_id in seen_notification_ids:
                continue
            seen_notification_ids.add(notification_id)
            notifications.append(
                await self.mark_as_read(
                    notification_id=notification_id,
                    staff_user_id=staff_user_id,
                )
            )
        return notifications
