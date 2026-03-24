from __future__ import annotations

from enum import Enum
from typing import Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NotificationPriority(str, Enum):
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class UnifiedNotification(BaseModel):
    title: str
    body: str
    data: dict[str, str] = Field(default_factory=dict)
    tokens: list[str]
    priority: NotificationPriority = NotificationPriority.NORMAL

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", "body", mode="before")
    def _normalize_text(cls, value: str) -> str:
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Text fields must not be empty")
        return normalized

    @field_validator("data", mode="before")
    def _normalize_data(cls, value: Mapping[str, object] | None) -> dict[str, str]:
        if value is None:
            return {}
        if not isinstance(value, Mapping):
            raise ValueError("Data must be a mapping")
        return {str(key): str(val) for key, val in value.items()}

    @field_validator("tokens", mode="before")
    def _normalize_tokens(cls, value: list[str] | tuple[str, ...]) -> list[str]:
        if not isinstance(value, (list, tuple)):
            raise ValueError("Tokens must be a list")
        cleaned = [str(token).strip() for token in value if str(token).strip()]
        if not cleaned:
            raise ValueError("At least one FCM token is required")
        return cleaned


PRIORITY_ORDER: tuple[NotificationPriority, ...] = (
    NotificationPriority.HIGH,
    NotificationPriority.NORMAL,
    NotificationPriority.LOW,
)
