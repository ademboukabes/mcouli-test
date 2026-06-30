"""
multAI backend seed script

What this does:
  - Creates staff users (admin, lead, multi roles)
  - Creates mobile users (alice, bob) with devices and sessions
  - Creates 2 events and joins all users to them
  - Uploads placeholder photos to MinIO and inserts them as approved
  - Creates face matches and photo approvals so gallery endpoints return results
  - Creates notifications for all users
  - Creates processing jobs marked complete so pipeline endpoints look healthy
  - Creates upload request groups and requests for staff review endpoints

Usage:
  docker compose -f docker-compose.mobile.yml exec fastapi uv run python seed.py
  docker compose -f docker-compose.mobile.yml exec fastapi uv run python seed.py --reset
"""

import asyncio
import io
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

import asyncpg  # type: ignore[import-untyped]
from dotenv import load_dotenv
from miniopy_async.api import Minio
from PIL import Image, ImageDraw

from app.core.config import settings
from app.core.securite import hash_password

load_dotenv()

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

STAFF_USERS = [
    {"email": "admin@multai.dev",  "password": "Admin1234!",  "role": "admin"},
    {"email": "lead@multai.dev",   "password": "Lead1234!",   "role": "multi_team_lead"},
    {"email": "multi@multai.dev",  "password": "Multi1234!",  "role": "multi"},
]

MOBILE_USERS = [
    {"email": "alice@example.com", "password": "Alice123!", "display_name": "Alice"},
    {"email": "bob@example.com",   "password": "Bob1234!",  "display_name": "Bob"},
]

EVENTS = [
    {
        "name": "Tech Conference 2025",
        "event_code": "TECH2025",
        "event_date": datetime(2025, 9, 15, 9, 0, tzinfo=timezone.utc),
        "status": "scheduled",
    },
    {
        "name": "Annual Gala",
        "event_code": "GALA2025",
        "event_date": datetime(2025, 12, 20, 19, 0, tzinfo=timezone.utc),
        "status": "scheduled",
    },
]

PHOTOS_PER_EVENT = 4
IMAGES_BUCKET = "images"

PHOTO_COLORS = [
    (52, 152, 219),
    (46, 204, 113),
    (231, 76, 60),
    (155, 89, 182),
    (241, 196, 15),
    (230, 126, 34),
    (26, 188, 156),
    (52, 73, 94),
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now() -> datetime:
    return datetime.now(timezone.utc)


def future(days: int) -> datetime:
    return now() + timedelta(days=days)


def make_storage_key(event_id: uuid.UUID, index: int) -> str:
    return f"seed/events/{event_id}/photo_{index}.jpg"


def generate_placeholder_image(label: str, color: tuple[int, int, int]) -> bytes:
    img = Image.new("RGB", (800, 600), color=color)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), label)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((800 - w) / 2, (600 - h) / 2), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

async def reset_db(conn: asyncpg.Connection) -> None:
    print("Resetting database...")
    tables = [
        "audit_events", "face_matches", "photo_faces", "photo_approvals",
        "user_photos", "processing_jobs", "upload_request_photos",
        "upload_requests", "upload_request_groups", "notifications",
        "staff_notifications", "staff_drive_connections", "event_participants",
        "user_sessions", "user_devices", "photos", "events",
        "users", "staff_users",
    ]
    for table in tables:
        await conn.execute(f"DELETE FROM {table}")
        print(f"  cleared {table}")
    print()


async def reset_minio(minio: Minio) -> None:
    print("Clearing MinIO seed objects...")
    objects = minio.list_objects(IMAGES_BUCKET, prefix="seed/", recursive=True)
    async for obj in objects:
        await minio.remove_object(IMAGES_BUCKET, obj.object_name)
    print("  MinIO seed objects cleared\n")


# ---------------------------------------------------------------------------
# MinIO
# ---------------------------------------------------------------------------

async def init_minio(minio: Minio) -> None:
    print("Setting up MinIO buckets...")
    for bucket in [IMAGES_BUCKET, "documents"]:
        if not await minio.bucket_exists(bucket):
            await minio.make_bucket(bucket)
            print(f"  created bucket: {bucket}")
        else:
            print(f"  bucket exists: {bucket}")
    print()


