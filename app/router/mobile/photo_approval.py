from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.container import Container, get_container
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.schema.request.mobile.photo_approval import PhotoApprovalRequest

router = APIRouter(prefix="/photos")


@router.get("/approvals")
async def list_my_approvals(
    status: Literal["pending", "approved", "rejected"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
    container: Container = Depends(get_container),
) -> list[dict[str, object]]:
    approvals = []
    async for a in container.photo_approval_querier.list_approvals_by_user_and_status(
        user_id=current_user.user_id,
        dollar_2=status,
        limit=limit,
        offset=offset,
    ):
        approvals.append({
            "id": str(a.id),
            "photo_id": str(a.photo_id),
            "decision": a.decision,
            "decided_at": a.decided_at.isoformat() if a.decided_at else None,
        })
    return approvals


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
