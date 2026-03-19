from typing import TypedDict
from pydantic import BaseModel
import uuid

class StaffUserSchema(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    session_id: uuid.UUID
    
    class Config:
        from_attributes = True

class StaffJWTPayload(TypedDict):
    sub: str   
    role: str
    type: str  
    exp: int