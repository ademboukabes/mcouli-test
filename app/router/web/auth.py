from fastapi import APIRouter, Depends, status
from app.container import Container, get_container
from app.deps.staff_auth import get_current_staff_user
from app.schema.auth.web.authSc import WebAuthRequest, WebAuthResponse
from app.schema.response.web.staff_user import StaffUserSchema # Ensure this path is correct

router = APIRouter(prefix="/auth", tags=["web-auth"])

@router.post("/login", response_model=WebAuthResponse)
async def admin_login(
    req: WebAuthRequest, 
    container: Container = Depends(get_container),
) -> WebAuthResponse:
    """Authenticates a staff member and creates a session."""
    return await container.web_auth_service.admin_login(
        email=req.email,
        password=req.password
    )

@router.post("/logout", status_code=status.HTTP_200_OK)
async def staff_logout(
    container: Container = Depends(get_container),
    current_staff: StaffUserSchema = Depends(get_current_staff_user),
) -> dict[str, str]:
    """
    Staff Only: Invalidate the current web session.
    Uses the staff id and device_id extracted from the session.
    """
    assert current_staff.device_id is not None 

    return await container.staff_session_service.delete_staff_session(
        staff_id=current_staff.id,
        device_id=current_staff.device_id
    )