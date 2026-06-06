import asyncio
import json
import os
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

from tests.e2e.conftest import _seed_event_and_photo, _wait_for_job, _cleanup, FIXTURE_DIR

# ── tests ─────────────────────────────────────────────────────────────


async def test_photo_ai_pipeline_detects_0_faces() -> None:
    """Photo with no faces → auto-approved, visibility set to public."""
    photo_id = uuid.uuid4()
    storage_key = f"e2e_noface_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "noface.jpg"
    assert image_path.exists(), f"Fixture not found: {image_path}"

    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    await bucket.put_bytes(
        object_name=storage_key,
        data=image_path.read_bytes(),
        content_type="image/jpeg",
    )
    async with engine.begin() as conn:
        event_id = await _seed_event_and_photo(
            conn, photo_id=photo_id, storage_key=storage_key
        )

    payload = {"photo_id": str(photo_id), "image_ref": storage_key, "event_id": str(event_id)}
    await NatsClient.publish(NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8"))

    try:
        final_status = await _wait_for_job(photo_id)
        assert final_status == "completed", f"Job ended with: {final_status}"

        async with engine.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT status, visibility FROM photos WHERE id = :pid"),
                    {"pid": photo_id},
                )
            ).fetchone()
        assert row is not None
        assert row[0] == "approved", f"Expected 'approved', got {row[0]}"
        assert row[1] == "public", f"Expected visibility 'public', got {row[1]}"
    finally:
        async with engine.begin() as conn:
            await _cleanup(conn, photo_id=photo_id, event_id=event_id)
        try:
            await bucket.delete(storage_key)
        except Exception:
            pass


async def test_photo_ai_pipeline_detects_multiple_faces() -> None:
    """Group photo (multiple faces) → status stays 'pending' awaiting approval."""
    photo_id = uuid.uuid4()
    storage_key = f"e2e_group_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "group.jpg"
    assert image_path.exists(), f"Fixture not found: {image_path}"

    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    await bucket.put_bytes(
        object_name=storage_key,
        data=image_path.read_bytes(),
        content_type="image/jpeg",
    )
    async with engine.begin() as conn:
        event_id = await _seed_event_and_photo(
            conn, photo_id=photo_id, storage_key=storage_key
        )

    payload = {"photo_id": str(photo_id), "image_ref": storage_key, "event_id": str(event_id)}
    await NatsClient.publish(NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8"))

    try:
        final_status = await _wait_for_job(photo_id)
        assert final_status == "completed", f"Job ended with: {final_status}"

        async with engine.connect() as conn:
            photo_status = (
                await conn.execute(
                    text("SELECT status FROM photos WHERE id = :pid"),
                    {"pid": photo_id},
                )
            ).scalar()
        # Group photo → pending because multiple unverified faces require human approval
        assert photo_status == "pending", f"Expected 'pending', got {photo_status}"
    finally:
        async with engine.begin() as conn:
            await _cleanup(conn, photo_id=photo_id, event_id=event_id)
        try:
            await bucket.delete(storage_key)
        except Exception:
            pass


async def test_photo_ai_pipeline_matched_user() -> None:
    """Single face matching an enrolled user → 'approved' + notification created."""
    from app.service.face_embedding import FaceEmbeddingService, FaceImagePayload

    photo_id = uuid.uuid4()
    storage_key = f"e2e_matched_{photo_id}.jpg"
    image_path = FIXTURE_DIR / "face.jpg"
    assert image_path.exists(), f"Fixture not found: {image_path}"

    image_bytes = image_path.read_bytes()

    # Pre-compute the embedding so we can plant a matching user
    face_service = FaceEmbeddingService()
    payload_face = FaceImagePayload(
        filename="face.jpg", content_type="image/jpeg", bytes=image_bytes
    )
    faces = await face_service.detect_faces(payload_face)
    assert len(faces) == 1, f"Expected exactly 1 face in face.jpg, got {len(faces)}"
    embedding_literal = "[" + ", ".join(str(x) for x in faces[0].embedding) + "]"

    matched_user_id = "00000000-0000-0000-0000-000000000002"

    bucket = Bucket(IMAGES_BUCKET_NAME, "")
    await bucket.put_bytes(
        object_name=storage_key, data=image_bytes, content_type="image/jpeg"
    )

    async with engine.begin() as conn:
        event_id = await _seed_event_and_photo(
            conn, photo_id=photo_id, storage_key=storage_key
        )
        # Clean up any previous failed run artifacts for this user
        await conn.execute(
            text("DELETE FROM notifications WHERE user_id = :uid"),
            {"uid": matched_user_id},
        )
        await conn.execute(
            text("DELETE FROM face_matches WHERE user_id = :uid"),
            {"uid": matched_user_id},
        )
        await conn.execute(
            text("DELETE FROM users WHERE id = :uid"), {"uid": matched_user_id}
        )
        # Insert a user with the exact same embedding
        await conn.execute(
            text(
                """
                INSERT INTO users (id, email, hashed_password, face_embedding)
                VALUES (:uid, 'matched@test.com', 'hash', :emb)
                """
            ),
            {"uid": matched_user_id, "emb": embedding_literal},
        )

    payload = {"photo_id": str(photo_id), "image_ref": storage_key, "event_id": str(event_id)}
    await NatsClient.publish(NatsSubjects.PHOTO_PROCESS, json.dumps(payload).encode("utf-8"))

    try:
        final_status = await _wait_for_job(photo_id)
        assert final_status == "completed", f"Job ended with: {final_status}"

        async with engine.connect() as conn:
            photo_status = (
                await conn.execute(
                    text("SELECT status FROM photos WHERE id = :pid"),
                    {"pid": photo_id},
                )
            ).scalar()
            assert photo_status == "approved", (
                f"Expected 'approved', got {photo_status}"
            )

            matched_db_user = (
                await conn.execute(
                    text(
                        """
                        SELECT fm.user_id
                        FROM face_matches fm
                        JOIN photo_faces pf ON pf.id = fm.photo_face_id
                        WHERE pf.photo_id = :pid
                        """
                    ),
                    {"pid": photo_id},
                )
            ).scalar()
            assert str(matched_db_user) == matched_user_id, (
                f"Expected matched user {matched_user_id}, got {matched_db_user}"
            )

            notif_count = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM notifications "
                        "WHERE user_id = :uid AND type = 'face_match'"
                    ),
                    {"uid": matched_user_id},
                )
            ).scalar()
            assert notif_count == 1, f"Expected 1 notification, got {notif_count}"
    finally:
        async with engine.begin() as conn:
            await _cleanup(
                conn,
                photo_id=photo_id,
                event_id=event_id,
                user_id=matched_user_id,
            )
        try:
            await bucket.delete(storage_key)
        except Exception:
            pass
