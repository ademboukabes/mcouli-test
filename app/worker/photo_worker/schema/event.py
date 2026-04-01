from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class PhotoProcessEvent(BaseModel):
    photo_id: uuid.UUID
    image_ref: str
    event_id: uuid.UUID | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "allow"}
