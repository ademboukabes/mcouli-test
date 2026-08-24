import json
from typing import Any, AsyncGenerator

import sqlalchemy.ext.asyncio
from sqlalchemy import event
from app.core.config import settings


DATABASE_URL = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"


engine = sqlalchemy.ext.asyncio.create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    pool_pre_ping=True,
)


@event.listens_for(engine.sync_engine, "connect")
def _register_jsonb_codec(dbapi_connection: Any, connection_record: Any) -> None:
    # SQLAlchemy's asyncpg dialect doesn't forward connect_args={"init": ...}
    # to asyncpg (it raises TypeError: unexpected keyword argument 'init'),
    # so codec registration has to go through the wrapped connection's
    # run_async bridge instead. Without this, asyncpg neither accepts a
    # Python dict as a jsonb bind param (raises DataError) nor decodes a
    # jsonb column back into one (returns raw JSON text) — every jsonb
    # column in the schema (audit metadata, notification payloads) needs
    # both directions to work.
    dbapi_connection.run_async(
        lambda conn: conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
            format="text",
        )
    )


async def get_db() -> AsyncGenerator[sqlalchemy.ext.asyncio.AsyncConnection, None]:
    async with engine.begin() as conn:
        yield conn
