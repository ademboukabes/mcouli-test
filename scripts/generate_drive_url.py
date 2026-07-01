import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from db.generated import stuff_user as staff_queries
from app.infra.redis import RedisClient
from app.service.staff_drive import StaffDriveService
from db.generated import staff_drive_connections as drive_queries

async def main():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url)
    
    # Init redis
    RedisClient.init(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD or "")
    redis = RedisClient.get_instance()

    async with engine.connect() as conn:
        q = staff_queries.AsyncQuerier(conn)
        import sqlalchemy
        row = (await conn.execute(sqlalchemy.text("SELECT id FROM staff_users LIMIT 1"))).fetchone()
        
        if not row:
            print("No staff user found! Creating one...")
            res = await q.create_staff_user(email="testadmin@example.com", hashed_password="pw", display_name="Admin", role="admin")
            staff_user_id = res.id
        else:
            staff_user_id = row[0]
            
        class DummyUser: pass
        staff_user = DummyUser()
        staff_user.id = staff_user_id

        drive_service = StaffDriveService(
            staff_user_querier=q,
            drive_connection_querier=drive_queries.AsyncQuerier(conn),
            redis=redis
        )
        url, state = await drive_service.create_connect_url(staff_user)
        print("========================")
        print("GOOGLE_AUTH_URL:", url)
        print("========================")

asyncio.run(main())
