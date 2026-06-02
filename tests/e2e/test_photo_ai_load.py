import asyncio
import uuid
import random
from pathlib import Path
import pytest
from sqlalchemy import text

from app.core.config import settings
from app.infra.database import engine
from app.infra.minio import init_minio_client, Bucket, IMAGES_BUCKET_NAME
from app.infra.nats import NatsClient, NatsSubjects

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.e2e,
]


@pytest.fixture(scope="function")
async def setup_infra():
    # Ensure connections are initialized
    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD,
    )
    await NatsClient.connect()

    yield
    
    # Cleanup
    await NatsClient.close()
    NatsClient._nc = None
    await engine.dispose()


async def _setup_event(conn) -> uuid.UUID:
    event_id = uuid.uuid4()
    
    # Create staff user
    await conn.execute(
        text(
            """
            INSERT INTO staff_users (id, email, password, role)
            VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'e2e_load@test.com', 'hash', 'admin')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    
    # Create event
    event_code = f"LOAD-{str(uuid.uuid4())[:6].upper()}"
    await conn.execute(
        text(
            """
            INSERT INTO events (id, name, event_code, event_date, status, created_by)
            VALUES (:id, 'E2E Load Event', :event_code, NOW(), 'draft', '00000000-0000-0000-0000-000000000001'::uuid)
            """
        ),
        {"id": event_id, "event_code": event_code}
    )
    return event_id


async def _wait_for_jobs_completion(photo_ids: list[uuid.UUID], timeout: int = 60) -> dict:
    start_time = asyncio.get_event_loop().time()
    
    async with engine.connect() as conn:
        while asyncio.get_event_loop().time() - start_time < timeout:
            result = await conn.execute(
                text(
                    """
                    SELECT status, count(*) 
                    FROM processing_jobs 
                    WHERE photo_id = ANY(:photo_ids) AND job_type = 'face_detection'
                    GROUP BY status
                    """
                ),
                {"photo_ids": photo_ids}
            )
            rows = result.fetchall()
            status_counts = {row[0]: row[1] for row in rows}
            
            # If total jobs equals number of photos, and no 'pending' or 'running', we're done
            total_jobs = sum(status_counts.values())
            if total_jobs == len(photo_ids):
                completed = status_counts.get("completed", 0)
                failed = status_counts.get("failed", 0)
                if completed + failed == len(photo_ids):
                    return status_counts

            await asyncio.sleep(2.0)
            
    return {"timeout": True}


async def test_photo_ai_load_20_photos(setup_infra):
    images_dir = Path("tests/fixtures/images")
    image_files = ["face.jpg", "group.jpg", "noface.jpg"]
    
    # Read image contents into memory to upload them quickly
    image_contents = {}
    for img in image_files:
        with open(images_dir / img, "rb") as f:
            image_contents[img] = f.read()

    num_photos = 20
    photo_tasks = []
    
    async with engine.begin() as conn:
        event_id = await _setup_event(conn)
        
        for i in range(num_photos):
            photo_id = uuid.uuid4()
            selected_img = random.choice(image_files)
            storage_key = f"load-test/{event_id}/{photo_id}.jpg"
            
            photo_tasks.append({
                "photo_id": photo_id,
                "storage_key": storage_key,
                "content": image_contents[selected_img]
            })
            
            # Insert photo record
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

    # 1. Upload all 20 photos to MinIO concurrently
    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    upload_coros = []
    for p in photo_tasks:
        upload_coros.append(
            bucket.put_bytes(object_name=p["storage_key"], data=p["content"], content_type="image/jpeg")
        )
    await asyncio.gather(*upload_coros)

    # 2. Publish 20 NATS messages concurrently
    import json
    publish_coros = []
    for p in photo_tasks:
        payload = {
            "photo_id": str(p["photo_id"]),
            "image_ref": p["storage_key"],
            "event_id": str(event_id)
        }
        payload_bytes = json.dumps(payload).encode("utf-8")
        publish_coros.append(
            NatsClient.publish(
                NatsSubjects.PHOTO_PROCESS.value,
                payload_bytes
            )
        )
    await asyncio.gather(*publish_coros)

    # 3. Wait for processing to finish
    photo_ids = [p["photo_id"] for p in photo_tasks]
    status_counts = await _wait_for_jobs_completion(photo_ids, timeout=180)
    
    assert "timeout" not in status_counts, "Load test timed out waiting for jobs to complete"
    
    completed = status_counts.get("completed", 0)
    failed = status_counts.get("failed", 0)
    
    assert failed == 0, f"Expected 0 failed jobs, got {failed}"
    assert completed == num_photos, f"Expected {num_photos} completed jobs, got {completed}"
