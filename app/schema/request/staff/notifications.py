from uuid import UUID

from pydantic import BaseModel, Field


class MarkStaffNotificationsReadRequest(BaseModel):
    notification_ids: list[UUID] = Field(min_length=1, max_length=100)
