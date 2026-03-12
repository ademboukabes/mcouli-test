from typing import Optional

from fastapi import APIRouter, Depends
from uuid import UUID

from app.container import get_container, Container
from app.core.exceptions import AppException
from app.deps.auth import MobileUserSchema, get_current_mobile_user

from app.schema.request.mobile.auth import MobileAuthRequest, RefreshTokenRequest
from app.schema.response.mobile.auth import MeResponse, DeviceSchema, MobileAuthResponse, SessionSchema, UserSchema

router = APIRouter(prefix="/auth", tags=["mobile-auth"])


@router.post("/register-login", response_model=MobileAuthResponse)
async def mobile_register_login(
    req: MobileAuthRequest,
    container: Container = Depends(get_container),
):

    return await container.auth_service.mobile_register_login(container.redis, req)


@router.post("/refresh", response_model=MobileAuthResponse)
async def refresh_token(
    req: RefreshTokenRequest,
    container: Container = Depends(get_container),
):

    return await container.auth_service.refresh_token(container.redis, req.refresh_token)


@router.post("/logout")
async def logout(
    container: Container = Depends(get_container),
    User:MobileUserSchema = Depends(get_current_mobile_user)
):

    return await container.auth_service.logout(
        container.redis,
        str(User.user_id),
        str(User.session_id),
    )


@router.post("/revoke-device")
async def revoke_device(
    device_id: UUID,
    container: Container = Depends(get_container),
    current_user:MobileUserSchema = Depends(get_current_mobile_user),
):

    await container.device_service.revoke_device(
        device_id=device_id,
        user_id=current_user.user_id,
    )
    return {"message": "Device revoked successfully"}


@router.get("/me", response_model=MeResponse)
async def get_me(
    current_user:MobileUserSchema = Depends(get_current_mobile_user),
    container: Container = Depends(get_container),
):

    user = await container.auth_service.user_querier.get_user_by_id(id=current_user.user_id)
    if user is None :
        raise AppException.not_found("user not found")

    devices, _ = await container.device_service.get_all_devices(current_user.user_id)
    device_list = [
        DeviceSchema(
            id=d.id,
            device_name=d.device_name or "uknown ",
            device_type=d.device_type or "uknown ",
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
