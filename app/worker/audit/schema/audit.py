from typing import Any
from uuid import UUID
from pydantic import BaseModel
from app.core.constant import AuditEventType


class AuditEventMessage(BaseModel):
    event_type: AuditEventType
    user_id: UUID | None = None
    metadata: dict[str, Any] | None = None
    description: str | None = None
