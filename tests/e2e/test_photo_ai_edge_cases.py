import asyncio
import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text

from app.infra.database import engine
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME
from app.infra.nats import NatsClient, NatsSubjects
from app.core.config import settings

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "images"

pytestmark = [
    pytest.mark.asyncio,
]

@pytest.fixture(autouse=True)
async def setup_infra():
    from app.infra.minio import init_minio_client
    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD,
    )
    yield
    from app.infra.nats import NatsClient
    await NatsClient.close()
    NatsClient._nc = None
    from app.infra.database import engine
    await engine.dispose()


async def _setup_event_and_photo(conn, photo_id: uuid.UUID, storage_key: str) -> uuid.UUID:
    event_id = uuid.uuid4()
    
    # Create staff user
    await conn.execute(
        text(
            """
            INSERT INTO staff_users (id, email, password, role)
            VALUES ('00000000-0000-0000-0000-000000000001'::uuid, 'e2e@test.com', 'hash', 'admin')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    
    # Create event
    event_code = f"E2E-{str(uuid.uuid4())[:6].upper()}"
    await conn.execute(
        text(
            """
            INSERT INTO events (id, name, event_code, event_date, status, created_by)
            VALUES (:id, 'E2E Edge Event', :event_code, NOW(), 'draft', '00000000-0000-0000-0000-000000000001'::uuid)
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
    return event_id


async def _wait_for_job_completion(photo_id: uuid.UUID) -> bool:
    max_retries = 30
    delay = 1.0

    async with engine.connect() as conn:
        for _ in range(max_retries):
            result = await conn.execute(
                text("SELECT status FROM processing_jobs WHERE photo_id = :photo_id AND job_type = 'face_detection'"),
                {"photo_id": photo_id}
            )
            job = result.fetchone()

            if job and job[0] == "completed":
                return True
            elif job and job[0] == "failed":
                return False

            await asyncio.sleep(delay)
    return False


async def test_photo_ai_pipeline_detects_0_faces():
    """Test what happens when a photo has no faces (noface.jpg)."""
    photo_id = uuid.uuid4()
    storage_key = f"e2e_noface_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "noface.jpg"

    assert image_path.exists(), "Test image noface.jpg not found"

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    await bucket.put_bytes(object_name=storage_key, data=image_bytes, content_type="image/jpeg")

    async with engine.begin() as conn:
        event_id = await _setup_event_and_photo(conn, photo_id, storage_key)

    payload = {"photo_id": str(photo_id), "image_ref": storage_key, "event_id": str(event_id)}
    await NatsClient.publish(NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8"))

    completed = await _wait_for_job_completion(photo_id)
    assert completed, "Photo processing timed out or failed"

    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT status, visibility FROM photos WHERE id = :photo_id"), {"photo_id": photo_id})
        photo_row = result.fetchone()
        
        assert photo_row[0] == "approved", f"Expected status 'approved', got {photo_row[0]}"
        assert photo_row[1] == "public", f"Expected visibility 'public', got {photo_row[1]}"

        # Cleanup
        await conn.execute(text("DELETE FROM processing_jobs WHERE photo_id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM photos WHERE id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM events WHERE id = :event_id"), {"event_id": event_id})

    await bucket.delete(storage_key)


async def test_photo_ai_pipeline_detects_multiple_faces():
    """Test what happens when a photo has multiple faces (group.jpg)."""
    photo_id = uuid.uuid4()
    storage_key = f"e2e_group_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "group.jpg"

    assert image_path.exists(), "Test image group.jpg not found"

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    await bucket.put_bytes(object_name=storage_key, data=image_bytes, content_type="image/jpeg")

    async with engine.begin() as conn:
        event_id = await _setup_event_and_photo(conn, photo_id, storage_key)

    payload = {"photo_id": str(photo_id), "image_ref": storage_key, "event_id": str(event_id)}
    await NatsClient.publish(NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8"))

    completed = await _wait_for_job_completion(photo_id)
    assert completed, "Photo processing timed out or failed"

    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT status FROM photos WHERE id = :photo_id"), {"photo_id": photo_id})
        photo_status = result.scalar()
        
        # A group photo leaves the status as pending because it contains multiple unverified faces
        assert photo_status == "pending", f"Expected status 'pending', got {photo_status}"

        # Cleanup
        await conn.execute(text("DELETE FROM processing_jobs WHERE photo_id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM photos WHERE id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM events WHERE id = :event_id"), {"event_id": event_id})

    await bucket.delete(storage_key)


async def test_photo_ai_pipeline_matched_user():
    """Test what happens when a single face matches an existing user."""
    from app.service.face_embedding import FaceEmbeddingService, FaceImagePayload
    
    photo_id = uuid.uuid4()
    storage_key = f"e2e_matched_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "face.jpg"

    assert image_path.exists(), "Test image face.jpg not found"

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    # 1. Extract the embedding using the actual service so we can mock a user
    face_service = FaceEmbeddingService()
    payload_face = FaceImagePayload(filename="face.jpg", content_type="image/jpeg", bytes=image_bytes)
    faces = await face_service.detect_faces(payload_face)
    assert len(faces) == 1, "Expected exactly 1 face in face.jpg"
    embedding = faces[0].embedding
    embedding_literal = "[" + ", ".join(str(x) for x in embedding) + "]"

    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    await bucket.put_bytes(object_name=storage_key, data=image_bytes, content_type="image/jpeg")

    async with engine.begin() as conn:
        event_id = await _setup_event_and_photo(conn, photo_id, storage_key)
        
        # Insert a matched user with the exact same embedding
        matched_user_id = "00000000-0000-0000-0000-000000000002"
        # First ensure clean state from any previous failed runs
        await conn.execute(text("DELETE FROM notifications WHERE user_id = :user_id"), {"user_id": matched_user_id})
        await conn.execute(text("DELETE FROM face_matches WHERE user_id = :user_id"), {"user_id": matched_user_id})
        await conn.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": matched_user_id})

        await conn.execute(
            text(
                f"""
                INSERT INTO users (id, email, hashed_password, face_embedding)
                VALUES ('{matched_user_id}'::uuid, 'matched@test.com', 'hash', '{embedding_literal}')
                """
            )
        )

    payload = {"photo_id": str(photo_id), "image_ref": storage_key, "event_id": str(event_id)}
    await NatsClient.publish(NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8"))

    completed = await _wait_for_job_completion(photo_id)
    assert completed, "Photo processing timed out or failed"

    async with engine.begin() as conn:
        # Check photo status
        result = await conn.execute(text("SELECT status FROM photos WHERE id = :photo_id"), {"photo_id": photo_id})
        photo_status = result.scalar()
        assert photo_status == "approved", f"Expected photo status 'approved', got {photo_status}"

        result = await conn.execute(
            text("SELECT fm.user_id FROM face_matches fm JOIN photo_faces pf ON pf.id = fm.photo_face_id WHERE pf.photo_id = :photo_id"), 
            {"photo_id": photo_id}
        )
        matched_db_user = result.scalar()
        assert str(matched_db_user) == matched_user_id, f"Expected user {matched_user_id}, got {matched_db_user}"

        # Check that notification was sent
        result = await conn.execute(
            text("SELECT count(*) FROM notifications WHERE user_id = :user_id AND type = 'face_match'"),
            {"user_id": matched_user_id}
        )
        notif_count = result.scalar()
        assert notif_count == 1, "Expected 1 notification for the matched user"

        # Cleanup
        await conn.execute(text("DELETE FROM notifications WHERE user_id = :user_id"), {"user_id": matched_user_id})
        await conn.execute(text("DELETE FROM photo_faces WHERE photo_id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": matched_user_id})
        await conn.execute(text("DELETE FROM processing_jobs WHERE photo_id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM photos WHERE id = :photo_id"), {"photo_id": photo_id})
        await conn.execute(text("DELETE FROM events WHERE id = :event_id"), {"event_id": event_id})

    await bucket.delete(storage_key)
