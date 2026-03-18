from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from db.generated.models import StaffNotification


class StaffNotificationSchema(BaseModel):
    id: UUID
    type: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime

    @classmethod
    def from_model(cls, notification: StaffNotification) -> "StaffNotificationSchema":
        return cls(
            id=notification.id,
            type=notification.type,
            payload=notification.payload,
            read_at=notification.read_at,
            created_at=notification.created_at,
        )


class StaffNotificationListResponse(BaseModel):
    items: list[StaffNotificationSchema]

    @classmethod
    def from_models(
        cls,
        notifications: list[StaffNotification],
    ) -> "StaffNotificationListResponse":
        return cls(items=[StaffNotificationSchema.from_model(item) for item in notifications])
