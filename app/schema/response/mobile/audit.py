from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from db.generated.models import AuditEvent
from app.core.constant import AuditEventType


class AuditEventSchema(BaseModel):
    id: UUID
    event_type: AuditEventType
    user_id: UUID | None
    metadata: dict[str, Any] | None
    created_at: datetime

    @classmethod
    def from_model(cls, event: AuditEvent) -> "AuditEventSchema":
        return cls(
            id=event.id,
            event_type=AuditEventType(event.event_type),
            user_id=event.user_id,
            metadata=event.metadata,
            created_at=event.created_at,
        )


class AuditEventListResponse(BaseModel):
    items: list[AuditEventSchema]
