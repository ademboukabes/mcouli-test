from pydantic import BaseModel, EmailStr
from uuid import UUID


class MobileAuthRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: str
    device_type: str
    device_id: UUID





class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UpdateDeviceTokenRequest(BaseModel):
    device_id: UUID
    push_token: str


class InactivateDeviceRequest(BaseModel):
    device_id: UUID
