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


class DriveItemSchema(BaseModel):
    id: str
    name: str
    mime_type: str
    size_bytes: int
    is_folder: bool


class DriveBrowseResponse(BaseModel):
    items: list[DriveItemSchema]


class GoogleDriveImportFileResult(BaseModel):
    drive_file_id: str
    original_file_name: str
    minio_bucket: str
    minio_object_name: str
    minio_object_path: str


class GoogleDriveImportResponse(BaseModel):
    files: list[GoogleDriveImportFileResult]
