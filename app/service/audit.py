from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.constant import AuditEventType
from app.core.exceptions import AppException
from db.generated import audit as audit_queries
from db.generated.models import AuditEvent


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
