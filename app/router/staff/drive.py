from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.container import Container, get_container
from app.core.exceptions import AppException
from app.deps.cookie_auth import get_current_staff_user
from app.schema.response.staff.drive import (
    GoogleDriveCallbackResponse,
    GoogleDriveConnectResponse,
    GoogleDriveConnectionStatusResponse,
    GoogleDriveDisconnectResponse,
)
from db.generated.models import StaffUser


router = APIRouter(prefix="/drive")


@router.get("/connect", response_model=GoogleDriveConnectResponse)
async def connect_google_drive(
    redirect_url: str | None = Query(default=None),
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> GoogleDriveConnectResponse:
    authorization_url, state = await container.staff_drive_service.create_connect_url(
        current_staff_user,
        redirect_url=redirect_url,
    )
    return GoogleDriveConnectResponse(authorization_url=authorization_url, state=state)


@router.get("/callback", response_model=GoogleDriveCallbackResponse)
async def google_drive_callback(
    code: str = Query(...),
    state: str = Query(...),
    error: str | None = Query(default=None),
    container: Container = Depends(get_container),
) -> GoogleDriveCallbackResponse | RedirectResponse:
    redirect_url = await container.staff_drive_service.get_callback_redirect_url(state)
    if error is not None:
        if redirect_url is not None:
            return RedirectResponse(
                container.staff_drive_service.build_frontend_callback_url(
                    redirect_url,
                    status="error",
                    error=error,
                )
            )
        raise AppException.bad_request(f"Google OAuth error: {error}")

    try:
        connection, redirect_url = await container.staff_drive_service.handle_callback(code, state)
    except HTTPException as exc:
        if redirect_url is not None:
            return RedirectResponse(
                container.staff_drive_service.build_frontend_callback_url(
                    redirect_url,
                    status="error",
                    error=str(exc.detail),
                )
            )
        raise

    if redirect_url is not None:
        return RedirectResponse(
            container.staff_drive_service.build_frontend_callback_url(
                redirect_url,
                status="success",
                google_email=connection.google_email,
            )
        )
    return GoogleDriveCallbackResponse(
        message="Google Drive connected successfully",
        google_email=connection.google_email,
    )


@router.get("/status", response_model=GoogleDriveConnectionStatusResponse)
async def google_drive_status(
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> GoogleDriveConnectionStatusResponse:
    connection = await container.staff_drive_service.get_status(current_staff_user.id)
    if connection is None:
        return GoogleDriveConnectionStatusResponse(connected=False)

    return GoogleDriveConnectionStatusResponse(
        connected=True,
        google_email=connection.google_email,
        scopes=[scope for scope in connection.scopes.split(" ") if scope],
        connected_at=connection.connected_at,
        token_expires_at=connection.token_expires_at,
    )


@router.post("/disconnect", response_model=GoogleDriveDisconnectResponse)
async def disconnect_google_drive(
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> GoogleDriveDisconnectResponse:
    await container.staff_drive_service.disconnect(current_staff_user.id)
    return GoogleDriveDisconnectResponse(message="Google Drive disconnected successfully")
