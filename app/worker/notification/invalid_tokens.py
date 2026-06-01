from __future__ import annotations

from typing import Iterable, Sequence

from db.generated import devices as device_queries

from app.core.constant import RedisKey
from app.core.logger import logger
from app.infra.database import engine
from app.infra.redis import RedisClient
from app.worker.notification.settings import NotifSetting


class InvalidTokenStore:
    def __init__(self, redis: RedisClient) -> None:
        self._redis = redis

    async def mark_invalid(self, tokens: Iterable[str]) -> None:
        normalized: list[str] = [t for t in tokens if t]

        if not normalized:
            return

        await self._redis.sadd(RedisKey.INVALID_TOKEN_SET_KEY, *normalized)
        await self._redis.expire(RedisKey.INVALID_TOKEN_SET_KEY, NotifSetting.TTL_SECONDS)

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


class DeviceInvalidationStore:
    async def mark_invalid(self, tokens: Iterable[str]) -> None:
        normalized: list[str] = [t for t in tokens if t]

        if not normalized:
            return

        # One transaction per token. Handlers run concurrently, so each write
        # gets its own connection rather than sharing one, and a failure on one
        # token does not abort the rest.
        failed: list[str] = []
        for token in normalized:
            try:
                async with engine.begin() as conn:
                    await device_queries.AsyncQuerier(conn).mark_device_token_invalid(
                        push_token=token
                    )
            except Exception:
                failed.append(token)
                logger.exception("Failed to flag device for invalid token %s", token)

        marked = len(normalized) - len(failed)
        if marked:
            logger.warning("Flagged %d devices as invalid", marked)
