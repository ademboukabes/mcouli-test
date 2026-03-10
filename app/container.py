import sqlalchemy.ext.asyncio
from fastapi import Depends
from app.infra.database import get_db
from app.infra.redis import RedisClient
from db.generated import user as user_queries
from db.generated import session as session_queries
from db.generated import devices as device_queries
from app.service.users import AuthService
from app.service.session import SessionService
from app.service.device import DeviceService



class Container:

    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        # infrastructure
        self.redis = RedisClient.get_instance()

        # queriers
        self.user_querier = user_queries.AsyncQuerier(conn)
        self.session_querier = session_queries.AsyncQuerier(conn)
        self.device_querier = device_queries.AsyncQuerier(conn)

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



async def get_container(
    conn: sqlalchemy.ext.asyncio.AsyncConnection = Depends(get_db),
) -> Container:
    return Container(conn)