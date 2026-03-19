from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class StaffUserSchema(BaseModel):
    id: UUID
    email: str | None
    role: str
    created_at: datetime
    updated_at: datetime
