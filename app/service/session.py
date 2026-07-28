from pydantic import BaseModel
from app.core.exceptions import AppException, DBExceptionImpl
from db.generated import session as session_queries
import uuid
from db.generated.models import UserSession
from datetime import datetime
from app.infra.redis import RedisClient
from app.core.constant import RedisKey
from app.core.logger import logger


class MobileSessionCache(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    idle_expires_at: datetime
    absolute_expires_at: datetime
    blocked: bool
    last_active: datetime


class SessionService:
    def __init__(
        self,
        session_querier: session_queries.AsyncQuerier,
        redis: RedisClient,
    ) -> None:
        self.session_querier = session_querier
        self.redis = redis

    @staticmethod
    async def cache_session_for_auth(
        redis: RedisClient,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        email: str,
        idle_expires_at: datetime,
        absolute_expires_at: datetime,
        blocked: bool,
        ttl: int,
        last_active: datetime,
    ) -> None:
        key = RedisKey.MobileSessionCache.value.format(session_id=session_id)
        payload = MobileSessionCache(
            session_id=session_id,
            user_id=user_id,
            email=email,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
            blocked=blocked,
            last_active=last_active,
        )
        try:
            await redis.set(key=key, value=payload.model_dump_json(), expire=ttl)
        except Exception:
            logger.warning(
                "cache_session_for_auth: redis unavailable, session_id=%s", session_id
            )

    @staticmethod
    async def get_cached_session(
        redis: RedisClient,
        session_id: uuid.UUID,
    ) -> MobileSessionCache | None:
        key = RedisKey.MobileSessionCache.value.format(session_id=session_id)
        try:
            raw = await redis.get(key)
        except Exception:
            logger.warning(
                "get_cached_session: redis unavailable, session_id=%s", session_id
            )
            return None  # caller falls through to Postgres
        if raw is None:
            return None
        return MobileSessionCache.model_validate_json(raw)

    @staticmethod
    async def delete_session_cache(
        redis: RedisClient,
        session_id: uuid.UUID,
    ) -> None:
        key = RedisKey.MobileSessionCache.value.format(session_id=session_id)
        try:
            await redis.delete(key)
        except Exception:
            logger.warning(
                "delete_session_cache: redis unavailable, session_id=%s", session_id
            )

    async def get_session_by_id(self, session_id: uuid.UUID) -> UserSession:
        try:
            session = await self.session_querier.get_session_by_id(id=session_id)
            if session is None:
                raise AppException.not_found("session not found")
            return session
        except Exception as e:
            raise DBExceptionImpl.handle(e)

    async def count_user_sessions(self, user_id: uuid.UUID) -> int:
        try:
            count = await self.session_querier.count_user_sessions(user_id=user_id)
            if count is None:
                raise AppException.internal_error("failed to count")
            return count
        except Exception as e:
            raise DBExceptionImpl.handle(e)
