from __future__ import annotations
from typing import Iterable
from redis.asyncio import Redis
from app.core.logger import logger
from app.core.constant import RedisKey



class InvalidTokenStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def mark_invalid(self, tokens: Iterable[str]) -> None:
        normalized = [token for token in tokens if token]
        if not normalized:
            return
        await self._redis.sadd(RedisKey.INVALID_TOKEN_SET_KEY, *normalized)
        logger.warning("Marked %d tokens for cleanup", len(normalized))
