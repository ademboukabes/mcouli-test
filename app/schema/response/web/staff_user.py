from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StaffUserSchema(BaseModel):
    id: UUID
    email: str | None
    role: str
    device_id: UUID | None = None # Make it optional
    session_id: UUID | None = None
    created_at: datetime
    updated_at: datetime