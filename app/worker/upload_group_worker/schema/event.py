from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class UploadGroupImportRequestedEvent(BaseModel):
    group_id: uuid.UUID
    event_id: uuid.UUID
    folder_id: str
    requested_by: uuid.UUID
    visibility: str
    day_number: int | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
