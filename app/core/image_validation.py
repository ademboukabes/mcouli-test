import re
import uuid
from dataclasses import dataclass
from io import BytesIO

import filetype  # type: ignore[import-untyped]
from fastapi import UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import Image

from app.core.constant import (
    IMAGE_ALLOWED_TYPES,
    MAX_IMAGE_DIM,
    MAX_IMAGE_SIZE,
    MIN_IMAGE_DIM,
)
from app.core.exceptions import AppException


@dataclass
class ImagePayload:
    filename: str
    content_type: str
    bytes: bytes


def sanitise_filename(raw: str | None, extension: str) -> str:
    prefix = str(uuid.uuid4())
    if not raw:
        return f"{prefix}.{extension}"
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", raw)
    name = name.replace("..", "_")
    name = name.lstrip(".")[:128]
    return f"{prefix}_{name}"


def validate_dimensions(contents: bytes) -> None:
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


def precheck_upload_headers(file: UploadFile) -> None:
    content_type = file.content_type
    if not content_type:
        raise AppException.image_format_error("Missing image Content-Type header")

    normalized_content_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    if normalized_content_type not in IMAGE_ALLOWED_TYPES:
        allowed = ", ".join(IMAGE_ALLOWED_TYPES)
        raise AppException.image_format_error(
            f"Unsupported Content-Type header. Allowed types: {allowed}"
        )

    content_length = file.headers.get("content-length")
    if content_length is None:
        return

    try:
        declared_size = int(content_length)
    except ValueError as exc:
        raise AppException.bad_request("Invalid image Content-Length header") from exc

    if declared_size > MAX_IMAGE_SIZE:
        raise AppException.bad_request(
            f"File exceeds maximum allowed size of {MAX_IMAGE_SIZE} bytes"
        )


async def build_image_payload(
    file: UploadFile, *, max_size: int = MAX_IMAGE_SIZE
) -> ImagePayload:
    precheck_upload_headers(file)
    contents = await read_limited(file, max_size)

    kind = filetype.guess(contents)
    if kind is None or kind.mime not in IMAGE_ALLOWED_TYPES:
        raise AppException.image_format_error(
            f"Unsupported format. Allowed types: {', '.join(IMAGE_ALLOWED_TYPES)}"
        )

    await run_in_threadpool(validate_dimensions, contents)

    return ImagePayload(
        filename=sanitise_filename(file.filename, kind.extension),
        content_type=kind.mime,
        bytes=contents,
    )
