from datetime import datetime, timedelta, timezone
import uuid
from collections.abc import AsyncIterable
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import AppException, DBException
from app.core.securite import (
    hash_password,
    verify_password,
    create_acces_mobile_token,
    create_raw_refresh_token,
    hash_refresh_token,
    encrypt_refresh_cache_payload,
    decrypt_refresh_cache_payload,
)
from app.core.config import settings
from app.infra.redis import RedisClient
from app.infra.minio import Bucket, IMAGES_BUCKET_NAME
from app.schema.request.mobile.auth import (
    MobileAuthBaseRequest,
    MobileLoginRequest,
    MobileRegisterRequest,
    RegisterVerifyRequest,
)
from app.schema.response.mobile.auth import MobileAuthResponse, RegisterPendingResponse
from app.infra.nats import NatsClient
import secrets
import json
from db.generated import user as user_queries
from db.generated import devices as device_queries
from db.generated import session as session_queries
from db.generated.models import User, UserDevice, RefreshToken
from db.generated import refresh_token as refresh_token_queries
from app.core.logger import logger
from app.service.face_embedding import FaceImagePayload, FaceEmbeddingService
from app.schema.internal.single_face_match import ClosestUserMatch
from app.service.session import SessionService


class AuthService:
    user_querier: user_queries.AsyncQuerier
    device_querier: device_queries.AsyncQuerier
    session_querier: session_queries.AsyncQuerier
    refresh_token_querier: refresh_token_queries.AsyncQuerier
    SESSION_LIMIT = settings.MOBILE_SESSION_LIMIT
    REDIS_SESSION_TTL = settings.MOBILE_SESSION_TTL_SECONDS
    REFRESH_GRACE_SECONDS = settings.MOBILE_REFRESH_TOKEN_REUSE_GRACE_SECONDS

    def __init__(
        self,
        user_querier: user_queries.AsyncQuerier,
        device_querier: device_queries.AsyncQuerier,
        session_querier: session_queries.AsyncQuerier,
        refresh_token_querier: refresh_token_queries.AsyncQuerier,
        face_embedding_service: FaceEmbeddingService,
    ):
        self.user_querier = user_querier
        self.device_querier = device_querier
        self.session_querier = session_querier
        self.refresh_token_querier = refresh_token_querier
        self.face_embedding_service = face_embedding_service

    async def _ensure_device_for_login(
        self,
        user_id: uuid.UUID,
        req: MobileAuthBaseRequest,
    ) -> UserDevice:
        existing_device = await self.device_querier.get_device_by_physical_id(
            user_id=user_id,
            physical_device_id=req.physical_device_id
        )

        if existing_device:
            if existing_device.is_invalid_token:
                raise AppException.forbidden(
                    "Device push token is invalid. Update the token before logging in."
                )
            if not existing_device.is_active:
                await self.device_querier.activate_device(id=existing_device.id, user_id=user_id)
            return existing_device

        device = await self.device_querier.create_device(
            arg=device_queries.CreateDeviceParams(
                column_1=None,
                user_id=user_id,
                device_name=req.device_name,
                device_type=req.device_type,
                totp_secret=None,
                physical_device_id=req.physical_device_id
            )
        )
        if not device:
            raise AppException.internal_error("Failed to create device")
        return device

    async def mobile_login(
        self,
        redis: RedisClient,
        req: MobileLoginRequest,
        client_ip: Optional[str] = None,
    ) -> MobileAuthResponse:
        logger.info("mobile_login attempt")
        max_attempts = settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS
        window = settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS

        if client_ip:
            await self.check_rate_limit(
                redis,
                f"rate:ip:{client_ip}",
                max_attempts,
                window,
            )
        await self.check_rate_limit(
            redis,
            f"rate:email:{req.email}",
            max_attempts,
            window,
        )

        existing_user = await self.user_querier.get_user_by_email(email=req.email)
        if existing_user is None:
            logger.warning("login attempt: user_not_found")
            raise AppException.unauthorized("User not found; consider registering instead")
        if existing_user.blocked:
            logger.warning("login attempt: user_blocked user_id=%s", existing_user.id)
            raise AppException.forbidden("User is blocked")
        if not verify_password(req.password, existing_user.hashed_password or ""):
            logger.warning("login attempt: invalid_credentials user_id=%s", existing_user.id)
            raise AppException.unauthorized("Invalid credentials")

        locked_user = await self.user_querier.get_user_by_id_for_update(id=existing_user.id)
        if not locked_user:
            raise AppException.unauthorized("User not found")
        if locked_user.blocked:
            logger.warning("login attempt: user_blocked_at_commit user_id=%s", locked_user.id)
            raise AppException.forbidden("User is blocked")

        logger.info("login success user_id=%s", locked_user.id)
        return await self._create_mobile_session(
            redis=redis,
            user=locked_user,
            req=req,
            is_new_user=False,
        )

    async def mobile_register(
        self,
        redis: RedisClient,
        req: MobileRegisterRequest,
        client_ip: Optional[str] = None,
    ) -> RegisterPendingResponse:
        logger.info("mobile_register attempt")
        max_attempts = settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS
        window = settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS

        if client_ip:
            await self.check_rate_limit(
                redis,
                f"rate:ip:{client_ip}",
                max_attempts,
                window,
            )
        await self.check_rate_limit(
            redis,
            f"rate:email:{req.email}",
            max_attempts,
            window,
        )

        existing_user = await self.user_querier.get_user_by_email(email=req.email)
        if existing_user is not None:
            logger.warning("register attempt: email_already_in_use")
            raise AppException.conflict("Email already in use; please login instead")

        hashed = hash_password(req.password)
        otp = "".join(secrets.choice("0123456789") for _ in range(6))

        pending_key = f"pending_user:{req.email}"
        pending_data = {
            "hashed_password": hashed,
        }

        # Save in Redis for 10 minutes (600 seconds)
        await redis.set(pending_key, json.dumps(pending_data), expire=600)
        await redis.set(f"otp:{req.email}", otp, expire=600)

        # Send to NATS
        await NatsClient.publish("email.send_otp", json.dumps({"email": req.email, "otp": otp}).encode("utf-8"))

        logger.info("register success, OTP sent")
        return RegisterPendingResponse(
            message="OTP sent to email",
            status="pending_verification",
            email=req.email
        )

    async def mobile_register_resend_otp(
        self,
        redis: RedisClient,
        email: str,
        client_ip: Optional[str] = None,
    ) -> RegisterPendingResponse:
        logger.info("resend_otp attempt for %s", email)
        max_attempts = settings.RATE_LIMIT_LOGIN_MAX_ATTEMPTS
        window = settings.RATE_LIMIT_LOGIN_WINDOW_SECONDS

        if client_ip:
            await self.check_rate_limit(
                redis,
                f"rate:ip:{client_ip}",
                max_attempts,
                window,
            )
        await self.check_rate_limit(
            redis,
            f"rate:email:{email}",
            max_attempts,
            window,
        )

        pending_key = f"pending_user:{email}"
        raw_data = await redis.get(pending_key)
        if not raw_data:
            raise AppException.not_found("No pending registration found for this email")

        otp = "".join(secrets.choice("0123456789") for _ in range(6))

        # Regenerate OTP with 10 mins TTL, without touching the pending_user TTL
        await redis.set(f"otp:{email}", otp, expire=600)

        # Send to NATS
        await NatsClient.publish("email.send_otp", json.dumps({"email": email, "otp": otp}).encode("utf-8"))

        logger.info("resend_otp success, new OTP sent to %s", email)
        return RegisterPendingResponse(
            message="New OTP sent to email",
            status="pending_verification",
            email=email
        )

    async def verify_mobile_register(
        self,
        redis: RedisClient,
        req: RegisterVerifyRequest,
        client_ip: Optional[str] = None,
    ) -> MobileAuthResponse:
        otp_key = f"otp:{req.email}"
        stored_otp = await redis.get(otp_key)

        if not stored_otp or stored_otp != req.otp:
            raise AppException.unauthorized("Invalid or expired OTP")

        pending_key = f"pending_user:{req.email}"
        raw_data = await redis.get(pending_key)
        if not raw_data:
            raise AppException.unauthorized("Registration session expired")

        data = json.loads(raw_data)

        try:
            user = await self.user_querier.create_user(email=req.email, hashed_password=data["hashed_password"])
            if not user:
                raise AppException.internal_error("Failed to create user")
        except SQLAlchemyError as exc:
            logger.error("Failed to create user: %s", exc)
            raise DBException.handle(exc)

        # Clean up redis
        await redis.delete(otp_key)
        await redis.delete(pending_key)

        logger.info("register verify success user_id=%s", user.id)
        return await self._create_mobile_session(
            redis=redis,
            user=user,
            req=req,
            is_new_user=True,
        )

    async def _create_mobile_session(
        self,
        *,
        redis: RedisClient,
        user: User,
        req: MobileAuthBaseRequest,
        is_new_user: bool,
    ) -> MobileAuthResponse:
        user_id: uuid.UUID = user.id

        await self.session_querier.lock_user_sessions(user_id=str(user_id))

        device = await self._ensure_device_for_login(user_id, req)

        now = datetime.now(timezone.utc)
        idle_expires_at = now + timedelta(days=settings.MOBILE_SESSION_DAYS)
        absolute_expires_at = now + timedelta(days=settings.MOBILE_SESSION_ABSOLUTE_DAYS)

        session = await self.session_querier.upsert_session(
            user_id=user_id,
            device_id=device.id,
            idle_expires_at=idle_expires_at,
            absolute_expires_at=absolute_expires_at,
        )
        if not session:
            raise AppException.internal_error("Failed to create session")

        async for evicted_id in self.session_querier.evict_overflow_sessions(
            user_id=user_id, id=session.id, session_limit=AuthService.SESSION_LIMIT
        ):
            await SessionService.delete_session_cache(redis, evicted_id)
            logger.warning(
                "session_evicted user_id=%s evicted_session_id=%s",
                user_id, evicted_id,
            )

        access_token = create_acces_mobile_token(str(session.id))

        raw_refresh_token = create_raw_refresh_token()
        await self.refresh_token_querier.create_refresh_token(
            session_id=session.id,
            family_id=uuid.uuid4(),
            token_hash=hash_refresh_token(raw_refresh_token),
        )
        expiry = settings.MOBILE_ACCESS_TOKEN_TTL_SECONDS
        logger.info("session_created session_id=%s user_id=%s", session.id, user_id)

        await SessionService.cache_session_for_auth(
            redis=redis,
            session_id=session.id,
            user_id=user_id,
            email=user.email or "",
            idle_expires_at=session.idle_expires_at,
            absolute_expires_at=session.absolute_expires_at,
            blocked=user.blocked,
            ttl=AuthService.REDIS_SESSION_TTL,
            last_active=session.last_active,
        )

        return MobileAuthResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            session_id=str(session.id),
            expires_in=expiry,
            user_id=user_id,
            is_new_user=is_new_user,
        )

    async def _handle_used_refresh_token(
        self,
        redis: RedisClient,
        row: RefreshToken,
        token_hash: str,
    ) -> MobileAuthResponse:
        """A `used=True` refresh token was presented. Returns a replayed
        response if this is a benign grace-window retry with a cached
        result, or raises if it's outside the grace window (theft) or
        inside the grace window with no cached replay available (a used
        token with nothing to replay is never treated as valid).
        """
        within_grace = (
            row.used_at is not None
            and (datetime.now(timezone.utc) - row.used_at)
            <= timedelta(seconds=AuthService.REFRESH_GRACE_SECONDS)
        )

        if within_grace:
            cache_key = f"refresh_retry:{token_hash}"
            cached = await redis.get(cache_key)
            if cached:
                try:
                    decrypted = decrypt_refresh_cache_payload(cached)
                except Exception:
                    # tampered, corrupted, or wrong key — treat exactly
                    # like a cache miss, never trust an undecryptable value
                    raise AppException.unauthorized("Invalid refresh token")
                session_for_check = await self.session_querier.get_session_by_id(id=row.session_id)
                if not session_for_check:
                    raise AppException.unauthorized("Session not found")
                user_for_check = await self.user_querier.get_user_by_id(id=session_for_check.user_id)
                if not user_for_check or user_for_check.blocked:
                    raise AppException.forbidden("User is blocked")
                return MobileAuthResponse.model_validate_json(decrypted)
            raise AppException.unauthorized("Invalid refresh token")

        logger.warning(
            "refresh_token_reuse_detected family_id=%s session_id=%s",
            row.family_id, row.session_id,
        )
        session_for_revoke = await self.session_querier.get_session_by_id(id=row.session_id)
        if session_for_revoke:
            await self.session_querier.delete_session_by_id(
                id=row.session_id, user_id=session_for_revoke.user_id
            )
            await SessionService.delete_session_cache(redis, row.session_id)
        raise AppException.unauthorized(
            "Refresh token reuse detected; session revoked"
        )

    async def refresh_token(
        self,
        redis: RedisClient,
        refresh_token: str,
    ) -> MobileAuthResponse:
        token_hash = hash_refresh_token(refresh_token)

        row = await self.refresh_token_querier.get_refresh_token_by_hash_for_update(
            token_hash=token_hash
        )
        if not row:
            raise AppException.unauthorized("Invalid refresh token")

        if row.used:
            return await self._handle_used_refresh_token(redis, row, token_hash)

        claimed = await self.refresh_token_querier.mark_refresh_token_used(id=row.id)
        if claimed is None:
            # Not expected to be reachable — the row lock above already
            # serializes concurrent access to this row.
            raise AppException.unauthorized("Invalid refresh token")
        row = claimed

        session = await self.session_querier.get_session_by_id(id=row.session_id)
        if not session:
            raise AppException.unauthorized("Session not found")
        now = datetime.now(timezone.utc)
        if session.idle_expires_at < now or session.absolute_expires_at < now:
            raise AppException.unauthorized("Session expired")

        user = await self.user_querier.get_user_by_id(id=session.user_id)
        if not user:
            raise AppException.unauthorized("User not found")
        if user.blocked:
            raise AppException.forbidden("User is blocked")

        new_access_token = create_acces_mobile_token(str(session.id))
        new_raw_refresh_token = create_raw_refresh_token()
        await self.refresh_token_querier.create_refresh_token(
            session_id=session.id,
            family_id=row.family_id,
            token_hash=hash_refresh_token(new_raw_refresh_token),
        )

        response = MobileAuthResponse(
            access_token=new_access_token,
            refresh_token=new_raw_refresh_token,
            session_id=str(session.id),
            expires_in=settings.MOBILE_ACCESS_TOKEN_TTL_SECONDS,
            user_id=session.user_id,
        )

        await redis.set(
            f"refresh_retry:{token_hash}",
            encrypt_refresh_cache_payload(response.model_dump_json()),
            expire=AuthService.REFRESH_GRACE_SECONDS,
        )

        return response

    async def logout(
        self,
        redis: RedisClient,
        user_id: str,
        session_id: str,
    ) -> dict[str, str]:
        sid = uuid.UUID(session_id)
        await self.session_querier.delete_session_by_id(id=sid, user_id=uuid.UUID(user_id))
        await SessionService.delete_session_cache(redis, sid)

        return {"message": "Logged out successfully"}

    async def add_embbed_user(
        self,
        user_id: uuid.UUID,
        image_payloads: AsyncIterable[FaceImagePayload],
    ) -> User:
        logger.info("Generating face embeddings for user %s", user_id)

        existing = await self.user_querier.get_user_by_id(id=user_id)
        if not existing:
            raise AppException.not_found("User not found")
        if existing.face_embedding is not None:
            raise AppException.conflict(
                "User already has an active face enrollment. "
                "Delete the existing enrollment before re-enrolling."
            )

        averaging = await self.face_embedding_service.compute_average_embedding_stream(
            image_payloads
        )
        vector_literal = "[" + ", ".join(str(x) for x in averaging) + "]"

        locked_existing = await self.user_querier.get_user_by_id_for_update(id=user_id)
        if not locked_existing:
            raise AppException.not_found("User not found")
        if locked_existing.face_embedding is not None:
            raise AppException.conflict(
                "User already has an active face enrollment. "
                "Delete the existing enrollment before re-enrolling."
            )

        user = await self.user_querier.set_user_embedding(
            dollar_1=vector_literal,
            id=user_id,
        )
        if not user:
            raise AppException.internal_error("Failed to set user embedding")

        return user

    async def validate_session(self, redis: RedisClient, session_id: str) -> bool:
        session = await self.session_querier.get_session_by_id(id=uuid.UUID(session_id))
        if not session:
            return False
        now = datetime.now(timezone.utc)
        if session.idle_expires_at < now or session.absolute_expires_at < now:
            return False
        user = await self.user_querier.get_user_by_id(id=session.user_id)
        if not user or user.blocked:
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

    async def update_avatar(self, *, user_id: uuid.UUID, avatar_key: str) -> User:
        try:
            user = await self.user_querier.update_user_avatar(
                avatar_key=avatar_key,
                id=user_id,
            )
            if not user:
                raise AppException.not_found("User not found")
            return user
        except Exception as exc:
            logger.error("Failed to update avatar for user %s: %s", user_id, exc)
            raise DBException.handle(exc)

    async def upload_avatar_bytes(
        self, *, avatar_key: str, data: bytes, content_type: str, filename: str
    ) -> None:
        try:
            bucket = Bucket(IMAGES_BUCKET_NAME, "avatars")
            await bucket.put_bytes(
                data=data,
                object_name=avatar_key,
                content_type=content_type,
                filename=filename,
            )
        except Exception as exc:
            raise AppException.storage_error("Failed to upload avatar image") from exc

    async def get_avatar_bytes(self, *, user_id: uuid.UUID) -> tuple[bytes, str, str]:
        user = await self.get_user(user_id=user_id)
        if not user.avatar_key:
            raise AppException.not_found("No avatar set")

        bucket = Bucket(IMAGES_BUCKET_NAME, "avatars")
        try:
            return await bucket.get(user.avatar_key)
        except HTTPException:
            raise
        except Exception as exc:
            raise AppException.storage_error("Failed to retrieve avatar image") from exc

    async def delete_avatar_bytes(self, *, avatar_key: str) -> None:
        try:
            bucket = Bucket(IMAGES_BUCKET_NAME, "avatars")
            await bucket.delete(avatar_key)
        except Exception as exc:
            logger.warning("Failed to clean up orphaned avatar %s: %s", avatar_key, exc)

    async def block_user(self, *, redis: RedisClient, user_id: uuid.UUID) -> User:
        try:
            locked = await self.user_querier.get_user_by_id_for_update(id=user_id)
            if not locked:
                raise AppException.not_found("User not found")
            user = await self.user_querier.set_user_blocked(blocked=True, id=user_id)
            if not user:
                raise AppException.internal_error("Failed to block user")
            session_ids = [s.id async for s in self.session_querier.list_sessions_by_user(user_id=user_id)]
            await self.session_querier.delete_all_user_sessions(user_id=user_id)
            for sid in session_ids:
                await SessionService.delete_session_cache(redis, sid)
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

    async def delete_user(self, *, redis: RedisClient, user_id: uuid.UUID) -> User:
        try:
            existing = await self.user_querier.get_user_by_id_for_update(id=user_id)
            if not existing:
                raise AppException.not_found("User not found")

            session_ids = [
                s.id
                async for s in self.session_querier.list_sessions_by_user(user_id=user_id)
            ]
            await self.session_querier.delete_all_user_sessions(user_id=user_id)
            await self.user_querier.delete_user(id=user_id)

            for sid in session_ids:
                await SessionService.delete_session_cache(redis=redis, session_id=sid)

            return existing
        except Exception as exc:
            logger.error("Failed to delete user: %s", exc)
            raise DBException.handle(exc)

    async def find_closest_user(self, *, embedding_literal: str) -> ClosestUserMatch | None:
        row = await self.user_querier.find_closest_user_by_embedding(
            dollar_1=embedding_literal,
        )
        if row is None or row.distance is None:
            return None
        return ClosestUserMatch(user_id=row.id, distance=float(row.distance))

    async def check_rate_limit(
        self,
        redis: RedisClient,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        """Enforce rate limiting using Redis INCR + EXPIRE. Fails open if Redis is unavailable."""
        try:
            current_count = await redis.incr(key)
            if current_count == 1:
                await redis.expire(key, window_seconds)
        except HTTPException:
            raise
        except Exception:
            logger.warning("check_rate_limit: redis unavailable, failing open for key=%s", key)
            return

        if current_count > max_requests:
            raise AppException.too_many_requests(
                "Too many requests. Please try again later.",
                retry_after=window_seconds,
            )
