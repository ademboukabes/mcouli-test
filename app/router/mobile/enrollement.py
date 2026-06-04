import re
import uuid
from PIL import Image
from io import BytesIO
from typing import Annotated, List
import filetype
from fastapi import APIRouter, File, UploadFile,  Depends
from pydantic import BaseModel
from app.container import Container, get_container
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.core.exceptions import AppException
from app.core.constant import (
    IMAGE_ALLOWED_TYPES,
    MAX_ENROLL_IMAGES,
    MAX_IMAGE_SIZE,
    MIN_ENROLL_IMAGES,
    MIN_IMAGE_DIM,
    MAX_IMAGE_DIM,
)
from app.service.face_embedding import FaceImagePayload
from db.generated.models import User

class EnrollmentResponse(BaseModel):
    id: uuid.UUID
    
    class Config:
        from_attributes = True

router = APIRouter()

def _sanitise_filename(raw: str | None, extension: str) -> str:
    prefix = str(uuid.uuid4())
    if not raw:
        return f"{prefix}.{extension}"
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", raw)
    name = name.lstrip(".")[:128]
    return f"{prefix}_{name}"

def _validate_dimensions(contents: bytes) -> None:
    try:
        img = Image.open(BytesIO(contents))
        img.verify()
        w, h = img.size
    except Exception:
        raise AppException.image_format_error(
            "File could not be decoded as a valid image"
        )
    if w < MIN_IMAGE_DIM or h < MIN_IMAGE_DIM:
        raise AppException.bad_request(
            f"Image too small — minimum {MIN_IMAGE_DIM}x{MIN_IMAGE_DIM} px"
        )
    if w > MAX_IMAGE_DIM or h > MAX_IMAGE_DIM:
        raise AppException.bad_request(
            f"Image too large — maximum {MAX_IMAGE_DIM}x{MAX_IMAGE_DIM} px"
        )
    
@router.post("/enroll", response_model=EnrollmentResponse)

async def enroll_face(
   files: Annotated[
        List[UploadFile],
        File(
            description="Upload one or more face images",
            openapi_examples={
                "single_file": {
                    "summary": "One file example",
                    "description": "Example of uploading one file",
                    "value": "example.jpg"
                },
                "multiple_files": {
                    "summary": "Multiple files example",
                    "description": "Example of uploading multiple files",
                    "value": ["face1.png", "face2.png"]
                },
            },
        ),
    ],
    container: Container = Depends(get_container),
    user: MobileUserSchema = Depends(get_current_mobile_user),
) -> User:

    if not (MIN_ENROLL_IMAGES <= len(files) <= MAX_ENROLL_IMAGES):
        raise AppException.bad_request(
            f"You must upload between {MIN_ENROLL_IMAGES} and {MAX_ENROLL_IMAGES} images for enrollment."
        )


    image_payloads: list[FaceImagePayload] = []
    for file in files:
        contents = await read_limited(file, MAX_IMAGE_SIZE)

        kind = filetype.guess(contents)
        if kind is None or kind.mime not in IMAGE_ALLOWED_TYPES:
            raise AppException.image_format_error(
                f"Unsupported format. Allowed types: {', '.join(IMAGE_ALLOWED_TYPES)}"
            )
        
        _validate_dimensions(contents)

        payload: FaceImagePayload = FaceImagePayload(
            filename=_sanitise_filename(file.filename, kind.extension),
            content_type=kind.mime,
            bytes=contents,
        )

        image_payloads.append(payload)

    updated_user = await container.auth_service.add_embbed_user(
        user.user_id,
        image_payloads,
    )
    return EnrollmentResponse.model_validate(updated_user)

async def read_limited(file: UploadFile, limit: int) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = await file.read(65536)  
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise AppException.image_size_error(
                f"File exceeds maximum size of {limit} bytes"
            )
        chunks.append(chunk)
    return b"".join(chunks)