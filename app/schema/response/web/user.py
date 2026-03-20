from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AdminUserSchema(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    blocked: bool
    created_at: datetime
    updated_at: datetime
