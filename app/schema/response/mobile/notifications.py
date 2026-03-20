from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from db.generated.models import Notification


class UserNotificationSchema(BaseModel):
    id: UUID
    type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, notification: Notification) -> "UserNotificationSchema":
        return cls(
            id=notification.id,
            type=notification.type,
            payload=notification.payload,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )


class UserNotificationListResponse(BaseModel):
    items: list[UserNotificationSchema]

    @classmethod
    def from_models(
        cls,
        notifications: list[Notification],
    ) -> "UserNotificationListResponse":
        return cls(items=[UserNotificationSchema.from_model(item) for item in notifications])