async def upload_photo(
    minio: Minio,
    storage_key: str,
    label: str,
    color: tuple[int, int, int],
) -> None:
    image_bytes = generate_placeholder_image(label, color)
    await minio.put_object(
        bucket_name=IMAGES_BUCKET,
        object_name=storage_key,
        data=io.BytesIO(image_bytes),
        length=len(image_bytes),
        content_type="image/jpeg",
        metadata={"filename": storage_key.split("/")[-1]},
    )


# ---------------------------------------------------------------------------
# Seeders
# ---------------------------------------------------------------------------

async def seed_staff_users(conn: asyncpg.Connection) -> list[uuid.UUID]:
    print("  -> Seeding staff users...")
    ids = []
    for u in STAFF_USERS:
        row = await conn.fetchrow(
            """
            INSERT INTO staff_users (email, password, role, created_at, updated_at)
            VALUES ($1, $2, $3::staff_role, $4, $4)
            ON CONFLICT (email) DO UPDATE
                SET password   = EXCLUDED.password,
                    role       = EXCLUDED.role,
                    updated_at = EXCLUDED.updated_at
            RETURNING id
            """,
            u["email"], hash_password(u["password"]), u["role"], now(),
        )
        ids.append(row["id"])
        print(f"     [OK] {u['role']}: {u['email']}  password: {u['password']}")
    return ids


