from fastapi import APIRouter, Depends
from app.container import Container, get_container
from app.deps.staff_auth import get_current_staff_user
from app.schema.auth.web.authSc import WebAuthRequest, WebAuthResponse
from db.generated.models import StaffUser

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

@router.post("/logout")
async def staff_logout(
    container: Container = Depends(get_container),
    current_staff: StaffUser = Depends(get_current_staff_user),
):
    # Pass ONLY the staff_id
    return await container.staff_session_service.delete_staff_session(
        staff_id=current_staff.id
    )