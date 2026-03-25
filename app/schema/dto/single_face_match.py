from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BBoxPayload(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class SingleFaceMatchJob(BaseModel):
    job_id: UUID = Field(default_factory=uuid4)
    photo_id: UUID
    face_index: int = 0
    image_ref: str
    bbox: BBoxPayload | None = None
    faces_detected: int | None = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "allow"}
