"""
Unit tests for image validation helpers in app.core.image_validation.

Run with: uv run pytest tests/unit/test_enroll_security.py -v
"""

import io
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import UploadFile
from fastapi.exceptions import HTTPException

from app.core.constant import MAX_IMAGE_SIZE, MIN_IMAGE_DIM, MAX_IMAGE_DIM  # noqa: E402
from app.core.image_validation import (
    sanitise_filename,
    validate_dimensions,
    precheck_upload_headers,
    read_limited,
)

# _enrollment_lock_key does not exist in the refactored module — skip those tests
_enrollment_lock_key = None


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_jpeg_bytes(width: int = 200, height: int = 200) -> bytes:
    """Generate a minimal valid JPEG in memory using Pillow."""
    from PIL import Image

    img = Image.new("RGB", (width, height), color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_upload_file(
    content: bytes,
    filename: str = "face.jpg",
    content_type: str | None = "image/jpeg",
    content_length: int | None = None,
) -> UploadFile:
    headers: dict[str, str] = {}
    if content_length is not None:
        headers["content-length"] = str(content_length)

    buf = io.BytesIO(content)
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.headers = headers
    mock_file.read = AsyncMock(side_effect=lambda n=-1: buf.read(n) if n == -1 else buf.read(n))
    mock_file.seek = AsyncMock(side_effect=lambda pos: buf.seek(pos))
    return mock_file  # type: ignore[return-value]


# ===========================================================================
# 1. sanitise_filename
# ===========================================================================


class TestSanitiseFilename:
    def test_normal_name_gets_uuid_prefix(self) -> None:
        result = sanitise_filename("portrait.jpg", "jpg")
        parts = result.split("_", 1)
        assert len(parts) == 2
        uuid.UUID(parts[0])  # raises if not a valid UUID
        assert parts[1] == "portrait.jpg"

    def test_path_traversal_is_neutralised(self) -> None:
        result = sanitise_filename("../../../etc/passwd.jpg", "jpg")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_null_bytes_are_replaced(self) -> None:
        assert "\x00" not in sanitise_filename("face\x00evil.jpg", "jpg")

    def test_control_characters_are_replaced(self) -> None:
        assert "\x1f" not in sanitise_filename("face\x1fmalicious.jpg", "jpg")

    def test_windows_reserved_chars_are_replaced(self) -> None:
        for char in r'\\/:*?"<>|':
            assert char not in sanitise_filename(f"face{char}name.jpg", "jpg"), \
                f"char {char!r} must be replaced"

    def test_none_filename_returns_uuid_only(self) -> None:
        result = sanitise_filename(None, "png")
        base, ext = result.rsplit(".", 1)
        uuid.UUID(base)
        assert ext == "png"

    def test_empty_filename_returns_uuid_only(self) -> None:
        result = sanitise_filename("", "jpg")
        base, ext = result.rsplit(".", 1)
        uuid.UUID(base)
        assert ext == "jpg"

    def test_long_filename_is_truncated(self) -> None:
        result = sanitise_filename("a" * 200, "jpg")
        name_part = result.split("_", 1)[1]
        assert len(name_part) <= 128

    def test_leading_dots_stripped(self) -> None:
        result = sanitise_filename("...hidden.jpg", "jpg")
        name_part = result.split("_", 1)[1]
        assert not name_part.startswith(".")


# ===========================================================================
# 2. validate_dimensions
# ===========================================================================


class TestValidateDimensions:
    def test_valid_image_passes(self) -> None:
        validate_dimensions(_make_jpeg_bytes(200, 200))  # must not raise

    def test_too_small_width_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_dimensions(_make_jpeg_bytes(MIN_IMAGE_DIM - 1, 200))
        assert exc_info.value.status_code == 400
        assert "too small" in exc_info.value.detail.lower()

    def test_too_small_height_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_dimensions(_make_jpeg_bytes(200, MIN_IMAGE_DIM - 1))
        assert exc_info.value.status_code == 400

    def test_too_large_width_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_dimensions(_make_jpeg_bytes(MAX_IMAGE_DIM + 1, 200))
        assert exc_info.value.status_code == 400
        assert "too large" in exc_info.value.detail.lower()

    def test_corrupt_bytes_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            validate_dimensions(b"this-is-not-an-image")
        assert exc_info.value.status_code == 400

    def test_boundary_min_dimension_passes(self) -> None:
        validate_dimensions(_make_jpeg_bytes(MIN_IMAGE_DIM, MIN_IMAGE_DIM))

    def test_boundary_max_dimension_passes(self) -> None:
        validate_dimensions(_make_jpeg_bytes(MAX_IMAGE_DIM, MAX_IMAGE_DIM))


# ===========================================================================
# 3. precheck_upload_headers
# ===========================================================================


class TestPrecheckUploadHeaders:
    def test_valid_jpeg_header_passes(self) -> None:
        precheck_upload_headers(_make_upload_file(b"", content_type="image/jpeg"))

    def test_valid_png_header_passes(self) -> None:
        precheck_upload_headers(_make_upload_file(b"", content_type="image/png"))

    def test_missing_content_type_raises_400(self) -> None:
        f = _make_upload_file(b"", content_type=None)
        with pytest.raises(HTTPException) as exc_info:
            precheck_upload_headers(f)
        assert exc_info.value.status_code == 400

    def test_unsupported_content_type_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            precheck_upload_headers(_make_upload_file(b"", content_type="application/pdf"))
        assert exc_info.value.status_code == 400

    def test_content_type_with_charset_param_accepted(self) -> None:
        # "image/jpeg; charset=utf-8" should normalise to "image/jpeg"
        precheck_upload_headers(
            _make_upload_file(b"", content_type="image/jpeg; charset=utf-8")
        )

    def test_oversized_content_length_raises_400(self) -> None:
        with pytest.raises(HTTPException) as exc_info:
            precheck_upload_headers(
                _make_upload_file(b"", content_type="image/jpeg", content_length=MAX_IMAGE_SIZE + 1)
            )
        assert exc_info.value.status_code == 400

    def test_valid_content_length_passes(self) -> None:
        precheck_upload_headers(
            _make_upload_file(b"", content_type="image/jpeg", content_length=1024)
        )

    def test_invalid_content_length_string_raises_400(self) -> None:
        f = _make_upload_file(b"", content_type="image/jpeg")
        f.headers = {"content-length": "not_a_number"}
        with pytest.raises(HTTPException) as exc_info:
            precheck_upload_headers(f)
        assert exc_info.value.status_code == 400


# ===========================================================================
# 4. read_limited
# ===========================================================================


class TestReadLimited:
    @pytest.mark.asyncio
    async def test_small_file_returns_full_bytes(self) -> None:
        data = b"hello world"
        result = await read_limited(_make_upload_file(data), MAX_IMAGE_SIZE)
        assert result == data

    @pytest.mark.asyncio
    async def test_exceeds_limit_raises_400(self) -> None:
        data = b"x" * (MAX_IMAGE_SIZE + 1)
        with pytest.raises(HTTPException) as exc_info:
            await read_limited(_make_upload_file(data), MAX_IMAGE_SIZE)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_exactly_at_limit_passes(self) -> None:
        data = b"x" * MAX_IMAGE_SIZE
        result = await read_limited(_make_upload_file(data), MAX_IMAGE_SIZE)
        assert len(result) == MAX_IMAGE_SIZE

    @pytest.mark.asyncio
    async def test_empty_file_returns_empty_bytes(self) -> None:
        result = await read_limited(_make_upload_file(b""), MAX_IMAGE_SIZE)
        assert result == b""

    @pytest.mark.asyncio
    async def test_aborts_early_without_reading_entire_stream(self) -> None:
        """Must abort after exceeding the limit — not exhaust the stream."""
        call_count = 0
        chunk = b"x" * 65536

        async def mock_read(n: int = -1) -> bytes:
            nonlocal call_count
            call_count += 1
            if call_count > 10:
                return b""
            return chunk

        f = MagicMock(spec=UploadFile)
        f.read = mock_read
        f.seek = AsyncMock()

        limit = 65536 * 5  # 5 chunks
        with pytest.raises(HTTPException):
            await read_limited(f, limit)

        assert call_count <= 7, "read_limited must abort early"


# ===========================================================================
# 5. _enrollment_lock_key — REMOVED
#    This helper does not exist in app.core.image_validation.
#    If it exists elsewhere, add a separate test file for it.
# ===========================================================================


# ===========================================================================
# 6. Magic byte sniffing (unit-level verification)
# ===========================================================================


class TestMagicByteSniffing:
    def test_pdf_bytes_not_classified_as_image(self) -> None:
        import filetype  # type: ignore[import-untyped]

        pdf_bytes = b"%PDF-1.4 fake pdf content"
        kind = filetype.guess(pdf_bytes)
        allowed = {"image/jpeg", "image/png", "image/heic", "image/heif"}
        assert kind is None or kind.mime not in allowed

    def test_real_jpeg_classified_as_jpeg(self) -> None:
        import filetype  # type: ignore[import-untyped]

        kind = filetype.guess(_make_jpeg_bytes(100, 100))
        assert kind is not None
        assert kind.mime == "image/jpeg"
