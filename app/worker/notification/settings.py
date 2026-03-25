from __future__ import annotations

from typing import Sequence

from pydantic import Field
from pydantic_settings import BaseSettings

from app.schema.internal.notification import NotificationPriority, PRIORITY_ORDER


class NotificationWorkerSettings(BaseSettings):
    subject_prefix: str = Field("notifications.delivery")
    queue_group: str | None = Field(None)
    redis_host: str = Field("localhost")
    redis_port: int = Field(6379)
    redis_password: str = Field("")
    nats_host: str = Field("localhost")
    nats_port: int = Field(4222)
    nats_user: str = Field("")
    nats_password: str = Field("")
    firebase_credentials_path: str | None = Field(None)
    MAX_SEND_ATTEMPTS = 5
    BASE_RETRY_DELAY = 2
    TTL_SECONDS = 30 * 24 * 3600
    CONCURRENCY = 10
    RATE_LIMIT = 50
    RATE_PERIOD = 1.0

    class Config:
        env_prefix = "NOTIFICATIONS_"

    def subject_for(self, priority: NotificationPriority) -> str:
        return f"{self.subject_prefix}.{priority.value}"

    def priority_subjects(self) -> Sequence[str]:
        return [self.subject_for(priority) for priority in PRIORITY_ORDER]

NotifSetting = NotificationWorkerSettings() # type: ignore
