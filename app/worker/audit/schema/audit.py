"""Pydantic models for audit events."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Extra

from app.core.constant import AuditEventType


class AuditEventMessage(BaseModel):
    """Validates the payload sent to the audit worker over NATS."""

    event_type: AuditEventType
    user_id: UUID | None = None
    metadata: dict[str, Any] | None = None
    description: str | None = None

    class Config:
        extra = Extra.forbid
