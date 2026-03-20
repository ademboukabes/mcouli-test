from datetime import datetime, timezone

from app.core.constant import RedisKey
from app.infra.redis import RedisClient


async def blacklist_session(
    redis: RedisClient,
    session_id: str,
    expires_at: datetime | None = None,
) -> None:
    ttl: int | None = None
    if expires_at is not None:
        ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())
        if ttl < 0:
            ttl = 0
    key = RedisKey.BlacklistedSession.value.format(session_id=session_id)
    await redis.set(key, "1", expire=ttl)


async def is_session_blacklisted(redis: RedisClient, session_id: str) -> bool:
    key = RedisKey.BlacklistedSession.value.format(session_id=session_id)
    return await redis.exists(key)
