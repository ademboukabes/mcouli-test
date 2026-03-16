from fastapi import APIRouter, Depends
from app.container import Container, get_container
# Ensure this path matches your folder structure exactly
from app.schema.auth.web.authSc import WebAuthRequest, WebAuthResponse

router = APIRouter(prefix="/web/auth", tags=["web-auth"])

@router.post("/login", response_model=WebAuthResponse)
async def admin_login(
    req: WebAuthRequest, # Ensure WebAuthRequest schema has 'password' not 'discord_id'
    container: Container = Depends(get_container),
) -> WebAuthResponse:
    return await container.web_auth_service.admin_login(
        redis=container.redis,
        email=req.email,
        password=req.password # Pass password here
    )
    return result