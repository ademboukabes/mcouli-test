from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DirectFileInputRequest(BaseModel):
    file_name: str
    mime_type: str
    size_bytes: int
    taken_at: Optional[datetime] = None
    day_number: Optional[int] = None
    visibility: str = "private"


class CreateDirectGroupRequest(BaseModel):
    event_id: UUID


class RegisterDirectBatchRequest(BaseModel):
    files: list[DirectFileInputRequest]
