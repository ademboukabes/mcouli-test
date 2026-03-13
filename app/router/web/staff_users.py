from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.container import Container, get_container
from app.core.logger import logger
from app.deps.staff_auth import get_current_staff_user
from app.schema.request.web.staff_user import StaffUserCreateRequest, StaffUserUpdateRequest
from app.schema.response.web.staff_user import StaffUserSchema
from db.generated.models import StaffUser, StaffRole

router = APIRouter(prefix="/staff-users", tags=["web-staff-users"])




@router.post("/", response_model=StaffUserSchema, status_code=status.HTTP_201_CREATED)
async def create_staff_user(
    req: StaffUserCreateRequest,
    container: Container = Depends(get_container),
    current_staff_user: StaffUser = Depends(get_current_staff_user),
) -> StaffUserSchema:
    staff_user = await container.staff_user_service.create_staff_user(
        email=req.email, password=req.password, role=StaffRole(req.role)
    )
    logger.info("created staff user %s", req.email or "<no-email>")
    return StaffUserSchema(
        id=staff_user.id,
        email=staff_user.email,
        role=staff_user.role,
        created_at=staff_user.created_at,
        updated_at=staff_user.updated_at
    )


@router.patch("/{staff_user_id}", response_model=StaffUserSchema)
async def update_staff_user(
    staff_user_id: UUID,
    req: StaffUserUpdateRequest,
    container: Container = Depends(get_container),
    current_staff_user: StaffUser = Depends(get_current_staff_user),
) -> StaffUserSchema:
    staff_user = await container.staff_user_service.update_staff_user(
        id=staff_user_id, email=req.email, role=StaffRole(req.role)
    )
    logger.info("updated staff user %s", staff_user_id)
    return StaffUserSchema(
        id=staff_user.id,
        email=staff_user.email,
        role=staff_user.role,
        created_at=staff_user.created_at,
        updated_at=staff_user.updated_at
    )


@router.delete("/{staff_user_id}", response_model=StaffUserSchema)
async def delete_staff_user(
    staff_user_id: UUID,
    container: Container = Depends(get_container),
    current_staff_user: StaffUser = Depends(get_current_staff_user),
) -> StaffUserSchema:
    staff_user = await container.staff_user_service.delete_staff_user(id=staff_user_id)
    logger.info("deleted staff user %s", staff_user_id)
    return StaffUserSchema(
        id=staff_user.id,
        email=staff_user.email,
        role=staff_user.role,
        created_at=staff_user.created_at,
        updated_at=staff_user.updated_at
    )
