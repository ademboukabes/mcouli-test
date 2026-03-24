from __future__ import annotations

from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.infra.nats import NatsClient
from app.schema.notification import NotificationPriority, PRIORITY_ORDER, UnifiedNotification
from app.worker.notification.settings import NotificationWorkerSettings


class NotificationQueueEntry(BaseModel):
    notification: UnifiedNotification
    attempts: int = Field(default=0, ge=0)

    model_config = ConfigDict(extra="forbid")


class NotificationQueue:
    def __init__(self, settings: NotificationWorkerSettings) -> None:
        self._settings = settings

    def _subject_for(self, priority: NotificationPriority) -> str:
        return self._settings.subject_for(priority)

    async def enqueue(self, notification: UnifiedNotification, attempts: int = 0) -> None:
        entry = NotificationQueueEntry(notification=notification, attempts=attempts)
        await self._publish(entry)

    async def enqueue_entry(self, entry: NotificationQueueEntry) -> None:
        await self._publish(entry)

    async def _publish(self, entry: NotificationQueueEntry) -> None:
        subject = self._subject_for(entry.notification.priority)
        payload = entry.model_dump_json().encode("utf-8")
        await NatsClient.publish(subject, payload)

    @staticmethod
    def priority_index(priority: NotificationPriority) -> int:
        return PRIORITY_ORDER.index(priority)

    def priority_subjects(self) -> Sequence[str]:
        return self._settings.priority_subjects()
