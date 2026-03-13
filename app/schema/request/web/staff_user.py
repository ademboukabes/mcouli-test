from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class StaffUserCreateRequest(BaseModel):
    discord_id: str = Field(..., min_length=1)
    email: Optional[EmailStr]
    role: Literal["admin", "multi"]


class StaffUserUpdateRequest(BaseModel):
    discord_id: str = Field(..., min_length=1)
    email: Optional[EmailStr]
    role: Literal["admin", "multi"]
