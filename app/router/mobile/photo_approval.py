from uuid import UUID

from fastapi import APIRouter, Depends

from app.container import Container, get_container
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.schema.request.mobile.photo_approval import PhotoApprovalRequest

router = APIRouter(prefix="/photos")


@router.post("/{photo_id}/decision")
async def decide_photo_approval(
    photo_id: UUID,
    req: PhotoApprovalRequest,
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
    container: Container = Depends(get_container),
) -> dict[str, str]:
    photo_status = await container.photo_approval_service.decide(
        photo_id=photo_id,
        user_id=current_user.user_id,
        decision=req.decision,
    )
    return {"message": "Decision recorded", "photo_status": photo_status}
