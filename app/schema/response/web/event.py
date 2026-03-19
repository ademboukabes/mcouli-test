from pydantic import BaseModel, ConfigDict
from datetime import datetime
import uuid
from typing import Optional

class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_code: str
    event_date: datetime
    status: str
    created_by: uuid.UUID
    created_at: datetime
    archived_at: Optional[datetime] = None

class ParticipantResponse(BaseModel):
    """Data for a user who joined an event"""
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    user_email: str
    joined_at: datetime

class UserEventResponse(BaseModel):
    """Data for an event a user has joined"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_date: datetime
    status: str
    joined_at: datetime

class JoinEventResponse(BaseModel):
    """Confirmation of a successful join"""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_id: uuid.UUID
    user_id: uuid.UUID
    joined_at: datetime
