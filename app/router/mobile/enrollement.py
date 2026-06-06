import re
import time
import uuid
from collections.abc import AsyncIterator
from io import BytesIO
from typing import Annotated, List

import filetype  # type: ignore[import-untyped]
import pillow_heif  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image
from pydantic import BaseModel

from app.container import Container, get_container
from app.core.constant import (
    ENROLL_IN_PROGRESS_TTL_SECONDS,
    AuditEventType,
    ENROLL_RATE_LIMIT_MAX,
    ENROLL_RATE_LIMIT_WINDOW,
    IMAGE_ALLOWED_TYPES,
    MAX_ENROLL_IMAGES,
    MAX_IMAGE_SIZE,
    MAX_IMAGE_DIM,
    MIN_ENROLL_IMAGES,
    MIN_IMAGE_DIM,
)
from app.core.exceptions import AppException
from app.core.logger import logger
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.service.face_embedding import FaceImagePayload


pillow_heif.register_heif_opener()


Image.MAX_IMAGE_PIXELS = MAX_IMAGE_DIM * MAX_IMAGE_DIM


class EnrollmentResponse(BaseModel):
    id: uuid.UUID

    model_config = {"from_attributes": True}


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
        w, h = img.size
    except Exception as e:
        raise AppException.image_format_error(
            "File could not be decoded as a valid image"
        ) from e

    max_pixels = Image.MAX_IMAGE_PIXELS

    if max_pixels is not None and w * h > max_pixels:
        raise AppException.bad_request(
            f"Image exceeds maximum allowed resolution of {max_pixels} total pixels."
        )

    try:
        img.load()
    except Exception as e:
        raise AppException.image_format_error(
            "File contains corrupted or incomplete pixel data"
        ) from e

    if w < MIN_IMAGE_DIM or h < MIN_IMAGE_DIM:
        raise AppException.bad_request(
            f"Image too small — minimum {MIN_IMAGE_DIM}x{MIN_IMAGE_DIM} px"
        )
    if w > MAX_IMAGE_DIM or h > MAX_IMAGE_DIM:
        raise AppException.bad_request(
            f"Image too large — maximum {MAX_IMAGE_DIM}x{MAX_IMAGE_DIM} px"
        )


async def read_limited(file: UploadFile, limit: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise AppException.bad_request(
                f"File exceeds maximum allowed size of {limit} bytes"
            )
        chunks.append(chunk)

    await file.seek(0)
    return b"".join(chunks)


@router.post("/enroll", response_model=EnrollmentResponse)
async def enroll_face(
    files: Annotated[
        List[UploadFile],
        File(
            description=(
                f"Between {MIN_ENROLL_IMAGES} and {MAX_ENROLL_IMAGES} face images "
                f"(JPEG, PNG, HEIC, or HEIF). "
                f"Each file must be under {MAX_IMAGE_SIZE // (1024 * 1024)} MB "
                f"and at least {MIN_IMAGE_DIM}x{MIN_IMAGE_DIM} px."
            ),
        ),
    ],
    container: Container = Depends(get_container),
    user: MobileUserSchema = Depends(get_current_mobile_user),
) -> EnrollmentResponse:
    start_time = time.perf_counter()
    image_count = len(files)
    lock_key: str | None = None
    lock_value: str | None = None
    lock_acquired = False

    async def image_payloads() -> AsyncIterator[FaceImagePayload]:
        for file in files:
            yield await _build_face_image_payload(file)

    try:
        await container.auth_service.check_rate_limit(
            redis=container.redis,
            key=f"rate:enroll:{user.user_id}",
            max_requests=ENROLL_RATE_LIMIT_MAX,
            window_seconds=ENROLL_RATE_LIMIT_WINDOW,
        )

        if not (MIN_ENROLL_IMAGES <= image_count <= MAX_ENROLL_IMAGES):
            raise AppException.bad_request(
                f"You must upload between {MIN_ENROLL_IMAGES} and "
                f"{MAX_ENROLL_IMAGES} images for enrollment."
            )

        lock_key = _enrollment_lock_key(user.user_id)
        lock_value = str(uuid.uuid4())
        lock_acquired = await container.redis.set(
            lock_key,
            lock_value,
            expire=ENROLL_IN_PROGRESS_TTL_SECONDS,
            nx=True,
        )
        if not lock_acquired:
            raise AppException.conflict(
                "Enrollment already in progress. Please wait for it to finish."
            )

        updated_user = await container.auth_service.add_embbed_user(
            user.user_id,
            image_payloads(),
        )
        await _record_enrollment_audit(
            container=container,
            user_id=user.user_id,
            image_count=image_count,
            outcome="success",
            duration_ms=int((time.perf_counter() - start_time) * 1000),
        )
        return EnrollmentResponse.model_validate(updated_user)
    except HTTPException as exc:
        await _record_enrollment_audit(
            container=container,
            user_id=user.user_id,
            image_count=image_count,
            outcome="failure",
            duration_ms=int((time.perf_counter() - start_time) * 1000),
            error_category=f"http_{exc.status_code}",
        )
        raise
    except Exception as e:
        await _record_enrollment_audit(
            container=container,
            user_id=user.user_id,
            image_count=image_count,
            outcome="failure",
            duration_ms=int((time.perf_counter() - start_time) * 1000),
            error_category="unexpected_error",
        )
        raise AppException.internal_error(
            "Enrollment failed due to an internal error"
        ) from e
    finally:
        if lock_acquired and lock_key is not None and lock_value is not None:
            await _release_enrollment_lock(
                container=container,
                lock_key=lock_key,
                lock_value=lock_value,
            )
