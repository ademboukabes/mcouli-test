"""
Integration tests for the Enrollment Flow.

These tests use a real PostgreSQL database to verify that
the user's face embedding is correctly persisted in the database.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from app.service.users import AuthService
from app.service.face_embedding import FaceImagePayload
from db.generated import user as user_queries


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def mock_face_embedding() -> AsyncMock:
    from app.service.face_embedding import FaceEmbeddingService
    svc = MagicMock(spec=FaceEmbeddingService)
    # Return a dummy embedding of size 512
    svc.compute_average_embedding = AsyncMock(return_value=[0.1] * 512)
    return svc


@pytest.fixture
async def db_conn():
    from sqlalchemy.ext.asyncio import create_async_engine
    from app.core.config import settings
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()

@pytest.fixture
def auth_service(mock_face_embedding: AsyncMock, db_conn) -> AuthService:
    from db.generated import session as session_queries
    from db.generated import devices as device_queries

    return AuthService(
        user_querier=user_queries.AsyncQuerier(db_conn),
        session_querier=session_queries.AsyncQuerier(db_conn),
        device_querier=device_queries.AsyncQuerier(db_conn),
        face_embedding_service=mock_face_embedding,
    )


# ===========================================================================
# Tests
# ===========================================================================

# Mark these as integration tests (require DB)
pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_enrollment_persists_embedding(
    auth_service: AuthService,
    mock_face_embedding: AsyncMock,
    db_conn,
) -> None:
    """Test the happy path: add_embbed_user updates the user's face_embedding."""
    # 1. Setup: Create a user without an embedding
    user = await user_queries.AsyncQuerier(db_conn).create_user(
        email=f"test-enroll-{uuid.uuid4()}@multai.com",
        hashed_password="hash",
    )
    assert user is not None
    user_id = user.id

    # 2. Execute enrollment
    payload = FaceImagePayload(image_bytes=b"fake-image", filename="face.jpg")

    try:
        await auth_service.add_embbed_user(
            user_id=user_id,
            image_payloads=[payload],
        )

        # 3. Verify: The user should now have an embedding
        updated_user = await user_queries.AsyncQuerier(db_conn).get_user_by_id(id=user_id)
        assert updated_user is not None
        assert updated_user.face_embedding is not None
        assert "0.1" in str(updated_user.face_embedding)

        # Face embedding service should have been called
        mock_face_embedding.compute_average_embedding.assert_called_once()

    finally:
        # Cleanup
        await db_conn.rollback()
        await db_conn.execute(
            text(f"DELETE FROM users WHERE id = '{user_id}'")
        )
        await db_conn.commit()
