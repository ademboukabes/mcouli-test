import sqlalchemy.ext.asyncio
from fastapi import Depends

from app.deps.ai_deps import get_face_embedding_service
from app.infra.database import get_db
from app.infra.redis import RedisClient
from app.service.device import DeviceService
from app.service.face_embedding import FaceEmbeddingService
from app.service.session import SessionService
from app.service.staged_upload_storage import StagedUploadStorageService
from app.service.staff_drive import StaffDriveService
from app.service.staff_notifications import StaffNotificationsService
from app.service.staff_user import StaffUserService

from app.service.audit import AuditService
from app.service.notification_gateway import NotificationGatewayService
from app.service.upload_requests import UploadRequestsService
from app.service.users import AuthService
from app.service.user_notification import UserNotificationService
from db.generated import devices as device_queries
from db.generated import photos as photo_queries
from db.generated import session as session_queries
from db.generated import staff_drive_connections as staff_drive_queries
from db.generated import staff_notifications as staff_notification_queries
from db.generated import stuff_user as staff_user_queries
from db.generated import upload_request_photos as upload_request_photo_queries
from db.generated import upload_requests as upload_request_queries
from db.generated import user as user_queries

from db.generated import events as event_queries
from db.generated import eventParticipant as participant_queries
from db.generated import stuff_user as staff_queries
from db.generated import notifications as notification_queries
from db.generated import audit as audit_queries
from app.service.event import EventService
from app.worker.notification.notification_queue import NotificationQueue
from app.worker.notification.settings import NotifSetting

class Container:
    def __init__(
        self,
        conn: sqlalchemy.ext.asyncio.AsyncConnection,
        face_embedding_service: FaceEmbeddingService | None = None,
    ):
        # infrastructure
        self.redis = RedisClient.get_instance()
        self.face_embedding_service = face_embedding_service or get_face_embedding_service()

        # queriers
        self.user_querier = user_queries.AsyncQuerier(conn)
        self.session_querier = session_queries.AsyncQuerier(conn)
        self.device_querier = device_queries.AsyncQuerier(conn)
        self.staff_user_querier = staff_user_queries.AsyncQuerier(conn)
        self.staff_drive_querier = staff_drive_queries.AsyncQuerier(conn)
        self.upload_request_querier = upload_request_queries.AsyncQuerier(conn)
        self.upload_request_photo_querier = upload_request_photo_queries.AsyncQuerier(conn)
        self.photo_querier = photo_queries.AsyncQuerier(conn)
        self.staff_notification_querier = staff_notification_queries.AsyncQuerier(conn)
        self.notification_querier = notification_queries.AsyncQuerier(conn)
        self.audit_querier = audit_queries.AsyncQuerier(conn)
        self.event_querier = event_queries.AsyncQuerier(conn)
        self.participant_querier = participant_queries.AsyncQuerier(conn)
        self.staff_querier = staff_queries.AsyncQuerier(conn)


        # services
        self.session_service = SessionService()
        self.session_service.init(
            session=self.session_querier,
            redis=self.redis,
        )


        self.device_service = DeviceService()
        self.device_service.init(
            device_querier=self.device_querier,
        )

        self.auth_service = AuthService(
            user_querier=self.user_querier,
            device_querier=self.device_querier,
            session_querier=self.session_querier,
            face_embedding_service=self.face_embedding_service,
        )

        self.staff_drive_service = StaffDriveService(
            staff_user_querier=self.staff_user_querier,
            drive_connection_querier=self.staff_drive_querier,
            redis=self.redis,
        )

        self.staff_notifications_service = StaffNotificationsService(
            notification_querier=self.staff_notification_querier,
        )
        self.staged_upload_storage_service = StagedUploadStorageService()

        self.upload_requests_service = UploadRequestsService(
            upload_request_querier=self.upload_request_querier,
            upload_request_photo_querier=self.upload_request_photo_querier,
            photo_querier=self.photo_querier,
            staged_upload_storage=self.staged_upload_storage_service,
            staff_drive_service=self.staff_drive_service,
            staff_notifications_service=self.staff_notifications_service,
        )

        self.user_notifications_service = UserNotificationService(
            notification_querier=self.notification_querier,
        )

        self.audit_service = AuditService(
            audit_querier=self.audit_querier,
        )

        self.staff_user_service = StaffUserService()

        self.staff_user_service.init(
            staff_user_querier=self.staff_user_querier,)

        self.event_service = EventService(
            e_querier=self.event_querier,
            p_querier=self.participant_querier,
        )

        notification_queue = NotificationQueue(settings=NotifSetting)
        self.notification_gateway_service = NotificationGatewayService(notification_queue)




async def get_container(
    conn: sqlalchemy.ext.asyncio.AsyncConnection = Depends(get_db),
) -> Container:
    return Container(conn)
