import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from miniopy_async.error import S3Error

from app.infra.minio import (
    Bucket,
    ImageBucket,
    ObjectStat,
    WaSimBucket,
    init_minio_client,
)

@pytest.fixture
def mock_minio_client():
    client = AsyncMock()
    # Mocking standard methods
    client.put_object = AsyncMock()

    mock_get_response = AsyncMock()
    mock_get_response.read = AsyncMock(return_value=b"fake_content")
    mock_get_response.content_type = "image/jpeg"
    mock_get_response.headers = {"x-amz-meta-filename": "test.jpg"}
    mock_get_response.close = MagicMock()

    client.get_object = AsyncMock(return_value=mock_get_response)
    client.remove_object = AsyncMock()
    client.copy_object = AsyncMock()

    return client


@pytest.fixture
def mock_upload_file():
    file = MagicMock(spec=UploadFile)
    file.filename = "test.jpg"
    file.content_type = "image/jpeg"
    file.file = io.BytesIO(b"fake_content")
    return file


@pytest.mark.asyncio
async def test_init_minio_client(mock_minio_client):
    with patch("app.infra.minio.Minio", return_value=mock_minio_client):
        mock_minio_client.bucket_exists.return_value = False
        await init_minio_client("localhost", 9000, "root", "password")

        # Ensure it creates the three standard buckets
        assert mock_minio_client.bucket_exists.call_count == 3
        assert mock_minio_client.make_bucket.call_count == 3
        assert Bucket.client == mock_minio_client


@pytest.mark.asyncio
async def test_bucket_put(mock_minio_client, mock_upload_file):
    Bucket.client = mock_minio_client
    bucket = Bucket("test_bucket", "prefix")

    object_name = await bucket.put(mock_upload_file, "custom_name.jpg")
    assert object_name == "custom_name.jpg"
    mock_minio_client.put_object.assert_called_once()

    kwargs = mock_minio_client.put_object.call_args[1]
    assert kwargs["bucket_name"] == "test_bucket"
    assert kwargs["object_name"] == "prefix/custom_name.jpg"
    assert kwargs["content_type"] == "image/jpeg"


@pytest.mark.asyncio
async def test_bucket_put_auto_generate_name(mock_minio_client, mock_upload_file):
    Bucket.client = mock_minio_client
    bucket = Bucket("test_bucket", "")

    object_name = await bucket.put(mock_upload_file)
    assert object_name is not None
    # Assuming UUID string format length
    assert len(object_name) == 36


@pytest.mark.asyncio
async def test_bucket_get_success(mock_minio_client):
    Bucket.client = mock_minio_client
    bucket = Bucket("test_bucket", "prefix")

    data, filename, content_type = await bucket.get("test.jpg")

    mock_minio_client.get_object.assert_called_once_with(
        bucket_name="test_bucket", object_name="prefix/test.jpg"
    )
    assert data == b"fake_content"
    assert filename == "test.jpg"
    assert content_type == "image/jpeg"


@pytest.mark.asyncio
async def test_bucket_get_not_found(mock_minio_client):
    Bucket.client = mock_minio_client

    # Simulate MinIO NoSuchKey error
    error_response = MagicMock()
    error_response.status = 404
    error_response.data = b"<Error><Code>NoSuchKey</Code></Error>"
    mock_minio_client.get_object.side_effect = S3Error(
        code="NoSuchKey",
        message="The specified key does not exist.",
        resource="/test_bucket/test.jpg",
        request_id="123",
        host_id="456",
        response=error_response,
    )

    bucket = Bucket("test_bucket", "")

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await bucket.get("test.jpg")
    assert exc.value.status_code == 404
    assert exc.value.detail == "File not found"


@pytest.mark.asyncio
async def test_bucket_delete(mock_minio_client):
    Bucket.client = mock_minio_client
    bucket = Bucket("test_bucket", "prefix")

    await bucket.delete("test.jpg")

    mock_minio_client.remove_object.assert_called_once_with(
        bucket_name="test_bucket", object_name="prefix/test.jpg"
    )


