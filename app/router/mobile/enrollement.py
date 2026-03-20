from typing import Annotated, List

from fastapi import APIRouter, File, UploadFile,  Depends

from app.container import Container, get_container
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.core.exceptions import AppException
from app.core.constant import IMAGE_ALLOWED_TYPES, MAX_ENROLL_IMAGES, MAX_IMAGE_SIZE, MIN_ENROLL_IMAGES
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
        if file.content_type not in IMAGE_ALLOWED_TYPES:
            raise AppException.image_format_error(
                f"File {file.filename} has unsupported format {file.content_type}"
            )

        contents = await file.read()
        if len(contents) > MAX_IMAGE_SIZE:
            raise AppException.bad_request(
                f"File {file.filename} exceeds maximum size of {MAX_IMAGE_SIZE} bytes"
            )

        payload: FaceImagePayload = FaceImagePayload(
            filename=file.filename or "unknown",
            content_type=file.content_type or "application/octet-stream",
            bytes=contents,
        )

        image_payloads.append(payload)

    return await container.auth_service.add_embbed_user(
        user.user_id,
        image_payloads,
    )
