import uuid

from pydantic import BaseModel, ConfigDict


class WebAuthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    access_token: str
    user_id: uuid.UUID
    role: str