async def seed_mobile_users(conn: asyncpg.Connection) -> list[uuid.UUID]:
    print("  -> Seeding mobile users...")
    ids = []
    for u in MOBILE_USERS:
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, hashed_password, display_name, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $4)
            ON CONFLICT (email) DO UPDATE
                SET hashed_password = EXCLUDED.hashed_password,
                    display_name    = EXCLUDED.display_name,
                    updated_at      = EXCLUDED.updated_at
            RETURNING id
            """,
            u["email"], hash_password(u["password"]), u["display_name"], now(),
        )
        ids.append(row["id"])
        print(f"     [OK] {u['display_name']}: {u['email']}  password: {u['password']}")
    return ids


async def seed_devices_and_sessions(
    conn: asyncpg.Connection,
    user_ids: list[uuid.UUID],
) -> None:
    print("  -> Seeding devices + sessions...")
    for user_id in user_ids:
        device_id = await conn.fetchval(
            """
            INSERT INTO user_devices (user_id, device_name, device_type, last_active, created_at)
            VALUES ($1, 'Seed Device', 'android', $2, $2)
            RETURNING id
            """,
            user_id, now(),
        )
        await conn.execute(
            """
            INSERT INTO user_sessions (user_id, device_id, created_at, last_active, expires_at)
            VALUES ($1, $2, $3, $3, $4)
            ON CONFLICT (user_id, device_id) DO NOTHING
            """,
            user_id, device_id, now(), future(30),
        )
    print(f"     [OK] {len(user_ids)} device(s) + session(s)")


async def seed_events(
    conn: asyncpg.Connection,
    staff_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    print("  -> Seeding events...")
    ids = []
    for i, e in enumerate(EVENTS):
        row = await conn.fetchrow(
            """
            INSERT INTO events (name, event_code, event_date, status, created_by, created_at)
            VALUES ($1, $2, $3, $4::event_status, $5, $6)
            ON CONFLICT (event_code) DO UPDATE
                SET name       = EXCLUDED.name,
                    event_date = EXCLUDED.event_date,
                    status     = EXCLUDED.status
            RETURNING id
            """,
            e["name"], e["event_code"], e["event_date"],
            e["status"], staff_ids[i % len(staff_ids)], now(),
        )
        ids.append(row["id"])
        print(f"     [OK] {e['event_code']} — join code: {e['event_code']}")
    return ids


async def seed_event_participants(
    conn: asyncpg.Connection,
    event_ids: list[uuid.UUID],
    user_ids: list[uuid.UUID],
) -> None:
    print("  -> Seeding event participants...")
    count = 0
    for event_id in event_ids:
        for user_id in user_ids:
            await conn.execute(
                """
                INSERT INTO event_participants (event_id, user_id, joined_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (event_id, user_id) DO NOTHING
                """,
                event_id, user_id, now(),
            )
            count += 1
    print(f"     [OK] {count} participant record(s)")


async def seed_photos(
    conn: asyncpg.Connection,
    minio: Minio,
    event_ids: list[uuid.UUID],
    user_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    print("  -> Seeding photos + uploading to MinIO...")
    photo_ids = []
    color_index = 0
    for event_id in event_ids:
        for i in range(PHOTOS_PER_EVENT):
            uploader = user_ids[i % len(user_ids)]
            storage_key = make_storage_key(event_id, i + 1)
            color = PHOTO_COLORS[color_index % len(PHOTO_COLORS)]
            color_index += 1

            await upload_photo(
                minio, storage_key,
                f"Event {str(event_id)[:8]} / Photo {i + 1}",
                color,
            )

            row = await conn.fetchrow(
                """
                INSERT INTO photos
                    (event_id, uploaded_by, storage_key, taken_at, day_number,
                     visibility, status, created_at)
                VALUES ($1, $2, $3, $4, $5, 'public', 'approved', $6)
                RETURNING id
                """,
                event_id, uploader, storage_key, now(), i + 1, now(),
            )
            photo_ids.append(row["id"])
            print(f"     [OK] {storage_key}")
    return photo_ids


async def seed_photo_access(
    conn: asyncpg.Connection,
    photo_ids: list[uuid.UUID],
    user_ids: list[uuid.UUID],
) -> None:
    print("  -> Seeding photo access (face matches + approvals)...")
    face_count = match_count = approval_count = 0

    for photo_id in photo_ids:
        embedding = [random.uniform(-1.0, 1.0) for _ in range(512)]
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        face_row = await conn.fetchrow(
            """
            INSERT INTO photo_faces (photo_id, face_index, embedding, bbox, created_at)
            VALUES ($1, 0, $2::vector, $3, $4)
            ON CONFLICT (photo_id, face_index) DO NOTHING
            RETURNING id
            """,
            photo_id, embedding_str,
            '{"x1":10,"y1":10,"x2":100,"y2":100}', now(),
        )
        if face_row:
            face_count += 1
            for user_id in user_ids:
                await conn.execute(
                    """
                    INSERT INTO face_matches (photo_face_id, user_id, confidence, created_at)
                    VALUES ($1, $2, $3, $4)
                    """,
                    face_row["id"], user_id,
                    round(random.uniform(0.85, 0.99), 4), now(),
                )
                match_count += 1

        for user_id in user_ids:
            await conn.execute(
                """
                INSERT INTO photo_approvals (photo_id, user_id, decision, decided_at)
                VALUES ($1, $2, 'approved', $3)
                """,
                photo_id, user_id, now(),
            )
            approval_count += 1

    print(f"     [OK] {face_count} face(s), {match_count} match(es), {approval_count} approval(s)")


async def seed_user_photos(
    conn: asyncpg.Connection,
    photo_ids: list[uuid.UUID],
    user_ids: list[uuid.UUID],
) -> None:
    print("  -> Seeding user_photos...")
    count = 0
    for photo_id in photo_ids:
        for user_id in user_ids:
            await conn.execute(
                """
                INSERT INTO user_photos (user_id, photo_id, visibility, created_at)
                VALUES ($1, $2, 'public', $3)
                ON CONFLICT (user_id, photo_id) DO NOTHING
                """,
                user_id, photo_id, now(),
            )
            count += 1
    print(f"     [OK] {count} record(s)")


async def seed_processing_jobs(
    conn: asyncpg.Connection,
    photo_ids: list[uuid.UUID],
) -> None:
    print("  -> Seeding processing jobs...")
    count = 0
    for photo_id in photo_ids:
        for job_type in ["face_detection", "face_embedding"]:
            await conn.execute(
                """
                INSERT INTO processing_jobs
                    (photo_id, job_type, status, attempts, created_at, completed_at)
                VALUES ($1, $2, $3::processing_job_status, 1, $4, $4)
                """,
                photo_id, job_type, "completed", now(),
            )
            count += 1
    print(f"     [OK] {count} job(s)")


async def seed_notifications(
    conn: asyncpg.Connection,
    user_ids: list[uuid.UUID],
) -> None:
    print("  -> Seeding notifications...")
    for user_id in user_ids:
        await conn.execute(
            """
            INSERT INTO notifications (user_id, type, payload, created_at)
            VALUES ($1, 'welcome', '{"message": "Welcome to multAI!"}', $2)
            """,
            user_id, now(),
        )
    print(f"     [OK] {len(user_ids)} notification(s)")


async def seed_staff_notifications(
    conn: asyncpg.Connection,
    staff_ids: list[uuid.UUID],
) -> None:
    print("  -> Seeding staff notifications...")
    for staff_id in staff_ids:
        await conn.execute(
            """
            INSERT INTO staff_notifications (staff_user_id, type, payload, created_at)
            VALUES ($1, 'system', '{"message": "Staff account seeded."}', $2)
            """,
            staff_id, now(),
        )
    print(f"     [OK] {len(staff_ids)} notification(s)")


async def seed_upload_request_groups(
    conn: asyncpg.Connection,
    event_ids: list[uuid.UUID],
    staff_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    print("  -> Seeding upload request groups...")
    ids = []
    for i, event_id in enumerate(event_ids):
        row = await conn.fetchrow(
            """
            INSERT INTO upload_request_groups
                (event_id, folder_id, requested_by, approved_by, status,
                 total_photo_count, batch_count, processing_status, created_at, approved_at)
            VALUES ($1, $2, $3, $4, 'approved'::upload_request_status,
                    $5, 2, 'completed', $6, $6)
            RETURNING id
            """,
            event_id, f"gdrive_folder_{i + 1}",
            staff_ids[i % len(staff_ids)],
            staff_ids[(i + 1) % len(staff_ids)],
            PHOTOS_PER_EVENT, now(),
        )
        ids.append(row["id"])
    print(f"     [OK] {len(ids)} group(s)")
    return ids


async def seed_upload_requests(
    conn: asyncpg.Connection,
    event_ids: list[uuid.UUID],
    staff_ids: list[uuid.UUID],
    group_ids: list[uuid.UUID],
) -> list[uuid.UUID]:
    print("  -> Seeding upload requests...")
    ids = []
    for i, event_id in enumerate(event_ids):
        row = await conn.fetchrow(
            """
            INSERT INTO upload_requests
                (event_id, drive_file_id, requested_by, approved_by, status,
                 photo_count, group_id, created_at, approved_at)
            VALUES ($1, $2, $3, $4, 'approved'::upload_request_status, $5, $6, $7, $7)
            RETURNING id
            """,
            event_id, f"gdrive_file_{i + 1}",
            staff_ids[i % len(staff_ids)],
            staff_ids[(i + 1) % len(staff_ids)],
            PHOTOS_PER_EVENT,
            group_ids[i % len(group_ids)], now(),
        )
        ids.append(row["id"])
    print(f"     [OK] {len(ids)} request(s)")
    return ids


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary() -> None:
    print()
    print("=" * 55)
    print("  SEED COMPLETE - MOBILE TEAM QUICKSTART")
    print("=" * 55)
    print()
    print("Mobile users:")
    for u in MOBILE_USERS:
        print(f"  email:    {u['email']}")
        print(f"  password: {u['password']}")
        print()
    print("Events:")
    for e in EVENTS:
        print(f"  {e['name']}  join code: {e['event_code']}")
    print()
    print(f"Photos: {len(EVENTS) * PHOTOS_PER_EVENT} total — approved, public, gallery-ready")
    print()
    print("Staff users:")
    for u in STAFF_USERS:
        print(f"  [{u['role']}] {u['email']}  password: {u['password']}")
    print("=" * 55)
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main(reset: bool = False) -> None:
    dsn = (
        f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )

    minio = Minio(
        f"{settings.MINIO_HOST}:{settings.MINIO_API_PORT}",
        access_key=settings.MINIO_ROOT_USER,
        secret_key=settings.MINIO_ROOT_PASSWORD,
        secure=False,
    )

    print(f"Connecting to {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}...")
    conn: asyncpg.Connection = await asyncpg.connect(dsn)

    try:
        if reset:
            await reset_db(conn)
            await reset_minio(minio)

        await init_minio(minio)

        async with conn.transaction():
            print("Seeding...\n")

            staff_ids = await seed_staff_users(conn)
            user_ids  = await seed_mobile_users(conn)

            await seed_devices_and_sessions(conn, user_ids)

            event_ids = await seed_events(conn, staff_ids)
            await seed_event_participants(conn, event_ids, user_ids)

            photo_ids = await seed_photos(conn, minio, event_ids, user_ids)

            await seed_photo_access(conn, photo_ids, user_ids)
            await seed_user_photos(conn, photo_ids, user_ids)
            await seed_processing_jobs(conn, photo_ids)

            await seed_notifications(conn, user_ids)
            await seed_staff_notifications(conn, staff_ids)

            group_ids = await seed_upload_request_groups(conn, event_ids, staff_ids)
            await seed_upload_requests(conn, event_ids, staff_ids, group_ids)

        print_summary()

    except Exception as e:
        print(f"Seed failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    if reset_flag:
        print("WARNING: Reset mode — all existing seed data will be wiped.\n")
    asyncio.run(main(reset=reset_flag))
