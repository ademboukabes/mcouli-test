import asyncio
import json
import uuid
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from db.generated import stuff_user as staff_queries
from app.infra.redis import RedisClient
from app.infra.minio import init_minio_client
from app.infra.nats import NatsClient, NatsSubjects

async def main():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url)

    try:
        RedisClient.init(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD or "")
    except RuntimeError:
        pass

    await init_minio_client(
        minio_host=settings.MINIO_HOST,
        minio_port=settings.MINIO_API_PORT,
        minio_root_user=settings.MINIO_ROOT_USER,
        minio_root_password=settings.MINIO_ROOT_PASSWORD
    )

    await NatsClient.connect(
        host=settings.NATS_HOST,
        port=settings.NATS_PORT,
        user=settings.NATS_USER,
        password=settings.NATS_PASSWORD
    )

    async with engine.connect() as conn:
        q = staff_queries.AsyncQuerier(conn)
        import sqlalchemy
        row = (await conn.execute(sqlalchemy.text("SELECT id FROM staff_users LIMIT 1"))).fetchone()
        staff_user_id = row[0]

        event_row = (await conn.execute(sqlalchemy.text("SELECT id FROM events LIMIT 1"))).fetchone()
        if not event_row:
            print("Creating dummy event...")
            ev_id = uuid.uuid4()
            await conn.execute(sqlalchemy.text("INSERT INTO events (id, title, date, location) VALUES (:id, 'Test Event', now(), 'Test Location')"), {"id": ev_id})
            event_id = ev_id
        else:
            event_id = event_row[0]

        from app.infra.minio import ImageBucket
        bucket = ImageBucket(f"staff-drive/{staff_user_id}")

        objects = bucket.client.list_objects(bucket.bucket_name, prefix=bucket.file_prefix + "/", recursive=True)
        count = 0
        async for obj in objects:
            storage_key = obj.object_name
            print(f"Injecting photo {storage_key} into AI pipeline...")

            # Create photo in DB
            new_id = uuid.uuid4()
            await conn.execute(
                sqlalchemy.text("INSERT INTO photos (id, event_id, storage_key, visibility) VALUES (:id, :event_id, :storage_key, 'public')"),
                {"id": new_id, "event_id": event_id, "storage_key": storage_key}
            )

            # Publish event
            await NatsClient.publish(
                NatsSubjects.PHOTO_PROCESS,
                json.dumps({
                    "photo_id": str(new_id),
                    "image_ref": storage_key,
                    "event_id": str(event_id)
                }).encode("utf-8")
            )
            count += 1
            if count >= 20:
                break

        await conn.commit()
        print(f"Successfully injected {count} photos to the AI worker!")

asyncio.run(main())
