import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from db.generated import staff_user as staff_queries
from app.infra.redis import RedisClient
from app.infra.google_drive import GoogleDriveClient
from app.service.staff_drive import StaffDriveService
from db.generated import staff_drive_connections as drive_queries

async def main():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url)

    # Init redis
    try:
        RedisClient.init(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD or "")
    except RuntimeError:
        pass
    redis = RedisClient.get_instance()

    async with engine.connect() as conn:
        q = staff_queries.AsyncQuerier(conn)
        import sqlalchemy
        row = (await conn.execute(sqlalchemy.text("SELECT id FROM staff_users LIMIT 1"))).fetchone()
        staff_user_id = row[0]

        class DummyUser:
            pass
        staff_user = DummyUser()
        staff_user.id = staff_user_id

        drive_service = StaffDriveService(
            staff_user_querier=q,
            drive_connection_querier=drive_queries.AsyncQuerier(conn),
            redis=redis
        )

        access_token = await drive_service.get_access_token_for_staff_user(staff_user_id)

        # List root folders
        print("=== DOSSIERS ET FICHIERS A LA RACINE DU DRIVE ===")
        items = await GoogleDriveClient.list_folder_contents(access_token=access_token)
        for i in items[:20]:
            type_str = "📁 DOSSIER" if i.mime_type == "application/vnd.google-apps.folder" else "📄 FICHIER"
            print(f"{type_str} | ID: {i.id} | NOM: {i.name}")

        if not items:
            print("Aucun fichier trouvé.")

asyncio.run(main())
