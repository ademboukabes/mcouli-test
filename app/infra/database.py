from typing import AsyncGenerator
import sqlalchemy.ext.asyncio
from app.core.config import settings


DATABASE_URL = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"


engine = sqlalchemy.ext.asyncio.create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
)


async def get_db() -> AsyncGenerator[sqlalchemy.ext.asyncio.AsyncConnection, None]:
    async with engine.begin() as conn:
        yield conn
