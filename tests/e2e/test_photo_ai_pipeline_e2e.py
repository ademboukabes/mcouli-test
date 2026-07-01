import json
import uuid

from sqlalchemy import text

from app.infra.database import engine
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME
from app.infra.nats import NatsClient, NatsSubjects

from tests.e2e.conftest import _seed_event_and_photo, _wait_for_job, _cleanup, FIXTURE_DIR


async def test_photo_ai_pipeline_detects_single_face() -> None:
    """Single face in photo with no enrolled users → auto-approved."""
    photo_id = uuid.uuid4()
    storage_key = f"e2e_test_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "face.jpg"

    assert image_path.exists(), f"Test fixture not found: {image_path}"

    bucket = Bucket(IMAGES_BUCKET_NAME, "")

    # 1. Seed MinIO + DB
    await bucket.put_bytes(
        object_name=storage_key,
        data=image_path.read_bytes(),
        content_type="image/jpeg",
    )
    async with engine.begin() as conn:
        event_id = await _seed_event_and_photo(
            conn, photo_id=photo_id, storage_key=storage_key
        )

    # 2. Trigger worker
    payload = {
        "photo_id": str(photo_id),
        "image_ref": storage_key,
        "event_id": str(event_id),
    }
    await NatsClient.publish(
        NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8")
    )

    # 3. Assertions + Cleanup — always run cleanup via try/finally
    try:
        final_status = await _wait_for_job(photo_id, timeout_s=60)
        assert final_status == "completed", f"Processing job ended with: {final_status}"

        async with engine.connect() as conn:
            photo_status = (
                await conn.execute(
                    text("SELECT status FROM photos WHERE id = :pid"),
                    {"pid": photo_id},
                )
            ).scalar()
        assert photo_status == "approved", (
            f"Expected photo status 'approved', got {photo_status}"
        )
    finally:
        async with engine.begin() as conn:
            await _cleanup(conn, photo_id=photo_id, event_id=event_id)
        try:
            await bucket.delete(storage_key)
        except Exception:
            pass


async def test_photo_ai_pipeline_corrupt_image() -> None:
    """Corrupt image → processing job fails, photo status remains pending or marked as error."""
    photo_id = uuid.uuid4()
    storage_key = f"e2e_corrupt_{photo_id}.jpg"

    bucket = Bucket(IMAGES_BUCKET_NAME, "")

    # 1. Seed MinIO with corrupt data + DB
    await bucket.put_bytes(
        object_name=storage_key,
        data=b"this is not a valid image file",
        content_type="image/jpeg",
    )
    async with engine.begin() as conn:
        event_id = await _seed_event_and_photo(
            conn, photo_id=photo_id, storage_key=storage_key
        )

    # 2. Trigger worker
    payload = {
        "photo_id": str(photo_id),
        "image_ref": storage_key,
        "event_id": str(event_id),
    }
    await NatsClient.publish(
        NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8")
    )

    # 3. Assertions + Cleanup
    try:
        final_status = await _wait_for_job(photo_id, timeout_s=30)
        assert final_status == "failed", f"Expected job to fail, but ended with: {final_status}"
    finally:
        async with engine.begin() as conn:
            await _cleanup(conn, photo_id=photo_id, event_id=event_id)
        try:
            await bucket.delete(storage_key)
        except Exception:
            pass
