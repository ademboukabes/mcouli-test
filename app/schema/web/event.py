from pydantic import BaseModel
from datetime import datetime
import uuid
from typing import Optional

class EventCreate(BaseModel):
    name: str
    qr_code_hash: str
    event_date: datetime

class EventResponse(BaseModel):
    id: uuid.UUID
    name: str
    qr_code_hash: str
    event_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True

class JoinEventRequest(BaseModel):
    user_id: uuid.UUID
    qr_code_hash: str  # The hash scanned from the QR code

class JoinEventResponse(BaseModel):
    event_id: uuid.UUID
    user_id: uuid.UUID
    joined_at: datetime

    class Config:
        from_attributes = True