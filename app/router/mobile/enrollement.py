from fastapi import APIRouter, UploadFile, File, Depends

from app.container import Container, get_container
from app.deps.auth import MobileUserSchema, get_current_mobile_user
from app.core.exceptions import AppException
from app.core.constant import IMAGE_ALLOWED_TYPES, MAX_ENROLL_IMAGES, MAX_IMAGE_SIZE, MIN_ENROLL_IMAGES
from app.service.face_embedding import FaceImagePayload

router = APIRouter()


@router.post("/enroll")
async def enroll_face(
    files: list[UploadFile] = File(...),
    container: Container = Depends(get_container),
    user: MobileUserSchema = Depends(get_current_mobile_user),
) -> dict[str, object]:

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

        image_payloads.append({
            "filename": file.filename,
            "content_type": file.content_type,
            "bytes": contents,
        })

    return await container.auth_service.add_embbed_user(
        user.user_id,
        image_payloads,
    )
