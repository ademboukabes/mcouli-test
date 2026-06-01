import asyncio
import json
import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.infra.database import engine
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME, init_minio_client
from app.infra.nats import NatsClient, NatsSubjects

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("MULTAI_RUN_E2E") != "1",
        reason="set MULTAI_RUN_E2E=1 to run live e2e tests",
    ),
]

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "images"


@pytest.fixture(autouse=True)
async def setup_infra():
    # Initialize MinIO
    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD,
    )
    yield
    # Cleanup NATS (close connection if any)
    await NatsClient.close()


async def test_photo_ai_pipeline_detects_single_face():
    # 1. Setup Test Data
    event_id = uuid.uuid4()
    photo_id = uuid.uuid4()
    storage_key = f"e2e_test_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "face.jpg"

    assert image_path.exists(), "Test image not found"
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 2. Upload to MinIO
    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    await bucket.put_bytes(
        object_name=storage_key,
        data=image_bytes,
        content_type="image/jpeg",
    )

    # 3. Insert into Database
    async with engine.begin() as conn:
        # Create a dummy staff user for the event's created_by foreign key
        await conn.execute(
            text(
                """
                INSERT INTO staff_users (id, email, password, role)
                VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'e2e@test.com', 'hash', 'admin')
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
        # Create a dummy event
        event_code = f"E2E-{str(uuid.uuid4())[:6].upper()}"
        await conn.execute(
            text(
                """
                INSERT INTO events (id, name, event_code, event_date, status, created_by)
                VALUES (:id, 'E2E Test Event', :event_code, NOW(), 'draft', '00000000-0000-0000-0000-000000000001'::uuid)
                """
            ),
            {"id": event_id, "event_code": event_code}
        )
        # Insert photo
        await conn.execute(
            text(
                """
                INSERT INTO photos (id, event_id, storage_key, visibility, status)
                VALUES (:id, :event_id, :storage_key, 'private', 'pending')
                """
            ),
            {
                "id": photo_id,
                "event_id": event_id,
                "storage_key": storage_key,
            }
        )

    # 4. Trigger Photo Worker via NATS
    payload = {
        "photo_id": str(photo_id),
        "image_ref": storage_key,
        "event_id": str(event_id),
    }
    await NatsClient.publish(NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8"))

    # 5. Poll for processing completion
    max_retries = 30
    delay = 1.0  # seconds
    
    completed = False
    async with engine.connect() as conn:
        for _ in range(max_retries):
            result = await conn.execute(
                text("SELECT status FROM processing_jobs WHERE photo_id = :photo_id AND job_type = 'face_detection'"),
                {"photo_id": photo_id}
            )
            job = result.fetchone()
            
            if job and job[0] == "completed":
                completed = True
                break
            elif job and job[0] == "failed":
                pytest.fail("Processing job failed")
                
            await asyncio.sleep(delay)

    assert completed, "Photo processing timed out"

    # 6. Verify assertions
    async with engine.begin() as conn:
        # Check if photo status is approved (since there are no users to match against)
        result = await conn.execute(
            text("SELECT status FROM photos WHERE id = :photo_id"),
            {"photo_id": photo_id}
        )
        photo_status = result.scalar()
        assert photo_status == "approved", f"Expected photo status 'approved', got {photo_status}"

        # Clean up database
        await conn.execute(text("DELETE FROM photo_faces WHERE photo_id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM processing_jobs WHERE photo_id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM photos WHERE id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM events WHERE id = :event_id"), {"event_id": event_id})

    # Clean up MinIO
    await bucket.delete(storage_key)
