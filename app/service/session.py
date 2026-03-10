from pydantic import BaseModel
from app.core.exceptions import AppException, DBExceptionImpl
from db.generated import session as session_queries
import uuid
from db.generated.models import UserSession 
from datetime import datetime,timedelta,timezone
from app.infra.redis import RedisClient
from app.core.constant import RedisKey
from db.generated.session import UpsertSessionRow

class SessionRedis(BaseModel):
    session_id:uuid.UUID
    user_id:uuid.UUID
    device_id:uuid.UUID
    last_active:datetime
    expires_at:datetime

class SessionService :
    session_querier : session_queries.AsyncQuerier
    redis : RedisClient

    def init(self,session:session_queries.AsyncQuerier,redis:RedisClient):
        self.session_querier = session
        self.redis = redis
    
    @staticmethod
    async def create_session(user_id:uuid.UUID,device_id:uuid.UUID)->UpsertSessionRow:
        try :
            session = await SessionService.session_querier.upsert_session(
                user_id=user_id,
                device_id=device_id,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            )
            if session is None :
                raise AppException.internal_error("session creation failed ")
            
            result = await SessionService.redis.set(
                key=RedisKey.UserSessionByUser.format(user_id=user_id),
                value=SessionRedis(
                    session_id=session.id,
                    user_id=session.user_id,
                    device_id=session.device_id,
                    last_active=session.last_active,
                    expires_at=session.expires_at,
                ).model_dump_json(),
                expire=60*60*5,
                nx=True
            )
            if not result:
                AppException.forbidden("You already logged in in another device")
            return session
        except Exception as e :
             raise DBExceptionImpl.handle(e)
            
        

    @staticmethod
    async def get_session_by_id(session_id:uuid.UUID)->UserSession:
        try :
            session = await SessionService.session_querier.get_session_by_id(id=session_id)
            if session is None :
                raise AppException.not_found("session Not found ")
            return session
        except Exception as e :
            raise DBExceptionImpl.handle(e)

            
    @staticmethod
    async def check_session(
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        device_id: uuid.UUID
    ) -> bool:
        try:
            session_in_redis = await SessionService.redis.get(
                RedisKey.UserSessionByUser.format(user_id=user_id)
            )

            if session_in_redis is None:
                return False

            session_info = SessionRedis.model_validate_json(session_in_redis)

            if session_info:
                if session_info.device_id != device_id and session_info.session_id != session_id:
                    raise AppException.forbidden("You already logged in on another device")

                await SessionService.redis.set(
                    key=RedisKey.UserSessionByUser.format(user_id=user_id),
                    value=SessionRedis(
                        session_id=session_info.session_id,
                        user_id=session_info.user_id,
                        device_id=session_info.device_id,
                        last_active=session_info.last_active,
                        expires_at=session_info.expires_at,
                    ).model_dump_json(),
                    expire=60 * 60 * 5,
                    nx=False,
                )

                return True

            session = await SessionService.session_querier.get_session_by_id(id=session_id)

            if session is None:
                raise AppException.forbidden("Session not found")

            await SessionService.redis.set(
                key=RedisKey.UserSessionByUser.format(user_id=user_id),
                value=SessionRedis(
                    session_id=session.id,
                    user_id=session.user_id,
                    device_id=session.device_id,
                    last_active=session.last_active,
                    expires_at=session.expires_at,
                ).model_dump_json(),
                expire=60 * 60 * 5,
                nx=True,
            )

            return True

        except Exception as e:
            raise DBExceptionImpl.handle(e)


    @staticmethod
    async def delete_session(session_id:uuid.UUID,user_id:uuid.UUID,device_id : uuid.UUID):
        try :
            await SessionService.session_querier.delete_session_by_device(user_id=user_id,device_id=device_id)
        except Exception as e :
           raise  DBExceptionImpl.handle(e)
    
    
    @staticmethod
    async def delete_expired_sessions():
        try :
            await SessionService.session_querier.delete_expired_sessions()
        except Exception as e :
           raise  DBExceptionImpl.handle(e)
    
    @staticmethod
    async def count_user_sessions(user_id:uuid.UUID)->int:
        try :
            count =  await SessionService.session_querier.count_user_sessions(user_id=user_id)
            if count is None :
                raise AppException.internal_error("failed to count ")
            else :
                return count
        except Exception as e :
             raise DBExceptionImpl.handle(e)
