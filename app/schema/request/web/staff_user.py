from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


class StaffUserCreateRequest(BaseModel):
    password: str = Field(..., min_length=8)
    email: Optional[EmailStr]
    role: Literal["multi_team_lead", "multi"]


class StaffUserUpdateRequest(BaseModel):
    email: Optional[EmailStr]
    role: Literal["multi_team_lead", "multi"]

