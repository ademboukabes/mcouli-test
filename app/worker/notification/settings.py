from __future__ import annotations

from typing import ClassVar, Sequence

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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
    MAX_SEND_ATTEMPTS: ClassVar[int] = 5
    BASE_RETRY_DELAY: ClassVar[int] = 2
    TTL_SECONDS: ClassVar[int] = 30 * 24 * 3600
    CONCURRENCY: ClassVar[int] = 10
    RATE_LIMIT: ClassVar[int] = 50
    RATE_PERIOD: ClassVar[float] = 1.0

    model_config = SettingsConfigDict(env_prefix="NOTIFICATIONS_")

    def subject_for(self, priority: NotificationPriority) -> str:
        return f"{self.subject_prefix}.{priority.value}"

    def priority_subjects(self) -> Sequence[str]:
        return [self.subject_for(priority) for priority in PRIORITY_ORDER]

NotifSetting = NotificationWorkerSettings()  # type: ignore
