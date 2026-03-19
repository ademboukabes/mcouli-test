import uuid

from pydantic import BaseModel


class WebAuthResponse(BaseModel):
    access_token: str
    user_id: uuid.UUID
    role: str

    class Config:
        from_attributes = True