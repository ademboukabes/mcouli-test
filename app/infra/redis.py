from redis.asyncio import Redis
from app.core.constant import RedisKey


class RedisClient:
    client: Redis
    _instance = None

    def __new__(cls, *args, **kwargs) -> "RedisClient":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, host: str, port: int, password: str) -> None:
        if not hasattr(self, "client"):
            self.client = Redis.from_url(
                f"redis://{host}:{port}", password=password, decode_responses=True
            )

    async def set(
        self,
        key: RedisKey | str,
        value: str,
        expire: int | None = None,
        nx: bool = False,
    ) -> bool:
        return await self.client.set(key, value, ex=expire, nx=nx)

    async def get(self, key: RedisKey | str) -> str | None:
        return await self.client.get(key)

    async def delete(self, key: RedisKey | str) -> int:
        return await self.client.delete(key)

    async def exists(self, key: RedisKey | str) -> bool:
        return await self.client.exists(key) > 0

    async def expire(self, key: RedisKey | str, seconds: int) -> bool:
        return await self.client.expire(key, seconds)

    @classmethod
    def get_instance(cls) -> "RedisClient":
        if cls._instance is None:
            raise RuntimeError("RedisClient not initialized")
        return cls._instance

    async def close(self) -> None:
        await self.client.close()
