import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from db.generated import stuff_user as staff_queries
from app.infra.redis import RedisClient
from app.infra.google_drive import GoogleDriveClient
from app.infra.minio import init_minio_client
from app.service.staff_drive import StaffDriveService, SelectedDriveFile
from db.generated import staff_drive_connections as drive_queries

async def main():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url)

    try:
        RedisClient.init(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD or "")
    except RuntimeError:
        pass
    redis = RedisClient.get_instance()

    # Init minio
    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD
    )

    async with engine.connect() as conn:
        q = staff_queries.AsyncQuerier(conn)
        import sqlalchemy
        row = (await conn.execute(sqlalchemy.text("SELECT id FROM staff_users LIMIT 1"))).fetchone()
        staff_user_id = row[0]

        class DummyUser: pass
        staff_user = DummyUser()
        staff_user.id = staff_user_id

        drive_service = StaffDriveService(
            staff_user_querier=q,
            drive_connection_querier=drive_queries.AsyncQuerier(conn),
            redis=redis
        )

        access_token = await drive_service.get_access_token_for_staff_user(staff_user_id)

        print("Fetching images from Drive...")
        items = await GoogleDriveClient.list_folder_contents(access_token=access_token)

        # Filter images
        image_items = [i for i in items if i.mime_type.startswith("image/")]

        if not image_items:
            print("No images found to import.")
            return

        print(f"Found {len(image_items)} images. Initiating import...")
        selections = [
            SelectedDriveFile(id=f.id, name=f.name, mime_type=f.mime_type)
            for f in image_items[:20]  # Let's import up to 20 for this test
        ]

        results = await drive_service.import_images_from_drive(
            staff_user=staff_user,
            selected_files=selections,
        )

        print(f"Successfully imported {len(results)} images to MinIO!")
        for r in results:
            print(f" -> {r.original_file_name} stored as {r.minio_object_name}")

asyncio.run(main())
