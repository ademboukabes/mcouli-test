from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class AdminUserCreateRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    display_name: Optional[str] = None
    blocked: bool = False


class AdminUserUpdateRequest(BaseModel):
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    blocked: Optional[bool] = None
