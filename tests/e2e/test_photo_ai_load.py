import asyncio
import json
import os
import random
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.infra.database import engine
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME, init_minio_client
from app.infra.nats import NatsClient, NatsSubjects

# ── guard: only run when explicitly requested ─────────────────────────
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        os.getenv("MULTAI_RUN_E2E") != "1",
        reason="set MULTAI_RUN_E2E=1 to run live e2e tests",
    ),
]

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "images"


@pytest.fixture(scope="function")
async def setup_infra() -> AsyncGenerator[None, None]:
    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD,
    )
    await NatsClient.connect()
    yield
    await NatsClient.close()
    NatsClient._nc = None  # type: ignore[attr-defined]
    await engine.dispose()


async def _setup_event(conn: AsyncConnection) -> uuid.UUID:
    event_id = uuid.uuid4()
    await conn.execute(  # type: ignore[union-attr]
        text(
            """
            INSERT INTO staff_users (id, email, password, role)
            VALUES ('00000000-0000-0000-0000-000000000001'::uuid,
                    'e2e_load@test.com', 'hash', 'admin')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    event_code = f"LOAD-{str(uuid.uuid4())[:6].upper()}"
    await conn.execute(  # type: ignore[union-attr]
        text(
            """
            INSERT INTO events (id, name, event_code, event_date, status, created_by)
            VALUES (:id, 'E2E Load Event', :code, NOW(), 'draft',
                    '00000000-0000-0000-0000-000000000001'::uuid)
            """
        ),
        {"id": event_id, "code": event_code},
    )
    return event_id


async def _wait_for_jobs(
    photo_ids: list[uuid.UUID], timeout: int = 180
) -> dict[str, int]:
    """Return a status→count dict once all jobs have a terminal status."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    async with engine.connect() as conn:
        while loop.time() < deadline:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT status, count(*)
                        FROM processing_jobs
                        WHERE photo_id = ANY(:ids)
                          AND job_type = 'face_detection'
                        GROUP BY status
                        """
                    ),
                    {"ids": photo_ids},
                )
            ).fetchall()
            status_counts: dict[str, int] = {row[0]: int(row[1]) for row in rows}
            total = sum(status_counts.values())
            if total == len(photo_ids):
                completed = status_counts.get("completed", 0)
                failed = status_counts.get("failed", 0)
                if completed + failed == len(photo_ids):
                    return status_counts
            await asyncio.sleep(2.0)
    return {"timeout": 1}


async def test_photo_ai_load_20_photos(setup_infra: None) -> None:  # noqa: ARG001
    """Process 20 photos concurrently; expect 0 failures within 3 minutes."""
    image_files = ["face.jpg", "group.jpg", "noface.jpg"]
    image_contents: dict[str, bytes] = {}
    for img in image_files:
        path = FIXTURE_DIR / img
        assert path.exists(), f"Fixture not found: {path}"
        image_contents[img] = path.read_bytes()

    num_photos = 20
    photo_tasks: list[dict[str, object]] = []
    event_id: uuid.UUID | None = None

    async with engine.begin() as conn:
        event_id = await _setup_event(conn)
        for _ in range(num_photos):
            photo_id = uuid.uuid4()
            selected_img = random.choice(image_files)
            storage_key = f"load-test/{event_id}/{photo_id}.jpg"
            photo_tasks.append(
                {"photo_id": photo_id, "storage_key": storage_key, "content": image_contents[selected_img]}
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO photos (id, event_id, storage_key, visibility, status)
                    VALUES (:id, :event_id, :key, 'private', 'pending')
                    """
                ),
                {"id": photo_id, "event_id": event_id, "key": storage_key},
            )

    assert event_id is not None
    bucket = Bucket(IMAGES_BUCKET_NAME, "")

    try:
        # 1. Upload all photos to MinIO concurrently
        await asyncio.gather(
            *[
                bucket.put_bytes(
                    object_name=p["storage_key"],  # type: ignore[arg-type]
                    data=p["content"],  # type: ignore[arg-type]
                    content_type="image/jpeg",
                )
                for p in photo_tasks
            ]
        )

        # 2. Publish 20 NATS messages concurrently
        await asyncio.gather(
            *[
                NatsClient.publish(
                    NatsSubjects.PHOTO_PROCESS.value,
                    json.dumps(
                        {
                            "photo_id": str(p["photo_id"]),
                            "image_ref": p["storage_key"],
                            "event_id": str(event_id),
                        }
                    ).encode("utf-8"),
                )
                for p in photo_tasks
            ]
        )

        # 3. Wait for all jobs
        photo_ids: list[uuid.UUID] = [
            p["photo_id"] for p in photo_tasks  # type: ignore[misc]
        ]
        status_counts = await _wait_for_jobs(photo_ids, timeout=180)

        assert "timeout" not in status_counts, (
            "Load test timed out waiting for jobs to complete"
        )
        failed = status_counts.get("failed", 0)
        completed = status_counts.get("completed", 0)
        assert failed == 0, f"Expected 0 failed jobs, got {failed}"
        assert completed == num_photos, (
            f"Expected {num_photos} completed jobs, got {completed}"
        )
    finally:
        # Always clean up DB and MinIO regardless of test outcome
        async with engine.begin() as conn:
            photo_ids_list = [p["photo_id"] for p in photo_tasks]
            if photo_ids_list:
                await conn.execute(
                    text(
                        "DELETE FROM face_matches fm "
                        "USING photo_faces pf "
                        "WHERE pf.id = fm.photo_face_id "
                        "AND pf.photo_id = ANY(:ids)"
                    ),
                    {"ids": photo_ids_list},
                )
                await conn.execute(
                    text("DELETE FROM photo_faces WHERE photo_id = ANY(:ids)"),
                    {"ids": photo_ids_list},
                )
                await conn.execute(
                    text("DELETE FROM processing_jobs WHERE photo_id = ANY(:ids)"),
                    {"ids": photo_ids_list},
                )
                await conn.execute(
                    text("DELETE FROM photos WHERE event_id = :eid"),
                    {"eid": event_id},
                )
            await conn.execute(
                text("DELETE FROM events WHERE id = :eid"), {"eid": event_id}
            )
        # Clean up MinIO objects
        for p in photo_tasks:
            try:
                await bucket.delete(p["storage_key"])  # type: ignore[arg-type]
            except Exception:
                pass
