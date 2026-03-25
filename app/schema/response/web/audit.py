from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from db.generated.models import AuditEvent, User
from app.core.constant import AuditEventType
from app.schema.response.mobile.auth import UserSchema


class AuditActorSchema(UserSchema):
    display_name: str | None

    @classmethod
    def from_user(cls, user: User) -> "AuditActorSchema":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
        )


class AuditEventSchema(BaseModel):
    id: UUID
    event_type: AuditEventType
    metadata: dict[str, Any] | None
    created_at: datetime
    actor: AuditActorSchema | None

    @classmethod
    def from_model(
        cls,
        event: AuditEvent,
        actor: User | None,
    ) -> "AuditEventSchema":
        return cls(
            id=event.id,
            event_type=AuditEventType(event.event_type),
            metadata=event.metadata,
            created_at=event.created_at,
            actor=AuditActorSchema.from_user(actor) if actor else None,
        )


class AuditEventListResponse(BaseModel):
    items: list[AuditEventSchema]
