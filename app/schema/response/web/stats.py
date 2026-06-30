from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class AdminStatsResponse(BaseModel):
    active_events: int
    photos_uploaded: int
    processed_photos: int
    queue_size: int
    timestamp: datetime

class DriveUsageResponse(BaseModel):
    used_bytes: int
    total_bytes: int
    timestamp: datetime

class AlertItem(BaseModel):
    id: str
    type: str
    title: str
    message: str
    created_at: datetime
    is_read: bool
    is_actionable: Optional[bool] = False
    action_text: Optional[str] = None

class AlertResponse(BaseModel):
    alerts: List[AlertItem]
    unread_count: int
    timestamp: datetime

class ProcessingLoadResponse(BaseModel):
    completed: float
    processing: float
    queued: float
