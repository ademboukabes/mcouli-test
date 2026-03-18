from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.container import Container, get_container
from app.deps.staff_auth import (
    get_current_staff_user,
    require_multi_team_lead_staff,
)
from app.schema.request.staff.uploads import (
    CreateUploadRequestRequest,
    RejectUploadRequestRequest,
)
from app.schema.response.staff.uploads import (
    UploadRequestListResponse,
    UploadRequestSchema,
)
from db.generated.models import StaffUser, UploadRequestStatus


router = APIRouter(prefix="/uploads", tags=["staff-uploads"])


@router.post("/request", response_model=UploadRequestSchema)
async def create_upload_request(
    req: CreateUploadRequestRequest,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> UploadRequestSchema:
    upload_request = await container.upload_requests_service.create_request(
        event_id=req.event_id,
        photos=req.to_inputs(),
        requested_by=current_staff_user,
    )
    return UploadRequestSchema.from_models(upload_request.request, upload_request.photos)


@router.get("", response_model=UploadRequestListResponse)
async def list_upload_requests(
    scope: Literal["my", "all"] = Query(default="my"),
    status: UploadRequestStatus | None = Query(default=None),
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> UploadRequestListResponse:
    requests = await container.upload_requests_service.list_requests(
        current_staff_user=current_staff_user,
        scope=scope,
        status=status.value if status is not None else None,
    )
    return UploadRequestListResponse.from_models(
        [(item.request, item.photos) for item in requests]
    )


@router.post("/{request_id}/approve", response_model=UploadRequestSchema)
async def approve_upload_request(
    request_id: UUID,
    current_staff_user: StaffUser = Depends(require_multi_team_lead_staff),
    container: Container = Depends(get_container),
) -> UploadRequestSchema:
    upload_request = await container.upload_requests_service.approve_request(
        request_id=request_id,
        approved_by=current_staff_user,
    )
    return UploadRequestSchema.from_models(upload_request.request, upload_request.photos)


@router.post("/{request_id}/reject", response_model=UploadRequestSchema)
async def reject_upload_request(
    request_id: UUID,
    req: RejectUploadRequestRequest,
    current_staff_user: StaffUser = Depends(require_multi_team_lead_staff),
    container: Container = Depends(get_container),
) -> UploadRequestSchema:
    upload_request = await container.upload_requests_service.reject_request(
        request_id=request_id,
        approved_by=current_staff_user,
        reason=req.reason,
    )
    return UploadRequestSchema.from_models(upload_request.request, upload_request.photos)
