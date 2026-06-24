from typing import Optional

from fastapi import APIRouter, Depends, Request
from uuid import UUID

from app.container import get_container, Container
from app.core.config import settings
from app.core.constant import AuditEventType
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user

from app.schema.request.mobile.auth import (
    MobileLoginRequest,
    MobileRegisterRequest,
    RegisterVerifyRequest,
    ResendOtpRequest,
    RefreshTokenRequest,
    UpdateDeviceTokenRequest,
    InactivateDeviceRequest,
)
from app.schema.response.mobile.auth import MeResponse, DeviceSchema, MobileAuthResponse, SessionSchema, UserSchema, RegisterPendingResponse

router = APIRouter(prefix="/auth")


def _get_client_ip(request: Request) -> str | None:
    if settings.TRUST_PROXY_HEADERS:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", maxsplit=1)[0].strip() or None

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip() or None

    return request.client.host if request.client else None


@router.post("/register", response_model=RegisterPendingResponse)
async def mobile_register(
    req: MobileRegisterRequest,
    request: Request,
    container: Container = Depends(get_container),
) -> RegisterPendingResponse:
    client_ip = _get_client_ip(request)
    result = await container.auth_service.mobile_register(container.redis, req, client_ip=client_ip)
    return result


@router.post("/register/resend-otp", response_model=RegisterPendingResponse)
async def mobile_register_resend_otp(
    req: ResendOtpRequest,
    request: Request,
    container: Container = Depends(get_container),
) -> RegisterPendingResponse:
    client_ip = _get_client_ip(request)
    result = await container.auth_service.mobile_register_resend_otp(container.redis, req.email, client_ip=client_ip)
    return result


@router.post("/register/verify", response_model=MobileAuthResponse)
async def mobile_register_verify(
    req: RegisterVerifyRequest,
    request: Request,
    container: Container = Depends(get_container),
) -> MobileAuthResponse:
    client_ip = _get_client_ip(request)
    result = await container.auth_service.verify_mobile_register(container.redis, req, client_ip=client_ip)
    await container.audit_service.create_record(
        event_type=AuditEventType.USER_SIGNUP,
        user_id=result.user_id,
        metadata={"endpoint": "register_verify"},
    )
    return result


@router.post("/login", response_model=MobileAuthResponse)
async def mobile_login(
    req: MobileLoginRequest,
    request: Request,
    container: Container = Depends(get_container),
) -> MobileAuthResponse:
    client_ip = _get_client_ip(request)
    result = await container.auth_service.mobile_login(container.redis, req, client_ip=client_ip)
    await container.audit_service.create_record(
        event_type=AuditEventType.USER_LOGIN,
        user_id=result.user_id,
        metadata={"endpoint": "login"},
    )
    return result


@router.post("/refresh", response_model=MobileAuthResponse)
async def refresh_token(
    req: RefreshTokenRequest,
    container: Container = Depends(get_container),
) -> MobileAuthResponse:
    return await container.auth_service.refresh_token(container.redis, req.refresh_token)


@router.post("/logout")
async def logout(
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
) -> dict[str, str]:
    result = await container.auth_service.logout(
        container.redis,
        str(current_user.user_id),
        str(current_user.session_id),
    )
    await container.audit_service.create_record(
        event_type=AuditEventType.USER_LOGOUT,
        user_id=current_user.user_id,
    )
    return result


@router.post("/revoke-device")
async def revoke_device(
    device_id: UUID,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
) -> dict[str, str]:
    from app.core.constant import RedisKey

    session = await container.session_service.session_querier.get_session_by_device(
        device_id=device_id
    )
    if session:
        await container.session_service.delete_session_cache(container.redis, session.id)

    user_session_key = RedisKey.UserSessionByUser.value.format(user_id=current_user.user_id)
    await container.redis.delete(user_session_key)

    await container.device_service.revoke_device(
        device_id=device_id,
        user_id=current_user.user_id,
    )
    return {"message": "Device revoked successfully"}


@router.post("/devices/token")
async def update_device_token(
    req: UpdateDeviceTokenRequest,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
) -> dict[str, str]:

    await container.device_service.update_device_push_token(
        device_id=req.device_id,
        user_id=current_user.user_id,
        push_token=req.push_token,
    )

    return {"message": "Device token updated"}


@router.post("/devices/inactivate")
async def inactivate_device(
    req: InactivateDeviceRequest,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
) -> dict[str, str]:

    await container.device_service.inactivate_device(
        device_id=req.device_id,
        user_id=current_user.user_id,
    )

    return {"message": "Device marked as inactive"}


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
    container: Container = Depends(get_container),
) -> MeResponse:
    user = await container.auth_service.get_user(user_id=current_user.user_id)

    devices, _ = await container.device_service.get_all_devices(current_user.user_id)
    device_list = [
        DeviceSchema(
            id=d.id,
            device_name=d.device_name or "unknown",
            device_type=d.device_type or "unknown",
            totp_secret=d.totp_secret,
        )
        for d in devices
    ]

    session_schema: Optional[SessionSchema] = None
    sessions_objs = await container.session_service.session_querier.get_session_by_id(
        id=current_user.session_id
    )

    if sessions_objs:
        session_schema = SessionSchema(
            session_id=sessions_objs.id,
            device_id=sessions_objs.device_id,
            last_active=sessions_objs.last_active,
            expires_at=sessions_objs.expires_at,
        )

    return MeResponse(
        user=UserSchema(id=user.id, email=user.email),
        devices=device_list,
        sessions=session_schema,
    )
