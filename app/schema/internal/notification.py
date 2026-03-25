from enum import Enum
from pydantic import BaseModel, ConfigDict, Field


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

PRIORITY_ORDER: tuple[NotificationPriority, ...] = (
    NotificationPriority.HIGH,
    NotificationPriority.NORMAL,
    NotificationPriority.LOW,
)
