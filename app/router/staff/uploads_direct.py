from uuid import UUID

from fastapi import APIRouter, Depends

from app.container import Container, get_container
from app.deps.cookie_auth import get_current_staff_user
from app.schema.internal.uploads import DirectFileInput
from app.schema.request.staff.uploads_direct import (
    CreateDirectGroupRequest,
    RegisterDirectBatchRequest,
)
from app.schema.response.staff.upload_groups import UploadRequestGroupSchema
from app.schema.response.staff.uploads_direct import (
    DirectUploadFileResponse,
    RegisterDirectBatchResponse,
    ResumeDirectGroupResponse,
)
from db.generated.models import StaffUser

router = APIRouter(prefix="/uploads/direct")
# this endpoint are for staff to upload images directly to the system and very large files and they can resume and restart and retry .


@router.post("/groups", response_model=UploadRequestGroupSchema)
async def create_direct_group(
    req: CreateDirectGroupRequest,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> UploadRequestGroupSchema:
    group = await container.upload_requests_service.create_direct_group(
        event_id=req.event_id,
        requested_by=current_staff_user,
    )
    details = await container.upload_requests_service.get_group_details(
        group_id=group.id,
        current_staff_user=current_staff_user,
    )
    return UploadRequestGroupSchema.from_details(details)


@router.post("/groups/{group_id}/batches", response_model=RegisterDirectBatchResponse)
async def register_direct_batch(
    group_id: UUID,
    req: RegisterDirectBatchRequest,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> RegisterDirectBatchResponse:
    results = await container.upload_requests_service.register_direct_batch(
        group_id=group_id,
        files=[
            DirectFileInput(
                file_name=f.file_name,
                mime_type=f.mime_type,
                size_bytes=f.size_bytes,
                taken_at=f.taken_at,
                day_number=f.day_number,
                visibility=f.visibility,
            )
            for f in req.files
        ],
        requested_by=current_staff_user,
    )
    return RegisterDirectBatchResponse(
        group_id=group_id,
        items=[
            DirectUploadFileResponse(
                photo_id=photo.id, file_name=photo.file_name, upload_url=url
            )
            for photo, url in results
        ],
    )


@router.post("/photos/{photo_id}/confirm", response_model=DirectUploadFileResponse)
async def confirm_direct_upload(
    photo_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> DirectUploadFileResponse:
    photo = await container.upload_requests_service.confirm_direct_upload(
        photo_id=photo_id,
        requested_by=current_staff_user,
    )
    return DirectUploadFileResponse(
        photo_id=photo.id, file_name=photo.file_name, upload_url=""
    )


@router.post("/photos/{photo_id}/fail", response_model=DirectUploadFileResponse)
async def fail_direct_upload(
    photo_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> DirectUploadFileResponse:
    photo = await container.upload_requests_service.fail_direct_upload(
        photo_id=photo_id,
        requested_by=current_staff_user,
    )
    return DirectUploadFileResponse(
        photo_id=photo.id, file_name=photo.file_name, upload_url=""
    )


@router.post("/groups/{group_id}/resume", response_model=ResumeDirectGroupResponse)
async def resume_direct_group(
    group_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> ResumeDirectGroupResponse:
    results = await container.upload_requests_service.resume_direct_group(
        group_id=group_id,
        requested_by=current_staff_user,
    )
    return ResumeDirectGroupResponse(
        items=[
            DirectUploadFileResponse(
                photo_id=photo.id, file_name=photo.file_name, upload_url=url
            )
            for photo, url in results
        ]
    )


@router.get("/groups/{group_id}", response_model=UploadRequestGroupSchema)
async def get_direct_group_status(
    group_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> UploadRequestGroupSchema:
    details = await container.upload_requests_service.get_group_details(
        group_id=group_id,
        current_staff_user=current_staff_user,
    )
    return UploadRequestGroupSchema.from_details(details)
