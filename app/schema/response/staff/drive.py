from datetime import datetime

from pydantic import BaseModel, Field


class GoogleDriveConnectResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleDriveConnectionStatusResponse(BaseModel):
    connected: bool
    google_email: str | None = None
    scopes: list[str] = Field(default_factory=list)
    connected_at: datetime | None = None
    token_expires_at: datetime | None = None


class GoogleDriveCallbackResponse(BaseModel):
    message: str
    google_email: str


class GoogleDriveDisconnectResponse(BaseModel):
    message: str
