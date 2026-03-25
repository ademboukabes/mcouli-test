from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.constant import AuditEventType
from app.core.exceptions import AppException
from db.generated import audit as audit_queries
from db.generated.models import AuditEvent
from app.worker.audit.schema.audit import AuditEventMessage
from app.infra.nats import NatsClient, NatsSubjects


class AuditService:
    def __init__(self, audit_querier: audit_queries.AsyncQuerier) -> None:
        self.audit_querier = audit_querier

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

    async def publish_event(
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
    ) -> list[AuditEvent]:
        params = audit_queries.ListAuditEventsParams(
            column_1=event_type.value if event_type else None,
            column_2=user_id,
            column_3=created_from,
            column_4=created_to,
            limit=limit,
            offset=offset,
        )
        events: list[AuditEvent] = []
        async for event in self.audit_querier.list_audit_events(arg=params):
            events.append(event)
        return events
