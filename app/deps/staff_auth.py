from typing import Annotated
import uuid

from fastapi import Depends
from app.container import Container, get_container
from app.core.exceptions import AppException
from db.generated.models import StaffRole, StaffUser


def _role_value(role: object) -> str:
    return getattr(role, "value", str(role))
from db.generated.models import StaffUser
from fastapi.security import OAuth2PasswordBearer
from app.core.securite import decode_staff_token
from db.generated.models import StaffUser


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

async def get_current_staff_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    container: Annotated[Container, Depends(get_container)],
) -> StaffUser:
    # 1. Decode the JWT
    payload = decode_staff_token(token)
    staff_id_str = payload.get("sub")
    
    if not staff_id_str:
        raise AppException.unauthorized("Token missing subject")

    # 2. Convert to UUID and fetch user from DB
    try:
        staff_id = uuid.UUID(staff_id_str)
    except ValueError:
        raise AppException.unauthorized("Invalid staff ID in token")

    staff_user = await container.staff_user_querier.get_staff_user_by_id(id=staff_user_id)
    if staff_user is None:
        raise AppException.not_found("Staff user not found")

    return staff_user


def ensure_multi_team_lead_staff(current_staff_user: StaffUser) -> StaffUser:
    if _role_value(current_staff_user.role) != StaffRole.MULTI_TEAM_LEAD.value:
        raise AppException.forbidden("Multi team lead access required")
    return current_staff_user


async def require_multi_team_lead_staff(
    current_staff_user: Annotated[StaffUser, Depends(get_current_staff_user)],
) -> StaffUser:
    return ensure_multi_team_lead_staff(current_staff_user)
    staff_user = await container.staff_querier.get_staff_user_by_id(id=staff_id)
    
    if not staff_user:
        raise AppException.not_found("Staff user no longer exists")
        
    return staff_user
