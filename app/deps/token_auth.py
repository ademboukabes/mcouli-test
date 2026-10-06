from datetime import datetime, timedelta, timezone
from typing import Annotated
import uuid

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.container import Container, get_container
from app.core.config import settings
from app.core.securite import decode_access_mobile_token
from app.infra.redis import RedisClient
from app.schema.response.mobile.auth import MobileUserSchema
from app.service.session import MobileSessionCache, SessionService

security = HTTPBearer()


def _check_session_validity(
    idle_expires_at: datetime,
    absolute_expires_at: datetime,
    blocked: bool,
) -> None:
    now = datetime.now(timezone.utc)
    if idle_expires_at < now or absolute_expires_at < now:
        raise HTTPException(status_code=401, detail="Session expired")
    if blocked:
        raise HTTPException(status_code=403, detail="User is blocked")


async def _validate_mcdi_session(
    container: Container,
    redis: RedisClient,
    mcdi_token: str | None,
) -> None:
    if not mcdi_token:
        return
    try:
        await container.mcdi_service.validate_token_cached(
            redis=redis,
            token=mcdi_token,
            ttl_seconds=300,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="MCDI session invalid or expired")


async def _touch_session_activity(
    container: Container,
    redis: RedisClient,
    cached: MobileSessionCache,
    now: datetime,
) -> None:
    if (now - cached.last_active).total_seconds() <= settings.SESSION_ACTIVITY_THROTTLE_SECONDS:
        return

    new_idle_expires_at = min(
        now + timedelta(days=settings.MOBILE_SESSION_DAYS),
        cached.absolute_expires_at,
    )
    await container.session_service.session_querier.update_session_activity(
        id=cached.session_id,
        idle_expires_at=new_idle_expires_at,
    )
    await SessionService.cache_session_for_auth(
        redis=redis,
        session_id=cached.session_id,
        user_id=cached.user_id,
        email=cached.email,
        idle_expires_at=new_idle_expires_at,
        absolute_expires_at=cached.absolute_expires_at,
        blocked=cached.blocked,
        ttl=settings.MOBILE_SESSION_TTL_SECONDS,
        last_active=now,
        mcdi_token=cached.mcdi_token,
    )


async def get_current_mobile_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    container: Annotated[Container, Depends(get_container)],
) -> MobileUserSchema:
    """
    Dependency to get the current logged-in mobile user.
    Fast path: Redis cache hit. Usually 0 DB queries; throttled touch to last_active.
    Slow path: Postgres fallback with cache re-population.
    """
    token = credentials.credentials
    payload = decode_access_mobile_token(token)
    session_id_str = payload.get("session_id")

    if not session_id_str:
        raise HTTPException(status_code=401, detail="Invalid token")

    session_id = uuid.UUID(session_id_str)
    redis = RedisClient.get_instance()

    # --- Fast path: Redis cache ---
    cached: MobileSessionCache | None = await SessionService.get_cached_session(
        redis, session_id
    )
    if cached is not None:
        _check_session_validity(
            cached.idle_expires_at,
            cached.absolute_expires_at,
            cached.blocked,
        )
        await _validate_mcdi_session(container, redis, cached.mcdi_token)
        await _touch_session_activity(container, redis, cached, datetime.now(timezone.utc))

        return MobileUserSchema(
            user_id=cached.user_id,
            email=cached.email,
            session_id=cached.session_id,
        )

    # --- Slow path: Postgres fallback ---
    session = await container.session_service.session_querier.get_session_by_id(
        id=session_id
    )
    if not session:
        raise HTTPException(status_code=401, detail="Session not found")

    user = await container.auth_service.user_querier.get_user_by_id(id=session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    _check_session_validity(
        session.idle_expires_at,
        session.absolute_expires_at,
        user.blocked,
    )

    await SessionService.cache_session_for_auth(
        redis=redis,
        session_id=session.id,
        user_id=session.user_id,
        email=user.email or "",
        idle_expires_at=session.idle_expires_at,
        absolute_expires_at=session.absolute_expires_at,
        blocked=user.blocked,
        ttl=settings.MOBILE_SESSION_TTL_SECONDS,
        last_active=session.last_active,
        mcdi_token=None,
    )

    return MobileUserSchema(
        user_id=user.id,
        email=user.email or "",
        session_id=session.id,
    )


async def require_onboarded_mobile_user(
    current_user: Annotated[MobileUserSchema, Depends(get_current_mobile_user)],
    container: Annotated[Container, Depends(get_container)],
) -> MobileUserSchema:
    """Gate for endpoints that require a completed face enrollment."""
    user = await container.auth_service.user_querier.get_user_by_id(
        id=current_user.user_id
    )
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    if user.face_embedding is None:
        raise HTTPException(
            status_code=403,
            detail="Complete face enrollment before accessing this resource",
        )
    return current_user
