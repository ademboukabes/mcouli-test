from fastapi import APIRouter, Depends

from app.container import Container, get_container
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.schema.request.mobile.notifications import MarkUserNotificationsReadRequest
from app.schema.response.mobile.notifications import UserNotificationListResponse


router = APIRouter(prefix="/notifications")


@router.get("", response_model=UserNotificationListResponse)
async def get_all_notifications(
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
) -> UserNotificationListResponse:
    notifications = await container.user_notifications_service.get_all_notifications(
        user_id=current_user.user_id,
    )
    return UserNotificationListResponse.from_models(notifications)


@router.post("/read", response_model=UserNotificationListResponse)
async def mark_as_read(
    req: MarkUserNotificationsReadRequest,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
) -> UserNotificationListResponse:
    notifications = await container.user_notifications_service.mark_notifications_as_read(
        notification_ids=req.notification_ids,
        user_id=current_user.user_id,
    )
    return UserNotificationListResponse.from_models(notifications)
