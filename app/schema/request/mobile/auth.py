from pydantic import BaseModel, EmailStr


class MobileAuthRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: str
    device_type: str
    device_id: str





class RefreshTokenRequest(BaseModel):
    refresh_token: str


