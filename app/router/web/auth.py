from fastapi import APIRouter, Depends
from app.container import Container, get_container
from app.schema.auth.web.authSc import WebAuthRequest, WebAuthResponse

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
