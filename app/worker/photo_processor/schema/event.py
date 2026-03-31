import uuid
from pydantic import BaseModel

class PhotoGroupProcessEvent(BaseModel) :
    photo_id: uuid.UUID
    storage_key: str
    event_id: uuid.UUID
