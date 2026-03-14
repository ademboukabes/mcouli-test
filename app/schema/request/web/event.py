from pydantic import BaseModel
from datetime import datetime
import uuid
from typing import Optional

class EventCreate(BaseModel):
    name: str
    event_code: str  
    event_date: datetime
    status: Optional[str] = "draft"

class JoinEventRequest(BaseModel):
    user_id: uuid.UUID 
    event_code: str  
