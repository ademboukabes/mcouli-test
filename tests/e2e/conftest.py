import asyncio
import os
import uuid
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.core.config import settings
from app.infra.database import engine
from app.infra.minio import init_minio_client
from app.infra.nats import NatsClient

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "images"

# ── guard: only run when explicitly requested ─────────────────────────
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "e2e: mark test as an end-to-end test")

@pytest.fixture(autouse=True)
async def setup_infra() -> AsyncGenerator[None, None]:
    if os.getenv("MULTAI_RUN_E2E") != "1":
        pytest.skip("set MULTAI_RUN_E2E=1 to run live e2e tests")
    
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


# ── shared helpers ────────────────────────────────────────────────────

async def _seed_event_and_photo(
    conn: AsyncConnection,
    *,
    photo_id: uuid.UUID,
    storage_key: str,
) -> uuid.UUID:
    """Insert a staff user, a new event, and a photo. Returns event_id."""
    event_id = uuid.uuid4()
    await conn.execute(  # type: ignore[union-attr]
        text(
            """
            INSERT INTO staff_users (id, email, password, role)
            VALUES ('00000000-0000-0000-0000-000000000001'::uuid,
                    'e2e@test.com', 'hash', 'admin')
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    event_code = f"E2E-{str(uuid.uuid4())[:6].upper()}"
    await conn.execute(  # type: ignore[union-attr]
        text(
            """
            INSERT INTO events (id, name, event_code, event_date, status, created_by)
            VALUES (:id, 'E2E Test Event', :code, NOW(), 'draft',
                    '00000000-0000-0000-0000-000000000001'::uuid)
            """
        ),
        {"id": event_id, "code": event_code},
    )
    await conn.execute(  # type: ignore[union-attr]
        text(
            """
            INSERT INTO photos (id, event_id, storage_key, visibility, status)
            VALUES (:id, :event_id, :key, 'private', 'pending')
            """
        ),
        {"id": photo_id, "event_id": event_id, "key": storage_key},
    )
    return event_id


async def _wait_for_job(photo_id: uuid.UUID, timeout_s: int = 60) -> str:
    """Poll processing_jobs until terminal status. Returns 'completed', 'failed', or 'timeout'."""
    deadline = asyncio.get_event_loop().time() + timeout_s
    async with engine.connect() as conn:
        while asyncio.get_event_loop().time() < deadline:
            row = (
                await conn.execute(
                    text(
                        "SELECT status FROM processing_jobs "
                        "WHERE photo_id = :pid AND job_type = 'face_detection'"
                    ),
                    {"pid": photo_id},
                )
            ).fetchone()
            if row and row[0] in ("completed", "failed"):
                return str(row[0])
            await asyncio.sleep(1.0)
    return "timeout"


async def _cleanup(
    conn: AsyncConnection,
    *,
    photo_id: uuid.UUID,
    event_id: uuid.UUID,
    user_id: str | None = None,
) -> None:
    """Delete all rows created during a test, in FK-safe order."""
    if user_id:
        await conn.execute(text("DELETE FROM notifications WHERE user_id = :uid"), {"uid": user_id})  # type: ignore[union-attr]
        await conn.execute(text("DELETE FROM face_matches WHERE user_id = :uid"), {"uid": user_id})  # type: ignore[union-attr]
        await conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})  # type: ignore[union-attr]
    await conn.execute(text("DELETE FROM face_matches fm USING photo_faces pf WHERE pf.id = fm.photo_face_id AND pf.photo_id = :pid"), {"pid": photo_id})  # type: ignore[union-attr]
    await conn.execute(text("DELETE FROM photo_faces WHERE photo_id = :pid"), {"pid": photo_id})  # type: ignore[union-attr]
    await conn.execute(text("DELETE FROM processing_jobs WHERE photo_id = :pid"), {"pid": photo_id})  # type: ignore[union-attr]
    await conn.execute(text("DELETE FROM photos WHERE id = :pid"), {"pid": photo_id})  # type: ignore[union-attr]
    await conn.execute(text("DELETE FROM events WHERE id = :eid"), {"eid": event_id})  # type: ignore[union-attr]
