from __future__ import annotations

from typing import Sequence

from pydantic import Field
from pydantic_settings import BaseSettings
from app.schema.notification import NotificationPriority, PRIORITY_ORDER


class NotificationWorkerSettings(BaseSettings):
    subject_prefix: str = Field("notifications.delivery")
    queue_group: str | None = Field(None)
    REDIS_HOST:str
    REDIS_PORT:int
    REDIS_PASSWORD:str

    class Config:
        env_prefix = "NOTIFICATIONS_"

    def subject_for(self, priority: NotificationPriority) -> str:
        return f"{self.subject_prefix}.{priority.value}"

    def priority_subjects(self) -> Sequence[str]:
        return [self.subject_for(priority) for priority in PRIORITY_ORDER]

NotifSettings = NotificationWorkerSettings() # type: ignore