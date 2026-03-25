from typing import cast, ClassVar

from redis.asyncio import Redis

from app.core.constant import RedisKey


class RedisClient:
    _client: Redis
    _instance: ClassVar["RedisClient | None"] = None

    def __init__(self, host: str, port: int, password: str) -> None:
        self._client = Redis.from_url( # type: ignore
            f"redis://{host}:{port}",
            password=password,
            decode_responses=True,
        )


    @classmethod
    def init(cls, host: str, port: int, password: str) -> "RedisClient":
        if cls._instance is not None:
            raise RuntimeError("RedisClient already initialized")

        cls._instance = cls(host, port, password)
        return cls._instance

    @classmethod
    def get_instance(cls) -> "RedisClient":
        if cls._instance is None:
            raise RuntimeError("RedisClient not initialized")

        return cls._instance


    async def set(
        self,
        key: RedisKey | str,
        value: str,
        expire: int | None = None,
        nx: bool = False,
    ) -> bool:
        result = await self._client.set(key, value, ex=expire, nx=nx)
        return bool(result)

    async def get(self, key: RedisKey | str) -> str | None:
        return await self._client.get(key)

    async def delete(self, key: RedisKey | str) -> int:
        result = await self._client.delete(key)
        return int(cast(int, result))

    async def exists(self, key: RedisKey | str) -> bool:
        result = await self._client.exists(key)
        return int(cast(int, result)) > 0

    async def expire(self, key: RedisKey | str, seconds: int) -> bool:
        result = await self._client.expire(key, seconds)
        return int(cast(int, result)) == 1


    async def sadd(self, key: RedisKey | str, *values: str) -> int:
        result =  self._client.sadd(key, *values)
        return int(cast(int, result))

    async def sismember(self, key: RedisKey | str, value: str) -> bool:
        result =  self._client.sismember(key, value)
        return int(cast(int, result)) == 1

    async def srem(self, key: RedisKey | str, *values: str) -> int:
        result =  self._client.srem(key, *values)
        return int(cast(int, result))


    async def close(self) -> None:
        await self._client.close()