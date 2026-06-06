import asyncio
import uuid
import jwt
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text

from app.main import app
from app.core.config import settings
from db.generated import user as user_queries
from app.infra.database import engine
from app.infra.redis import RedisClient

pytestmark = pytest.mark.asyncio(loop_scope="session")

@pytest.fixture(scope="session", autouse=True)
async def setup_infra():
    # We must init Redis since ASGITransport doesn't trigger the lifespan
    try:
        RedisClient.init(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
        )
    except RuntimeError:
        pass # Already initialized
    yield
    await RedisClient.get_instance().close()

@pytest.fixture(scope="session")
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c

def create_mock_jwt(user_id: str, exp_delta_hours: int = 24) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(hours=exp_delta_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

async def test_jwt_validation_invalid_signature(client):
    """Test that a JWT with an invalid signature is rejected."""
    payload = {
        "sub": str(uuid.uuid4()),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    invalid_token = jwt.encode(payload, "wrong_secret_key", algorithm="HS256")
    
    # We must use "Bearer "
    response = await client.get(
        "/user/photos",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    assert response.status_code == 401
    assert "Invalid token" in response.text

async def test_jwt_validation_expired_token(client):
    """Test that an expired JWT is rejected."""
    expired_token = create_mock_jwt(str(uuid.uuid4()), exp_delta_hours=-1)
    
    response = await client.get(
        "/user/photos",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    assert response.status_code == 401
    assert "Token has expired" in response.text

async def test_blocked_user_access(client):
    """Test that a blocked user cannot access protected endpoints."""
    async with engine.begin() as conn:
        uq = user_queries.AsyncQuerier(conn)
        user = await uq.create_user(
            email=f"blocked-{uuid.uuid4()}@test.com",
            hashed_password="hash"
        )
        user_id = user.id
        
        # We need a session ID to put in the JWT, otherwise the auth dependency fails with "Invalid token"
        session_id = uuid.uuid4()
        
        await uq.set_user_blocked(blocked=True, id=user_id)
        
    payload = {
        "session_id": str(session_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
    
    try:
        response = await client.get(
            "/user/photos",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code in (401, 403), f"Expected 401 or 403, got {response.status_code}"
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DELETE FROM users WHERE id = '{user_id}'"))

async def test_rate_limiting(client):
    """Test that multiple requests within a short timeframe hit rate limits."""
    async with engine.begin() as conn:
        uq = user_queries.AsyncQuerier(conn)
        user = await uq.create_user(
            email=f"rate-{uuid.uuid4()}@test.com",
            hashed_password="hash"
        )
        user_id = user.id
        session_id = uuid.uuid4()

    payload = {
        "session_id": str(session_id),
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    try:
        responses = []
        # We test with enough requests to hit the 20/min limit
        for _ in range(25):
            res = await client.get(
                "/user/photos",
                headers={"Authorization": f"Bearer {token}"}
            )
            responses.append(res.status_code)
            
        assert 429 in responses, "Expected to hit rate limit (429) after multiple rapid requests"
    finally:
        async with engine.begin() as conn:
            await conn.execute(text(f"DELETE FROM users WHERE id = '{user_id}'"))
        try:
            redis = RedisClient.get_instance()
            await redis._client.delete("rate_limit:/user/photos:127.0.0.1")
            await redis._client.delete("rate_limit:/user/photos:testclient")
        except Exception:
            pass
