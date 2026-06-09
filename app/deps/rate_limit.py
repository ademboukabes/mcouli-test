from fastapi import Request, HTTPException
from typing import Callable

from app.infra.redis import RedisClient

def RateLimiter(requests: int, window: int) -> Callable:
    async def _rate_limit_dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "127.0.0.1"
        # We can also use user_id if we wanted to rate-limit per user, but IP is general.
        # For simplicity, IP based rate limit on the endpoint
        path = request.url.path
        key = f"rate_limit:{path}:{client_ip}"

        redis = RedisClient.get_instance()

        # Increment request count
        current = await redis.incr(key)
        if current == 1:
            # Set expiry for the window if it's the first request
            await redis.expire(key, window)

        if current > requests:
            raise HTTPException(status_code=429, detail="Too Many Requests")

    return _rate_limit_dependency
