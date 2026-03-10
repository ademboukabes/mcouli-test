from typing import List, Optional
from pydantic import BaseModel
import uuid
from datetime import datetime

class DeviceSchema(BaseModel):
    id: uuid.UUID
    device_name: str
    device_type: str
    totp_secret: str | None

class SessionSchema(BaseModel):
    session_id: uuid.UUID
    device_id: uuid.UUID
    last_active: datetime
    expires_at: datetime

class UserSchema(BaseModel):
    id: uuid.UUID
    email: str

class MeResponse(BaseModel):
    user: UserSchema
    devices: List[DeviceSchema]
    sessions: Optional[SessionSchema]
    


class MobileAuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    session_id: str 
    expires_in: int 
