from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class EventCreate(BaseModel):
    name: str
    event_date: datetime
    end_date: Optional[datetime] = None
    status: Optional[str] = "draft"

class JoinEventRequest(BaseModel):
    event_code: str
