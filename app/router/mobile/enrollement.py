from typing import Annotated, List
import filetype
from fastapi import APIRouter, File, UploadFile,  Depends

from app.container import Container, get_container
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.core.exceptions import AppException
from app.core.constant import (
    DEFAULT_CONTENT_TYPE,
    IMAGE_ALLOWED_TYPES,
    MAX_ENROLL_IMAGES,
    MAX_IMAGE_SIZE,
    MIN_ENROLL_IMAGES,
)
from app.service.face_embedding import FaceImagePayload
from db.generated.models import User

router = APIRouter()


@router.post("/enroll")
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
                f"File {file.filename} is not a valid image. Allowed types: {', '.join(IMAGE_ALLOWED_TYPES)}"
            )
        
        if len(contents) > MAX_IMAGE_SIZE:
            raise AppException.bad_request(
                f"File {file.filename} exceeds maximum size of {MAX_IMAGE_SIZE} bytes"
            )

        payload: FaceImagePayload = FaceImagePayload(
            filename=file.filename or "unknown",
            content_type=file.content_type or DEFAULT_CONTENT_TYPE,
            bytes=contents,
        )

        image_payloads.append(payload)

    return await container.auth_service.add_embbed_user(
        user.user_id,
        image_payloads,
    )

async def read_limited(file: UploadFile, limit: int) -> bytes:
    chunks = []
    total = 0
    while True:
        chunk = await file.read(65536)  
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise AppException.bad_request(
                f"File exceeds maximum size of {limit} bytes"
            )
        chunks.append(chunk)
    return b"".join(chunks)