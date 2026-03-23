from datetime import datetime

from app.infra.redis import RedisClient


# Deprecated: sessions are validated against the database as the source of truth.
# Keep these helpers as no-ops to avoid breaking callers while we remove usage.
async def blacklist_session(
    redis: RedisClient,
    session_id: str,
    expires_at: datetime | None = None,
) -> None:
    _ = (redis, session_id, expires_at)
    return None


async def is_session_blacklisted(redis: RedisClient, session_id: str) -> bool:
    _ = (redis, session_id)
    return False
