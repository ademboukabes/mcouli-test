from fastapi import APIRouter, Depends
from app.container import Container, get_container
from fastapi import Response

from app.deps.staff_auth import get_current_staff_user
from app.schema.request.web.auth import WebAuthRequest
from app.schema.response.web.auth import WebAuthResponse
from db.generated.models import StaffUser
router = APIRouter(prefix="/auth")

@router.post("/login", response_model=WebAuthResponse,description="so here both the dahbsoard will authneticate from this endpoitn ")
async def admin_login(
    req: WebAuthRequest,
    r:Response,
    container: Container = Depends(get_container),
) -> WebAuthResponse:

    authResponse = await container.staff_user_service.admin_login(
        email=req.email,
        password=req.password
    )
    r.set_cookie(
        key="access_token",
        value=authResponse.access_token,
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=60 * 60 * 24 * 7,
    )
    return authResponse


@router.get("/me",response_model=WebAuthResponse)
async def get_me_admin(
    user:StaffUser = Depends(get_current_staff_user),
    container:Container = Depends(get_container)
):
    return user