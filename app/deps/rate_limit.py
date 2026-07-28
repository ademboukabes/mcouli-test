from fastapi import Request, HTTPException
from typing import Callable

from app.deps.client_ip import get_client_ip
from app.infra.redis import RedisClient
from app.core.logger import logger

def RateLimiter(requests: int, window: int) -> Callable:
    async def _rate_limit_dependency(request: Request) -> None:
        client_ip = get_client_ip(request) or "127.0.0.1"
        path = request.url.path
        key = f"rate_limit:{path}:{client_ip}"

        redis = RedisClient.get_instance()

        try:
            current = await redis.incr(key)
            if current == 1:
                await redis.expire(key, window)
        except HTTPException:
            raise
        except Exception:
            logger.warning("rate_limit: redis unavailable, failing open for key=%s", key)
            return

        if current > requests:
            raise HTTPException(status_code=429, detail="Too Many Requests")

    return _rate_limit_dependency
