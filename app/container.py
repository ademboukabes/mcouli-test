import sqlalchemy.ext.asyncio
from fastapi import Depends
from app.infra.database import get_db
from app.infra.redis import RedisClient
from db.generated import user as user_queries
from db.generated import session as session_queries
from db.generated import devices as device_queries
from db.generated import stuff_user as staff_user_queries
from db.generated import staff_drive_connections as staff_drive_queries
from app.service.users import AuthService
from app.service.session import SessionService
from app.service.device import DeviceService
from app.service.staff_drive import StaffDriveService
from app.service.staff_user import StaffUserService



class Container:

    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        # infrastructure
        self.redis = RedisClient.get_instance()

        # queriers
        self.user_querier = user_queries.AsyncQuerier(conn)
        self.session_querier = session_queries.AsyncQuerier(conn)
        self.device_querier = device_queries.AsyncQuerier(conn)
        self.staff_user_querier = staff_user_queries.AsyncQuerier(conn)
        self.staff_drive_querier = staff_drive_queries.AsyncQuerier(conn)

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
        )

        self.staff_drive_service = StaffDriveService(
            staff_user_querier=self.staff_user_querier,
            drive_connection_querier=self.staff_drive_querier,
            redis=self.redis,
        )

        self.staff_user_service = StaffUserService()
        self.staff_user_service.init(
            staff_user_querier=self.staff_user_querier,
        )



async def get_container(
    conn: sqlalchemy.ext.asyncio.AsyncConnection = Depends(get_db),
) -> Container:
    return Container(conn)
