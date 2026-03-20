from fastapi import APIRouter, Depends

from app.container import Container, get_container
from app.deps.cookie_auth import get_current_staff_user
from app.schema.request.staff.notifications import MarkStaffNotificationsReadRequest
from app.schema.response.staff.notifications import (
    StaffNotificationListResponse,
)
from db.generated.models import StaffUser


router = APIRouter(prefix="/notifications")


@router.get("", response_model=StaffNotificationListResponse)
async def list_staff_notifications(
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> StaffNotificationListResponse:
    notifications = await container.staff_notifications_service.list_notifications(
        staff_user_id=current_staff_user.id
    )
    return StaffNotificationListResponse.from_models(notifications)


@router.post("/read", response_model=StaffNotificationListResponse)
async def mark_staff_notifications_as_read(
    req: MarkStaffNotificationsReadRequest,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> StaffNotificationListResponse:
    notifications = await container.staff_notifications_service.mark_many_as_read(
        notification_ids=req.notification_ids,
        staff_user_id=current_staff_user.id,
    )
    return StaffNotificationListResponse.from_models(notifications)
