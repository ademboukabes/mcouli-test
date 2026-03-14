from fastapi import APIRouter, Depends
from app.container import Container, get_container
# Ensure this path matches your folder structure exactly
from app.schema.auth.web.authSc import WebAuthRequest, WebAuthResponse

router = APIRouter(prefix="/web/auth", tags=["web-auth"])

@router.post("/login", response_model=WebAuthResponse)
async def admin_login(
    req: WebAuthRequest,
    container: Container = Depends(get_container),
) -> WebAuthResponse: # Explicit return type hint for Pylance
    """Entry point for Admin/Staff login via Discord details."""
    
    # We await the service call and ensure the return type matches WebAuthResponse
    result = await container.web_auth_service.admin_login(
        redis=container.redis,
        email=req.email,
        discord_id=req.discord_id
    )
    return result