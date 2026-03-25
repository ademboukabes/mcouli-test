from __future__ import annotations

from typing import Iterable, Sequence

from app.core.constant import RedisKey
from app.core.logger import logger
from app.infra.redis import RedisClient


class InvalidTokenStore:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def mark_invalid(self, tokens: Iterable[str]) -> None:
        normalized: list[str] = [t for t in tokens if t]

        if not normalized:
            return

        await self._redis.sadd(RedisKey.INVALID_TOKEN_SET_KEY, *normalized)

        logger.warning("Marked %d tokens for cleanup", len(normalized))

    async def is_invalid(self, token: str) -> bool:
        if not token:
            return False

        return await self._redis.sismember(
            RedisKey.INVALID_TOKEN_SET_KEY, token
        )

    async def remove(self, tokens: Sequence[str]) -> None:
        if not tokens:
            return

        await self._redis.srem(
            RedisKey.INVALID_TOKEN_SET_KEY, *tokens
        )