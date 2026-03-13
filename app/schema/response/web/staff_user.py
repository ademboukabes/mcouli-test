from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StaffUserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    discord_id: str
    email: str | None
    role: str
    created_at: datetime
    updated_at: datetime
