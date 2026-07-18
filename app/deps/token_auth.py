from datetime import datetime, timezone
from typing import Annotated
import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.container import get_container, Container
from app.core.config import settings
from app.core.securite import decode_access_mobile_token
from app.infra.redis import RedisClient
from app.service.session import MobileSessionCache, SessionService

security = HTTPBearer()


class MobileUserSchema(BaseModel):
    user_id: uuid.UUID
    email: str
    session_id: uuid.UUID


async def get_current_mobile_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    container: Annotated[Container, Depends(get_container)],
) -> MobileUserSchema:
    """
    Dependency to get the current logged-in mobile user.
    Fast path: Redis cache hit. Usually 0 DB queries; occasionally 1 cheap,
    throttled UPDATE to last_active (see SESSION_ACTIVITY_THROTTLE_SECONDS) —
    this is not a full round trip through the slow path, just a single
    indexed write on the request's existing connection.
    Slow path: Postgres fallback (2 DB queries) with cache re-population.
    """
    token = credentials.credentials
    payload = decode_access_mobile_token(token)
    session_id_str = payload.get("session_id")

    if not session_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")

    session_id = uuid.UUID(session_id_str)

    # --- Fast path: Redis cache ---
    redis = RedisClient.get_instance()
    cached: MobileSessionCache | None = await SessionService.get_cached_session(
        redis, session_id
    )
    if cached is not None:
        if cached.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Session expired")
        if cached.blocked:
            raise HTTPException(status_code=403, detail="User is blocked")

        now = datetime.now(timezone.utc)
        if (now - cached.last_active).total_seconds() > settings.SESSION_ACTIVITY_THROTTLE_SECONDS:
            await container.session_service.session_querier.update_session_activity(
                id=cached.session_id
            )
            await SessionService.cache_session_for_auth(
                redis=redis,
                session_id=cached.session_id,
                user_id=cached.user_id,
                email=cached.email,
                expires_at=cached.expires_at,
                blocked=cached.blocked,
                ttl=settings.MOBILE_SESSION_TTL_SECONDS,
                last_active=now,
            )

        return MobileUserSchema(
            user_id=cached.user_id,
            email=cached.email,
            session_id=cached.session_id,
        )

    # --- Slow path: Postgres fallback ---
    session = await container.session_service.session_querier.get_session_by_id(id=session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Session not found")

    exp_ts = payload.get("exp")
    if exp_ts and session.expires_at.timestamp() < exp_ts:
        raise HTTPException(status_code=401, detail="Session expired")

    user = await container.auth_service.user_querier.get_user_by_id(id=session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.blocked:
        raise HTTPException(status_code=403, detail="User is blocked")

    # Re-populate cache so next request hits Redis. The session row was just
    # fetched fresh from Postgres, so its last_active is already accurate —
    # no extra write needed here, only cache population.
    await SessionService.cache_session_for_auth(
        redis=redis,
        session_id=session.id,
        user_id=session.user_id,
        email=user.email or "",
        expires_at=session.expires_at,
        blocked=user.blocked,
        ttl=settings.MOBILE_SESSION_TTL_SECONDS,
        last_active=session.last_active,
    )

    return MobileUserSchema(
        user_id=user.id,
        email=user.email or "",
        session_id=session.id,
    )
