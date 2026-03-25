from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.constant import AuditEventType
from app.core.exceptions import AppException
from db.generated import audit as audit_queries
from db.generated import user as user_queries
from db.generated.models import AuditEvent, User
from app.worker.audit.schema.audit import AuditEventMessage
from app.infra.nats import NatsClient, NatsSubjects


class AuditService:
    def __init__(
        self,
        audit_querier: audit_queries.AsyncQuerier,
        user_querier: user_queries.AsyncQuerier,
    ) -> None:
        self.audit_querier = audit_querier
        self.user_querier = user_querier

    _DEFAULT_CREATED_FROM = datetime(1970, 1, 1, tzinfo=timezone.utc)
    _DEFAULT_CREATED_TO = datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)

    async def record_event(
        self,
        *,
        event_type: AuditEventType,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        audit = await self.audit_querier.create_audit_event(
            event_type=event_type.value,
            user_id=user_id,
            metadata=metadata,
        )
        if audit is None:
            raise AppException.internal_error("Failed to persist audit event")
        return audit

    async def create_record(
        self,
        *,
        event_type: AuditEventType,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        description: str | None = None,
    ) -> None:
        message = AuditEventMessage(
            event_type=event_type,
            user_id=user_id,
            metadata=metadata,
            description=description,
        ).model_dump_json()
        await NatsClient.publish(NatsSubjects.AUDIT_EVENT, message.encode("utf-8"))

    async def list_audit_events(
        self,
        *,
        event_type: AuditEventType | None = None,
        user_id: UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[tuple[AuditEvent, User | None]]:
        params = audit_queries.ListAuditEventsParams(
            event_type.value if event_type else None,
            user_id,
            created_from or self._DEFAULT_CREATED_FROM,
            created_to or self._DEFAULT_CREATED_TO,
            limit,
            offset,
        )
        events: list[AuditEvent] = []
        async for event in self.audit_querier.list_audit_events(arg=params):
            events.append(event)

        user_ids = {event.user_id for event in events if event.user_id is not None}
        actors: dict[UUID, User] = {}
        for user_id in user_ids:
            user = await self.user_querier.get_user_by_id(id=user_id)
            if user:
                actors[user_id] = user
        return [
            (
                event,
                actors.get(event.user_id) if event.user_id is not None else None,
            )
            for event in events
        ]
