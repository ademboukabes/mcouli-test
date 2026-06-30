from typing import Annotated
import uuid

from fastapi import Cookie, Depends
from app.container import Container, get_container
from app.core.exceptions import AppException
from db.generated.models import StaffRole, StaffUser
from app.core.securite import decode_staff_token



def _role_value(role: object) -> str:
    return getattr(role, "value", str(role))



async def get_current_staff_user(
    container: Annotated[Container, Depends(get_container)],
    token: Annotated[str | None, Cookie(alias="access_token")] = None,
) -> StaffUser:
    if token is None :
        raise AppException.unauthorized("token doestn exist")
    else :
        payload = decode_staff_token(token)
        staff_id_str = payload.sub

        if not staff_id_str:
            raise AppException.unauthorized("Token missing subject")

        # 2. Convert to UUID and fetch user from DB
        try:
            staff_id = uuid.UUID(staff_id_str)
        except ValueError:
            raise AppException.unauthorized("Invalid staff ID in token")

        staff_user = await container.staff_user_querier.get_staff_user_by_id(id=staff_id)
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


def ensure_admin_staff(current_staff_user: StaffUser) -> StaffUser:
    if _role_value(current_staff_user.role) != StaffRole.ADMIN.value:
        raise AppException.forbidden("Admin access required")
    return current_staff_user

async def require_admin_staff(
    current_staff_user: Annotated[StaffUser, Depends(get_current_staff_user)],
) -> StaffUser:
    return ensure_admin_staff(current_staff_user)
