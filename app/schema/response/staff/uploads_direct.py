from uuid import UUID

from pydantic import BaseModel


class DirectUploadFileResponse(BaseModel):
    photo_id: UUID
    file_name: str
    upload_url: str


class RegisterDirectBatchResponse(BaseModel):
    group_id: UUID
    items: list[DirectUploadFileResponse]


class ResumeDirectGroupResponse(BaseModel):
    items: list[DirectUploadFileResponse]
