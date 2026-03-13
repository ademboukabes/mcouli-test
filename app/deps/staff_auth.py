from typing import Annotated
import uuid

from fastapi import Depends, Header

from app.container import Container, get_container
from app.core.exceptions import AppException
from db.generated.models import StaffUser


async def get_current_staff_user(
    x_staff_user_id: Annotated[str, Header(alias="X-Staff-User-Id")],
    container: Annotated[Container, Depends(get_container)],
) -> StaffUser:
    try:
        staff_user_id = uuid.UUID(x_staff_user_id)
    except ValueError as exc:
        raise AppException.bad_request("Invalid X-Staff-User-Id header") from exc

    staff_user = await container.staff_user_querier.get_staff_user_by_id(id=staff_user_id)
    if staff_user is None:
        raise AppException.not_found("Staff user not found")

    return staff_user
