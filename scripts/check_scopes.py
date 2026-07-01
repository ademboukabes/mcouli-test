import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings

async def main():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url)
    
    async with engine.connect() as conn:
        import sqlalchemy
        row = (await conn.execute(sqlalchemy.text("SELECT google_email, scopes FROM staff_drive_connections LIMIT 1"))).fetchone()
        if row:
            print(f"Email: {row[0]}, Scopes: {row[1]}")
        else:
            print("No connection found")

asyncio.run(main())
