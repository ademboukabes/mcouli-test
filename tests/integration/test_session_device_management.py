"""
Integration tests for session & device management.

These tests use a real PostgreSQL database (not fakes) specifically because
the behaviors under test depend on real SQL semantics that a fake cannot
verify: the UpsertSession ON CONFLICT clause actually matching the live
UNIQUE(user_id, device_id) constraint, and the user_sessions.device_id FK
actually being ON DELETE CASCADE. Both were previously verified by hand via
psql; these tests make that verification automatic and regression-proof.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text

from app.core.securite import hash_password
from app.schema.request.mobile.auth import MobileLoginRequest
from app.service.users import AuthService
from db.generated import devices as device_queries
from db.generated import session as session_queries
from db.generated import user as user_queries

pytestmark = pytest.mark.integration


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
async def db_conn():
    from app.core.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine

    url = (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.connect() as conn:
        yield conn
    await engine.dispose()


@pytest.fixture
def mock_face_embedding() -> AsyncMock:
    from app.service.face_embedding import FaceEmbeddingService

    svc = MagicMock(spec=FaceEmbeddingService)
    return svc


@pytest.fixture
def auth_service(mock_face_embedding: AsyncMock, db_conn) -> AuthService:
    return AuthService(
        user_querier=user_queries.AsyncQuerier(db_conn),
        session_querier=session_queries.AsyncQuerier(db_conn),
        device_querier=device_queries.AsyncQuerier(db_conn),
        face_embedding_service=mock_face_embedding,
    )


class _FakeRedis:
    """Minimal redis stand-in — no rate-limit backing store or cache
    assertions needed for these tests, just enough for the login flow
    to complete without touching a real Redis instance."""

    def __init__(self) -> None:
        self._store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, seconds: int) -> None:
        pass

    async def ttl(self, key: str) -> int:
        return -1

    async def set(self, key: str, value: str, expire: int) -> None:
        return None

    async def get(self, key: str) -> str | None:
        return None

    async def delete(self, key: str) -> None:
        return None


# ===========================================================================
# Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_relogin_on_same_device_replaces_not_duplicates_real_db(
    auth_service: AuthService,
    db_conn,
) -> None:
    """Regression test against the real UpsertSession query: logging in twice
    from the same (user, physical_device_id) must produce exactly one
    session row with a stable id, not two rows — verifying the live
    UNIQUE(user_id, device_id) constraint and ON CONFLICT clause actually
    match, which a fake-based unit test cannot verify."""
    password = "ValidPass@123"
    email = f"test-session-{uuid.uuid4()}@multai.com"
    physical_device_id = uuid.uuid4()

    user = await user_queries.AsyncQuerier(db_conn).create_user(
        email=email,
        hashed_password=hash_password(password),
    )
    assert user is not None
    user_id = user.id

    try:
        req = MobileLoginRequest(
            email=email,
            password=password,
            device_name="Integration Test Device",
            device_type="android",
            physical_device_id=physical_device_id,
        )

        result1 = await auth_service.mobile_login(_FakeRedis(), req)
        result2 = await auth_service.mobile_login(_FakeRedis(), req)

        assert result1.session_id == result2.session_id

        row = (
            await db_conn.execute(
                text("SELECT COUNT(*) FROM user_sessions WHERE user_id = :uid"),
                {"uid": user_id},
            )
        ).scalar()
        assert row == 1

        device_row = (
            await db_conn.execute(
                text("SELECT COUNT(*) FROM user_devices WHERE user_id = :uid"),
                {"uid": user_id},
            )
        ).scalar()
        assert device_row == 1
    finally:
        await db_conn.execute(
            text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(
            text("DELETE FROM user_devices WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await db_conn.commit()


@pytest.mark.asyncio
async def test_revoke_device_cascades_delete_session_real_db(
    db_conn,
) -> None:
    """Regression test verifying user_sessions_device_id_fkey is genuinely
    ON DELETE CASCADE: deleting a device row via the real revoke_device
    query must also delete its session row, with no separate DELETE
    needed. Previously verified once by hand via psql \\d user_sessions;
    this makes it automatic."""
    email = f"test-revoke-{uuid.uuid4()}@multai.com"

    user_querier = user_queries.AsyncQuerier(db_conn)
    device_querier = device_queries.AsyncQuerier(db_conn)
    session_querier = session_queries.AsyncQuerier(db_conn)

    user = await user_querier.create_user(email=email, hashed_password="hash")
    assert user is not None
    user_id = user.id

    try:
        device = await device_querier.create_device(
            arg=device_queries.CreateDeviceParams(
                column_1=None,
                user_id=user_id,
                device_name="Integration Test Device",
                device_type="android",
                totp_secret=None,
                physical_device_id=uuid.uuid4(),
            )
        )
        assert device is not None

        session = await session_querier.upsert_session(
            user_id=user_id,
            device_id=device.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        assert session is not None
        session_id = session.id

        # Confirm the session actually exists before we revoke.
        pre = await session_querier.get_session_by_id(id=session_id)
        assert pre is not None

        await device_querier.revoke_device(id=device.id, user_id=user_id)

        post = await session_querier.get_session_by_id(id=session_id)
        assert post is None

        device_still_there = (
            await db_conn.execute(
                text("SELECT COUNT(*) FROM user_devices WHERE id = :did"),
                {"did": device.id},
            )
        ).scalar()
        assert device_still_there == 0
    finally:
        await db_conn.execute(
            text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(
            text("DELETE FROM user_devices WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await db_conn.commit()

@pytest.mark.asyncio
async def test_concurrent_new_device_logins_settle_at_cap_real_db(
    auth_service: AuthService,
    db_conn,
) -> None:
    """Stress test for EvictOldestSessions with SKIP LOCKED: multiple
    simultaneous logins from distinct new devices must never overshoot the
    session cap, and the final session set must be exactly SESSION_LIMIT rows.
    This is the only test that exercises the real Postgres locking behavior
    that the design depends on — a fake cannot verify this."""
    from app.core.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine

    password = "ValidPass@123"
    email = f"test-concurrent-{uuid.uuid4()}@multai.com"
    physical_device_id = uuid.uuid4()

    user = await user_queries.AsyncQuerier(db_conn).create_user(
        email=email,
        hashed_password=hash_password(password),
    )
    assert user is not None
    user_id = user.id

    # Pre-seed one session so we start exactly at cap-1.
    cap = AuthService.SESSION_LIMIT
    pre_seed_device = await device_queries.AsyncQuerier(db_conn).create_device(
        arg=device_queries.CreateDeviceParams(
            column_1=None,
            user_id=user_id,
            device_name="Pre-seed Device",
            device_type="android",
            totp_secret=None,
            physical_device_id=physical_device_id,
        )
    )
    await session_queries.AsyncQuerier(db_conn).upsert_session(
        user_id=user_id,
        device_id=pre_seed_device.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )

    # CRITICAL: Commit the setup transaction so the user/device/session rows
    # are visible to the separate connections used by concurrent tasks.
    await db_conn.commit()

    assert cap >= 2, "SESSION_LIMIT must be >= 2 for this test to be meaningful"
    concurrent_logins = cap

    # Need separate connections for true concurrency — asyncpg can't multiplex
    # on a single connection. Each task gets its own connection from the engine.
    url = (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    engine = create_async_engine(url, pool_pre_ping=True)

    async def _login_task(task_idx: int) -> None:
        async with engine.connect() as conn:
            task_auth = AuthService(
                user_querier=user_queries.AsyncQuerier(conn),
                session_querier=session_queries.AsyncQuerier(conn),
                device_querier=device_queries.AsyncQuerier(conn),
                face_embedding_service=auth_service.face_embedding_service,
            )
            req = MobileLoginRequest(
                email=email,
                password=password,
                device_name=f"Concurrent Device {task_idx}",
                device_type="ios",
                physical_device_id=uuid.uuid4(),
            )
            await task_auth.mobile_login(_FakeRedis(), req)
            await conn.commit()

    try:
        await asyncio.gather(*(_login_task(i) for i in range(concurrent_logins)))

        count = (
            await db_conn.execute(
                text("SELECT COUNT(*) FROM user_sessions WHERE user_id = :uid"),
                {"uid": user_id},
            )
        ).scalar()
        assert count == cap, (
            f"Expected exactly {cap} sessions after concurrent logins, got {count}"
        )
    finally:
        await engine.dispose()
        await db_conn.execute(
            text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(
            text("DELETE FROM user_devices WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await db_conn.commit()

@pytest.mark.asyncio
async def test_concurrent_block_and_login_never_leaves_blocked_user_with_session(
    db_conn,
) -> None:
    """The race this test exists for: block_user and mobile_login racing on
    the same user. Regardless of which wins the timing, a user that ends up
    blocked must never retain an active session — that would mean a login
    slipped through the row-lock re-check and created a session after
    block_user's cleanup already ran. Repeated because this is a genuine
    timing race, not deterministic on a single run."""
    from app.core.config import settings
    from app.service.users import AuthService
    from sqlalchemy.ext.asyncio import create_async_engine

    url = (
        f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    engine = create_async_engine(url, pool_pre_ping=True)

    async def _run_one_trial() -> None:
        password = "ValidPass@123"
        email = f"test-block-race-{uuid.uuid4()}@multai.com"

        user = await user_queries.AsyncQuerier(db_conn).create_user(
            email=email, hashed_password=hash_password(password),
        )
        assert user is not None
        user_id = user.id
        await db_conn.commit()

        async def _login() -> None:
            async with engine.connect() as conn:
                svc = AuthService(
                    user_querier=user_queries.AsyncQuerier(conn),
                    session_querier=session_queries.AsyncQuerier(conn),
                    device_querier=device_queries.AsyncQuerier(conn),
                    face_embedding_service=MagicMock(),
                )
                req = MobileLoginRequest(
                    email=email, password=password,
                    device_name="Race Device", device_type="android",
                    physical_device_id=uuid.uuid4(),
                )
                try:
                    await svc.mobile_login(_FakeRedis(), req)
                except Exception:
                    pass
                await conn.commit()

        async def _block() -> None:
            async with engine.connect() as conn:
                svc = AuthService(
                    user_querier=user_queries.AsyncQuerier(conn),
                    session_querier=session_queries.AsyncQuerier(conn),
                    device_querier=device_queries.AsyncQuerier(conn),
                    face_embedding_service=MagicMock(),
                )
                await svc.block_user(redis=_FakeRedis(), user_id=user_id)
                await conn.commit()

        await asyncio.gather(_login(), _block())

        blocked = (
            await db_conn.execute(
                text("SELECT blocked FROM users WHERE id = :uid"), {"uid": user_id}
            )
        ).scalar()
        session_count = (
            await db_conn.execute(
                text("SELECT COUNT(*) FROM user_sessions WHERE user_id = :uid"),
                {"uid": user_id},
            )
        ).scalar()

        await db_conn.execute(
            text("DELETE FROM user_sessions WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(
            text("DELETE FROM user_devices WHERE user_id = :uid"), {"uid": user_id}
        )
        await db_conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        await db_conn.commit()

        if blocked:
            assert session_count == 0, (
                "A blocked user retained an active session — the row-lock "
                "re-check in mobile_login did not close the race."
            )

    try:
        for _ in range(20):
            await _run_one_trial()
    finally:
        await engine.dispose()
