from datetime import datetime, timedelta, timezone
import uuid

from app.core.exceptions import AppException, DBException
from app.core.securite import (
    hash_password,
    verify_password,
    create_acces_mobile_token,
    create_refresh_mobile_token,
    decode_refresh_mobile_token,
    Get_expiry_time,
)
from app.core import constant
from app.core.config import settings
from app.infra.redis import RedisClient

from app.schema.request.mobile.auth import MobileAuthRequest
from app.schema.response.mobile.auth import MobileAuthResponse
from db.generated import user as user_queries
from db.generated import devices as device_queries
from db.generated import session as session_queries
from db.generated.models import User, UserDevice
from app.core.logger import logger
from app.service.face_embedding import FaceImagePayload, FaceEmbeddingService
from app.schema.internal.single_face_match import ClosestUserMatch


class AuthService:
    user_querier: user_queries.AsyncQuerier
    device_querier: device_queries.AsyncQuerier
    session_querier: session_queries.AsyncQuerier
    SESSION_LIMIT = settings.MOBILE_SESSION_LIMIT
    REDIS_SESSION_TTL = settings.MOBILE_SESSION_TTL_SECONDS

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

    async def _ensure_device_for_login(
        self,
        user_id: uuid.UUID,
        req: MobileAuthRequest,
    ) -> UserDevice:
        existing_device = await self.device_querier.get_device_by_id(id=req.device_id)

        if existing_device:
            if existing_device.user_id != user_id:
                raise AppException.forbidden("Device already registered to another user")
            if existing_device.is_invalid_token:
                raise AppException.forbidden(
                    "Device push token is invalid. Update the token before logging in."
                )
            if not existing_device.is_active:
                await self.device_querier.activate_device(id=req.device_id, user_id=user_id)
            return existing_device

        device = await self.device_querier.create_device(
            arg=device_queries.CreateDeviceParams(
                column_1=req.device_id,
                user_id=user_id,
                device_name=req.device_name,
                device_type=req.device_type,
                totp_secret=None,
            )
        )
        if not device:
            raise AppException.internal_error("Failed to create device")
        return device

    async def mobile_register_login(
        self,
        redis: RedisClient,
        req: MobileAuthRequest,
    ) -> MobileAuthResponse:
        logger.info("mobile register/login attempt for %s", req.email)
        existing_user = await self.user_querier.get_user_by_email(email=req.email)
        user: User | None = None

        is_new_user = False
        if existing_user is not None:
            if existing_user.blocked:
                raise AppException.forbidden("User is blocked")
            if not verify_password(req.password, existing_user.hashed_password or ""):
                raise AppException.unauthorized("Invalid credentials")
            user = existing_user
            logger.info("existing user login: %s", req.email)
        else:
            is_new_user = True
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

        session_count = await self.session_querier.count_user_sessions(user_id=user_id)
        if session_count and session_count >= AuthService.SESSION_LIMIT:
            logger.warning(
                "user %s reached session limit %s",
                req.email,
                AuthService.SESSION_LIMIT,
            )
            raise AppException.forbidden("Maximum session limit reached")

        device_id = req.device_id
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.MOBILE_SESSION_DAYS
        )

        await self._ensure_device_for_login(user_id, req)

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
            user_id=user_id,
            is_new_user=is_new_user,
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

        user = await self.user_querier.get_user_by_id(id=session.user_id)
        if not user:
            raise AppException.unauthorized("User not found")
        if user.blocked:
            raise AppException.forbidden("User is blocked")

        new_access_token = create_acces_mobile_token(session_id)
        new_refresh_token = create_refresh_mobile_token(session_id)
        expiry = Get_expiry_time()

        return MobileAuthResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            session_id=session_id,
            expires_in=expiry,
            user_id=session.user_id,
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
    ) -> User:
        logger.info("Generating face embeddings for user %s", user_id)

        averaging = await self.face_embedding_service.compute_average_embedding(
            image_payloads
        )
        vector_literal = "[" + ", ".join(str(x) for x in averaging) + "]"
        user = await self.user_querier.set_user_embedding(
            dollar_1=vector_literal,
            id=user_id,
        )
        if not user:
            raise AppException.internal_error("Failed to set user embedding")

        return user

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
        return True

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self.user_querier.get_user_by_id(id=user_id)

    async def create_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
        blocked: bool = False,
    ) -> User:
        try:
            hashed = hash_password(password)
            user = await self.user_querier.create_user(
                email=email,
                hashed_password=hashed,
            )
            if not user:
                raise AppException.internal_error("Failed to create user")

            if display_name is not None or blocked:
                updated = await self.user_querier.update_user(
                    email=user.email,
                    display_name=display_name,
                    blocked=blocked,
                    id=user.id,
                )
                if not updated:
                    raise AppException.internal_error("Failed to update user")
                return updated

            return user
        except Exception as exc:
            logger.error("Failed to create user: %s", exc)
            raise DBException.handle(exc)

    async def get_user(self, *, user_id: uuid.UUID) -> User:
        user = await self.user_querier.get_user_by_id(id=user_id)
        if not user:
            raise AppException.not_found("User not found")
        return user

    async def list_users(self, *, limit: int, offset: int) -> list[User]:
        try:
            users: list[User] = []
            async for user in self.user_querier.list_users(limit=limit, offset=offset):
                users.append(user)
            return users
        except Exception as exc:
            logger.error("Failed to list users: %s", exc)
            raise DBException.handle(exc)

    async def update_user(
        self,
        *,
        user_id: uuid.UUID,
        email: str | None = None,
        display_name: str | None = None,
        blocked: bool | None = None,
    ) -> User:
        try:
            existing = await self.user_querier.get_user_by_id(id=user_id)
            if not existing:
                raise AppException.not_found("User not found")

            new_email = email if email is not None else existing.email
            new_display_name = (
                display_name if display_name is not None else existing.display_name
            )
            new_blocked = blocked if blocked is not None else existing.blocked

            user = await self.user_querier.update_user(
                email=new_email,
                display_name=new_display_name,
                blocked=new_blocked,
                id=user_id,
            )
            if not user:
                raise AppException.internal_error("Failed to update user")
            return user
        except Exception as exc:
            logger.error("Failed to update user: %s", exc)
            raise DBException.handle(exc)

    async def delete_user(self, *, redis: RedisClient, user_id: uuid.UUID) -> User:
        try:
            existing = await self.user_querier.get_user_by_id(id=user_id)
            if not existing:
                raise AppException.not_found("User not found")
            await self.user_querier.delete_user(id=user_id)
            session_key = constant.RedisKey.UserSessionByUser.value.format(
                user_id=user_id
            )
            await redis.delete(session_key)
            return existing
        except Exception as exc:
            logger.error("Failed to delete user: %s", exc)
            raise DBException.handle(exc)

    async def block_user(self, *, redis: RedisClient, user_id: uuid.UUID) -> User:
        try:
            user = await self.user_querier.set_user_blocked(blocked=True, id=user_id)
            if not user:
                raise AppException.not_found("User not found")

            session_key = constant.RedisKey.UserSessionByUser.value.format(
                user_id=user_id
            )
            await redis.delete(session_key)

            return user
        except Exception as exc:
            logger.error("Failed to block user: %s", exc)
            raise DBException.handle(exc)

    async def unblock_user(self, *, user_id: uuid.UUID) -> User:
        try:
            user = await self.user_querier.set_user_blocked(blocked=False, id=user_id)
            if not user:
                raise AppException.not_found("User not found")
            return user
        except Exception as exc:
            logger.error("Failed to unblock user: %s", exc)
            raise DBException.handle(exc)

    async def find_closest_user(self, *, embedding_literal: str) -> ClosestUserMatch | None:
        row = await self.user_querier.find_closest_user_by_embedding(
            dollar_1=embedding_literal,
        )
        if row is None or row.distance is None:
            return None
        return ClosestUserMatch(user_id=row.id, distance=float(row.distance))
