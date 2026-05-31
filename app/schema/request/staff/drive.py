from pydantic import BaseModel, Field


class GoogleDriveImportFileSelection(BaseModel):
    id: str
    name: str
    mime_type: str | None = Field(default=None, alias="mimeType")


class GoogleDriveImportRequest(BaseModel):
    files: list[GoogleDriveImportFileSelection] = Field(default_factory=list)
