from pydantic import BaseModel
from app.core.exceptions import AppException, DBExceptionImpl
from db.generated import staffSessions as staff_queries # Ensure this matches your sqlc output
import uuid
from datetime import datetime, timedelta, timezone
from app.infra.redis import RedisClient
from app.core.constant import RedisKey

class StaffSessionRedis(BaseModel):
    session_id: uuid.UUID
    staff_id: uuid.UUID
    device_id: uuid.UUID
    last_active: datetime
    expires_at: datetime
    role: str

class StaffSessionService:
    staff_querier: staff_queries.AsyncQuerier
    redis: RedisClient

    def __init__(self, session: staff_queries.AsyncQuerier, redis: RedisClient) -> None:
        self.staff_querier = session
        self.redis = redis

    async def create_staff_session(self, staff_id: uuid.UUID, device_id: uuid.UUID, role: str):
        try:
            # 1. DB Persistence
            session = await self.staff_querier.upsert_staff_session(
                staff_id=staff_id,
                device_id=device_id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
            )
            if session is None:
                raise AppException.internal_error("Staff session creation failed")

            # 2. Redis Persistence with "Single Device" check (nx=True)
            result = await self.redis.set(
                key=RedisKey.StaffSessionByStaff.format(staff_id=staff_id),
                value=StaffSessionRedis(
                    session_id=session.id,
                    staff_id=session.staff_id,
                    device_id=session.device_id,
                    last_active=session.last_active,
                    expires_at=session.expires_at,
                    role=role
                ).model_dump_json(),
                expire=60 * 60 * 8,
                nx=True
            )
            
            if not result:
                raise AppException.forbidden("Staff already logged in on another browser/device")
                
            return session
        except Exception as e:
            raise DBExceptionImpl.handle(e)

    async def get_staff_session_by_id(self, session_id: uuid.UUID):
        try:
            session = await self.staff_querier.get_staff_session_by_id(id=session_id)
            if session is None:
                raise AppException.not_found("Staff session not found")
            return session
        except Exception as e:
            raise DBExceptionImpl.handle(e)

    async def check_staff_session(
        self,
        session_id: uuid.UUID,
        staff_id: uuid.UUID,
        device_id: uuid.UUID
    ) -> bool:
        try:
            session_in_redis = await self.redis.get(
                RedisKey.StaffSessionByStaff.format(staff_id=staff_id)
            )

            if session_in_redis is None:
                # Fallback to DB if Redis cache expired
                session = await self.staff_querier.get_staff_session_by_id(id=session_id)
                if session is None:
                    return False
                
                # Re-populate Redis
                await self.redis.set(
                    key=RedisKey.StaffSessionByStaff.format(staff_id=staff_id),
                    value=StaffSessionRedis(
                        session_id=session.id,
                        staff_id=session.staff_id,
                        device_id=session.device_id,
                        last_active=session.last_active,
                        expires_at=session.expires_at,
                        role="admin" # You might need to fetch the actual role here
                    ).model_dump_json(),
                    expire=60 * 60 * 8,
                    nx=True,
                )
                return True

            session_info = StaffSessionRedis.model_validate_json(session_in_redis)

            if session_info:
                if session_info.device_id != device_id and session_info.session_id != session_id:
                    raise AppException.forbidden("You already logged in on another device")

                # Update Activity/TTL in Redis
                await self.redis.set(
                    key=RedisKey.StaffSessionByStaff.format(staff_id=staff_id),
                    value=session_info.model_dump_json(),
                    expire=60 * 60 * 8,
                    nx=False,
                )
                return True
            
            return False
        except Exception as e:
            raise DBExceptionImpl.handle(e)

    async def delete_staff_session(
        self, staff_id: uuid.UUID, device_id: uuid.UUID
    ) -> None:
        try:
            await self.staff_querier.delete_staff_session_by_device(staff_id=staff_id, device_id=device_id)
            await self.redis.delete(RedisKey.StaffSessionByStaff.format(staff_id=staff_id))
        except Exception as e:
            raise DBExceptionImpl.handle(e)

    async def delete_expired_staff_sessions(self) -> None:
        try:
            await self.staff_querier.delete_expired_staff_sessions()
        except Exception as e:
            raise DBExceptionImpl.handle(e)
        

        