from datetime import datetime, timedelta, timezone
import uuid

from app.core import constant
from app.core.exceptions import AppException
from app.core.securite import (
    hash_password,
    verify_password,
    create_acces_mobile_token,
    create_refresh_mobile_token,
    decode_refresh_mobile_token,
    Get_expiry_time,
)
from app.infra.redis import RedisClient

from app.schema.request.mobile.auth import MobileAuthRequest
from app.schema.response.mobile.auth import MobileAuthResponse
from db.generated import user as user_queries
from db.generated import devices as device_queries
from db.generated import session as session_queries
from db.generated.models import User
from app.core.logger import logger
from app.service.face_embedding import FaceImagePayload, FaceEmbeddingService


class AuthService:
    user_querier: user_queries.AsyncQuerier
    device_querier: device_queries.AsyncQuerier
    session_querier: session_queries.AsyncQuerier
    SESSION_LIMIT = 3
    REDIS_SESSION_TTL = 180

    def __init__(
        self,
        user_querier: user_queries.AsyncQuerier,
        device_querier: device_queries.AsyncQuerier,
        session_querier: session_queries.AsyncQuerier,
        face_embedding_service: FaceEmbeddingService,
    ):
        self.user_querier = user_querier
        self.device_querier = device_querier
        self.session_querier = session_querier
        self.face_embedding_service = face_embedding_service

    async def mobile_register_login(
        self,
        redis: RedisClient,
        req: MobileAuthRequest,
    ) -> MobileAuthResponse:
        logger.info("mobile register/login attempt for %s", req.email)
        existing_user = await self.user_querier.get_user_by_email(email=req.email)
        user: User | None = None

        if existing_user is not None:
            if not verify_password(req.password, existing_user.hashed_password or ""):
                raise AppException.unauthorized("Invalid credentials")
            user = existing_user
            logger.info("existing user login: %s", req.email)
        else:
            hashed = hash_password(req.password)
            logger.info("creating new user for %s", req.email)
            user = await self.user_querier.create_user(
                email=req.email, hashed_password=hashed
            )
            if not user:
                raise AppException.internal_error("Failed to create user")

        assert user is not None

        user_id: uuid.UUID = user.id

        session_key = constant.RedisKey.UserSessionByUser.value.format(user_id=user_id)
        if await redis.exists(session_key):
            raise AppException.forbidden("User already has an active session")

        session_count = await self.session_querier.count_user_sessions(user_id=user_id)
        if session_count and session_count >= AuthService.SESSION_LIMIT:
            logger.warning(
                "user %s reached session limit %s",
                req.email,
                AuthService.SESSION_LIMIT,
            )
            raise AppException.forbidden("Maximum session limit reached")

        device_id = req.device_id
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        device = await self.device_querier.create_device(
            arg=device_queries.CreateDeviceParams(
            column_1=device_id,
            user_id=user_id,
            device_name=req.device_name,
            device_type=req.device_type,
            totp_secret=None,

            )

        )

        if not device:
            raise AppException.internal_error("Failed to create device")

        session = await self.session_querier.upsert_session(
            user_id=user_id,
            device_id=device_id,
            expires_at=expires_at,
        )

        if not session:
            raise AppException.internal_error("Failed to create session")

        await redis.set(
            session_key, str(session.id), expire=AuthService.REDIS_SESSION_TTL
        )

        access_token = create_acces_mobile_token(str(session.id))
        refresh_token = create_refresh_mobile_token(str(session.id))
        expiry = Get_expiry_time()
        logger.info("created session %s for user %s", session.id, user_id)

        return MobileAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        session_id=str(session.id),
            expires_in=expiry,
        )

    async def refresh_token(
        self,
        redis: RedisClient,
        refresh_token: str,
    ) -> MobileAuthResponse:
        payload = decode_refresh_mobile_token(refresh_token)
        session_id = payload.get("session_id")

        if not session_id:
            raise AppException.unauthorized("Invalid refresh token")

        session = await self.session_querier.get_session_by_id(id=uuid.UUID(session_id))

        if not session:
            raise AppException.unauthorized("Session not found")

        if session.expires_at < datetime.now(timezone.utc):
            raise AppException.unauthorized("Session expired")

        session_key = constant.RedisKey.UserSessionByUser.value.format(
            user_id=session.user_id
        )
        redis_session = await redis.get(session_key)

        if not redis_session or redis_session != session_id:
            raise AppException.unauthorized("Session invalidated")

        await redis.expire(session_key, AuthService.REDIS_SESSION_TTL)

        new_access_token = create_acces_mobile_token(session_id)
        new_refresh_token = create_refresh_mobile_token(session_id)
        expiry = Get_expiry_time()

        return MobileAuthResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            session_id=session_id,
            expires_in=expiry,
        )

    async def logout(
        self,
        redis: RedisClient,
        user_id: str,
        session_id: str,
    ) -> dict[str, str]:
        session_key = constant.RedisKey.UserSessionByUser.value.format(user_id=user_id)
        await redis.delete(session_key)
        return {"message": "Logged out successfully"}

    async def add_embbed_user(
        self,
        user_id: uuid.UUID,
        image_payloads: list[FaceImagePayload],
    ) -> dict[str, object]:
        logger.info("Generating face embeddings for user %s", user_id)

        averaging = await self.face_embedding_service.compute_average_embedding(
            image_payloads
        )

        return {
            "message": "Face enrollment successful",
            "face_embedding": averaging,
        }

    async def validate_session(
        self,
        redis: RedisClient,
        session_id: str,
    ) -> bool:
        session = await self.session_querier.get_session_by_id(id=uuid.UUID(session_id))

        if not session:
            return False

        if session.expires_at < datetime.now(timezone.utc):
            return False

        session_key = constant.RedisKey.UserSessionByUser.value.format(
            user_id=session.user_id
        )
        redis_session = await redis.get(session_key)

        return redis_session == session_id

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.user_querier.get_user_by_id(id=user_id)
