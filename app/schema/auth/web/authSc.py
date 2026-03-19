from pydantic import BaseModel, EmailStr
import uuid

class WebAuthRequest(BaseModel):
    email: EmailStr
    password: str

class WebAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user_id: uuid.UUID
    role: str
    expires_in: int
