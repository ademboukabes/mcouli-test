from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.container import Container, get_container
from app.core.logger import logger
from app.deps.staff_auth import get_current_staff_user
from app.schema.request.web.staff_user import StaffUserCreateRequest, StaffUserUpdateRequest
from app.schema.response.web.staff_user import StaffUserSchema
from db.generated.models import StaffRole, StaffUser

router = APIRouter(prefix="/staff-users")


@router.get("/", response_model=list[StaffUserSchema])
async def list_staff_users(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(default=None),
    role: StaffRole | None = Query(default=None),
    sort_by: Literal["created_at", "email"] = Query(default="created_at"),
    sort_direction: Literal["asc", "desc"] = Query(default="desc"),
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> list[StaffUserSchema]:
    staff_users = await container.staff_user_service.list_staff_users(
        limit=limit,
        offset=offset,
        search=search,
        role=role,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    return [
        StaffUserSchema(
            id=user.id,
            email=user.email,
            role=user.role,
            created_at=user.created_at,
            updated_at=user.updated_at
        )
        for user in staff_users
    ]


@router.post("/", response_model=StaffUserSchema, status_code=status.HTTP_201_CREATED)
async def create_staff_user(
    req: StaffUserCreateRequest,
    container: Container = Depends(get_container),
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
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),

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
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
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