@pytest.mark.asyncio
async def test_bucket_put_bytes(mock_minio_client):
    Bucket.client = mock_minio_client
    bucket = Bucket("test_bucket", "")

    await bucket.put_bytes(
        data=b"byte_data",
        object_name="byte_test.txt",
        content_type="text/plain"
    )

    mock_minio_client.put_object.assert_called_once()
    kwargs = mock_minio_client.put_object.call_args[1]
    assert kwargs["bucket_name"] == "test_bucket"
    assert kwargs["object_name"] == "byte_test.txt"
    assert kwargs["content_type"] == "text/plain"
    assert kwargs["length"] == 9


@pytest.mark.asyncio
async def test_bucket_copy(mock_minio_client):
    Bucket.client = mock_minio_client
    bucket = Bucket("test_bucket", "prefix")

    await bucket.copy(source_object_name="source.jpg", target_object_name="target.jpg")

    mock_minio_client.copy_object.assert_called_once()
    kwargs = mock_minio_client.copy_object.call_args[1]
    assert kwargs["bucket_name"] == "test_bucket"
    assert kwargs["object_name"] == "prefix/target.jpg"
    assert kwargs["source"].object_name == "prefix/source.jpg"


@pytest.mark.asyncio
async def test_image_bucket_valid_extension(mock_minio_client, mock_upload_file):
    Bucket.client = mock_minio_client
    bucket = ImageBucket("img_prefix")

    mock_upload_file.filename = "test.png"
    mock_upload_file.content_type = "image/png"

    object_name = await bucket.put(mock_upload_file, "custom.png")
    assert object_name == "custom.png"


@pytest.mark.asyncio
async def test_image_bucket_invalid_extension(mock_minio_client, mock_upload_file):
    Bucket.client = mock_minio_client
    bucket = ImageBucket("img_prefix")

    mock_upload_file.filename = "test.pdf"
    mock_upload_file.content_type = "application/pdf"

    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await bucket.put(mock_upload_file)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_wa_sim_bucket_auto_name(mock_minio_client, mock_upload_file):
    Bucket.client = mock_minio_client
    bucket = WaSimBucket()

    object_name = await bucket.put(mock_upload_file)
    # WaSimBucket generates 16 digit string
    assert len(object_name) == 16
    assert object_name.isdigit()


@pytest.mark.asyncio
async def test_presigned_put_url_calls_client_with_expiry(mock_minio_client):
    Bucket.client = mock_minio_client
    mock_minio_client.presigned_put_object = AsyncMock(return_value="https://minio.local/signed")
    bucket = Bucket("test_bucket", "")

    url = await bucket.presigned_put_url("staging/foo.jpg", expires_seconds=1800)

    assert url == "https://minio.local/signed"
    mock_minio_client.presigned_put_object.assert_awaited_once()
    kwargs = mock_minio_client.presigned_put_object.call_args[1]
    assert kwargs["object_name"] == "staging/foo.jpg"
    assert kwargs["expires"].total_seconds() == 1800


@pytest.mark.asyncio
async def test_stat_returns_object_stat_when_present(mock_minio_client):
    Bucket.client = mock_minio_client
    stat_result = MagicMock(size=12345, content_type="image/jpeg")
    mock_minio_client.stat_object = AsyncMock(return_value=stat_result)
    bucket = Bucket("test_bucket", "")

    result = await bucket.stat("staging/foo.jpg")

    assert result == ObjectStat(size=12345, content_type="image/jpeg")


@pytest.mark.asyncio
async def test_stat_returns_none_when_object_missing(mock_minio_client):
    Bucket.client = mock_minio_client
    error = S3Error(
        code="NoSuchKey", message="not found", resource="", request_id="",
        host_id="", response=MagicMock(),
    )
    mock_minio_client.stat_object = AsyncMock(side_effect=error)
    bucket = Bucket("test_bucket", "")

    result = await bucket.stat("staging/missing.jpg")

    assert result is None
