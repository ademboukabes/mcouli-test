from datetime import datetime, timedelta, timezone
import uuid
from app.core import constant
from app.core.exceptions import AppException
from app.core.securite import (
    create_acces_mobile_token, 
    create_refresh_mobile_token,
    Get_expiry_time,
    verify_password
)
from app.infra.redis import RedisClient
from db.generated import stuff_user as staff_queries
from db.generated import session as session_queries

from app.schema.auth.web.authSc import WebAuthResponse

class WebAuthService:
    def __init__(
        self,
        staff_querier: staff_queries.AsyncQuerier,
        session_querier: session_queries.AsyncQuerier,
    ):
        self.staff_querier = staff_querier
        self.session_querier = session_querier
        self.REDIS_SESSION_TTL = 3600  # 1 hour for web sessions

    async def admin_login(
        self,
        redis: RedisClient,
        email: str,
        password: str,  # Changed from discord_id
    ) -> WebAuthResponse:
    # 1. Verify the Staff User exists
        staff = await self.staff_querier.get_staff_user_by_email(email=email)
    
    # FIX: Check password instead of discord_id
        if not staff or not verify_password(password, staff.password):
            raise AppException.unauthorized("Invalid email or password")

    # 2. Handle Session 
        web_device_id = uuid.uuid5(uuid.NAMESPACE_DNS, "web-admin-panel")
        expires_at = datetime.now(timezone.utc) + timedelta(days=1)

        session = await self.session_querier.upsert_session(
            user_id=staff.id,
            device_id=web_device_id,
            expires_at=expires_at,
        )

        if not session:
            raise AppException.internal_error("Failed to initialize admin session")

        # 3. Cache in Redis
        session_key = constant.RedisKey.UserSessionByUser.value.format(user_id=staff.id)
        await redis.set(
            session_key, str(session.id), expire=self.REDIS_SESSION_TTL
        )

        # 4. Generate Tokens
        access_token = create_acces_mobile_token(str(session.id))
        refresh_token = create_refresh_mobile_token(str(session.id))
        
        return WebAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=staff.id,
            role=staff.role,
            expires_in=Get_expiry_time(),
        )