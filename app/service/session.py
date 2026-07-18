from pydantic import BaseModel
from app.core.exceptions import AppException, DBExceptionImpl
from db.generated import session as session_queries
import uuid
from db.generated.models import UserSession
from datetime import datetime
from app.infra.redis import RedisClient
from app.core.constant import RedisKey


class MobileSessionCache(BaseModel):
    session_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    expires_at: datetime
    blocked: bool
    last_active: datetime


class SessionService:
    session_querier: session_queries.AsyncQuerier
    redis: RedisClient

    def init(self, session: session_queries.AsyncQuerier, redis: RedisClient) -> None:
        self.session_querier = session
        self.redis = redis
        SessionService.session_querier = session
        SessionService.redis = redis

    @staticmethod
    async def cache_session_for_auth(
        redis: RedisClient,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        email: str,
        expires_at: datetime,
        blocked: bool,
        ttl: int,
        last_active: datetime
    ) -> None:
        key = RedisKey.MobileSessionCache.value.format(session_id=session_id)
        payload = MobileSessionCache(
            session_id=session_id,
            user_id=user_id,
            email=email,
            expires_at=expires_at,
            blocked=blocked,
            last_active=last_active
        )
        await redis.set(key=key, value=payload.model_dump_json(), expire=ttl)

    @staticmethod
    async def get_cached_session(
        redis: RedisClient,
        session_id: uuid.UUID,
    ) -> MobileSessionCache | None:
        key = RedisKey.MobileSessionCache.value.format(session_id=session_id)
        raw = await redis.get(key)
        if raw is None:
            return None
        return MobileSessionCache.model_validate_json(raw)

    @staticmethod
    async def delete_session_cache(
        redis: RedisClient,
        session_id: uuid.UUID,
    ) -> None:
        key = RedisKey.MobileSessionCache.value.format(session_id=session_id)
        await redis.delete(key)

    @staticmethod
    async def get_session_by_id(session_id: uuid.UUID) -> UserSession:
        try:
            session = await SessionService.session_querier.get_session_by_id(id=session_id)
            if session is None:
                raise AppException.not_found("session Not found ")
            return session
        except Exception as e:
            raise DBExceptionImpl.handle(e)

    @staticmethod
    async def delete_expired_sessions() -> None:
        try:
            await SessionService.session_querier.delete_expired_sessions()
        except Exception as e:
            raise DBExceptionImpl.handle(e)

    @staticmethod
    async def count_user_sessions(user_id: uuid.UUID) -> int:
        try:
            count = await SessionService.session_querier.count_user_sessions(user_id=user_id)
            if count is None:
                raise AppException.internal_error("failed to count ")
            else:
                return count
        except Exception as e:
            raise DBExceptionImpl.handle(e)
