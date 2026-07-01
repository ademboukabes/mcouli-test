import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from db.generated import stuff_user as staff_queries
from db.generated import upload_request_groups as group_queries
from db.generated import upload_requests as request_queries
from db.generated import upload_request_photos as request_photo_queries
from db.generated import photos as photo_queries
from db.generated import staff_drive_connections as drive_queries
from db.generated import staff_notifications as notif_queries
from db.generated import audit as audit_queries
from app.service.upload_requests import UploadRequestsService
from app.service.staged_upload_storage import StagedUploadStorageService
from app.service.staff_drive import StaffDriveService
from app.service.staff_notifications import StaffNotificationsService
from app.service.audit import AuditService
from app.schema.request.staff.uploads import CreateUploadRequestPhotoRequest
from app.infra.redis import RedisClient
from app.infra.minio import init_minio_client
from app.infra.nats import NatsClient
import uuid

async def main():
    url = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    engine = create_async_engine(url)

    try:
        RedisClient.init(host=settings.REDIS_HOST, port=settings.REDIS_PORT, password=settings.REDIS_PASSWORD or "")
    except RuntimeError:
        pass
    redis = RedisClient.get_instance()

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

        class DummyUser:
            pass
        staff_user = DummyUser()
        staff_user.id = staff_user_id
        staff_user.role = "multi_team_lead" # Important for approval!

        # Need an event
        event_row = (await conn.execute(sqlalchemy.text("SELECT id FROM events LIMIT 1"))).fetchone()
        if not event_row:
            print("Creating dummy event...")
            ev_id = uuid.uuid4()
            await conn.execute(sqlalchemy.text("INSERT INTO events (id, title, date, location) VALUES (:id, 'Test Event', now(), 'Test Location')"), {"id": ev_id})
            event_id = ev_id
        else:
            event_id = event_row[0]

        upload_service = UploadRequestsService(
            upload_request_group_querier=group_queries.AsyncQuerier(conn),
            upload_request_querier=request_queries.AsyncQuerier(conn),
            upload_request_photo_querier=request_photo_queries.AsyncQuerier(conn),
            photo_querier=photo_queries.AsyncQuerier(conn),
            staged_upload_storage=StagedUploadStorageService(),
            staff_drive_service=StaffDriveService(staff_user_querier=q, drive_connection_querier=drive_queries.AsyncQuerier(conn), redis=redis),
            staff_notifications_service=StaffNotificationsService(notif_queries.AsyncQuerier(conn)),
            audit_service=AuditService(audit_queries.AsyncQuerier(conn), None),
        )

        # Get staged photos from minio bucket for this staff user
        from app.infra.minio import ImageBucket
        bucket = ImageBucket(f"staff-drive/{staff_user_id}")

        objects = bucket.client.list_objects(bucket.bucket_name, prefix=bucket.file_prefix + "/", recursive=True)
        photo_inputs = []
        async for obj in objects:
            name = obj.object_name.split("/")[-1]
            photo_inputs.append(CreateUploadRequestPhotoRequest(
                staged_object_name=name,
                original_file_name=name,
            ))
            if len(photo_inputs) >= 20:
                break

        if not photo_inputs:
            print("No staged photos found in minio.")
            return

        print(f"Submitting {len(photo_inputs)} photos to upload request...")

        req_details = await upload_service.create_upload(
            event_id=event_id,
            folder_id="drive-import",
            photos=photo_inputs,
            visibility="public",
            day_number=1,
            requested_by=staff_user,
        )

        print(f"Created upload request! ID: {req_details.id}")
        print("Approving upload request to trigger AI pipeline...")

        await upload_service.approve_request(request_id=req_details.id, approved_by=staff_user)

        print("Done! Photos should now be processed by AI.")

asyncio.run(main())
