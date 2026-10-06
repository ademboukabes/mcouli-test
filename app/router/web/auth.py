from fastapi import APIRouter, Depends, Request, Cookie
from app.container import Container, get_container
from fastapi import Response
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.deps.cookie_auth import get_current_staff_user
from app.schema.response.web.staff_user import StaffUserSchema
from db.generated.models import StaffUser
from app.core.exceptions import AppException
import urllib.parse
import secrets

router = APIRouter(prefix="/auth")


@router.get("/mcdi/login")
async def mcdi_login(r: Response) -> RedirectResponse:
    state = secrets.token_urlsafe(16)
    r.set_cookie(
        "mcdi_state",
        state,
        httponly=True,
        max_age=300,
        secure=settings.environment != "dev",
        samesite="lax"
    )
    params = urllib.parse.urlencode({
        "client_id": settings.MCDI_PROJECT_ID,
        "redirect_uri": settings.MCDI_REDIRECT_URI_WEB,
        "state": state
    })
    url = f"{settings.MCDI_BASE_URL.replace('/api', '')}/api/auth/sso/authorize?{params}"
    return RedirectResponse(url)


@router.get("/mcdi/callback")
async def mcdi_callback(
    request: Request,
    r: Response,
    code: str,
    state: str,
    container: Container = Depends(get_container),
) -> RedirectResponse:
    cookie_state = request.cookies.get("mcdi_state")
    if not cookie_state or state != cookie_state:
        raise AppException.unauthorized("Invalid state parameter")

    mcdi_data = await container.mcdi_service.exchange_code(code, settings.MCDI_REDIRECT_URI_WEB)

    # Extract email and verify staff access
    email = mcdi_data.get("member", {}).get("email")
    if not email:
        raise AppException.unauthorized("No email provided by MCDI")

    staff_user = await container.staff_user_querier.get_staff_user_by_email(email=email)
    if not staff_user:
        raise AppException.unauthorized("Not authorized for admin panel")

    token = mcdi_data.get("token")
    if not token:
        raise AppException.internal_error("MCDI did not return a session token")

    # Let the frontend dashboard URL be determined by CORS origin or environment
    frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:5173"

    redirect_res = RedirectResponse(url=f"{frontend_url}/dashboard")
    redirect_res.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.environment != "dev",
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    redirect_res.delete_cookie("mcdi_state")
    return redirect_res


@router.get("/me", response_model=StaffUserSchema)
async def get_me_admin(
    user: StaffUser = Depends(get_current_staff_user),
) -> StaffUserSchema:
    return StaffUserSchema(
        id=user.id,
        created_at=user.created_at,
        role=user.role,
        updated_at=user.updated_at,
        email=user.email,
    )


@router.post("/logout", status_code=204)
async def admin_logout(
    r: Response,
    token: str | None = Cookie(default=None, alias="access_token"),
    container: Container = Depends(get_container),
) -> None:
    # We could also call MCDI logout endpoint here to kill the session globally or for this project
    # But removing the cookie is the minimum required.
    r.delete_cookie(
        key="access_token",
        httponly=True,
        secure=settings.environment != "dev",
        samesite="lax",
    )
