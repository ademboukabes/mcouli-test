from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.container import Container, get_container
from app.core.config import settings
from app.core.logger import logger
from app.deps.cookie_auth import get_current_staff_user
from app.schema.request.web.user import AdminUserCreateRequest, AdminUserUpdateRequest
from app.schema.response.web.user import AdminUserSchema, to_admin_user_schema
from db.generated.models import StaffUser


router = APIRouter(prefix="/users")

@router.post("/", response_model=AdminUserSchema, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: AdminUserCreateRequest,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> AdminUserSchema:
    user = await container.auth_service.create_user(
        email=req.email,
        password=req.password,
        display_name=req.display_name,
        blocked=req.blocked,
    )
    logger.info("admin %s created user %s", current_staff_user.id, user.id)
    return to_admin_user_schema(user)


@router.get("/", response_model=list[AdminUserSchema])
async def list_users(
    limit: int = Query(
        settings.ADMIN_USERS_DEFAULT_LIMIT, ge=1, le=settings.ADMIN_USERS_MAX_LIMIT
    ),
    offset: int = Query(0, ge=0),
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> list[AdminUserSchema]:
    users = await container.auth_service.list_users(limit=limit, offset=offset)
    return [to_admin_user_schema(user) for user in users]


@router.get("/{user_id}", response_model=AdminUserSchema)
async def get_user(
    user_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> AdminUserSchema:
    user = await container.auth_service.get_user(user_id=user_id)
    return to_admin_user_schema(user)


@router.put("/{user_id}", response_model=AdminUserSchema)
async def update_user(
    user_id: UUID,
    req: AdminUserUpdateRequest,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> AdminUserSchema:
    user = await container.auth_service.update_user(
        user_id=user_id,
        email=req.email,
        display_name=req.display_name,
        blocked=req.blocked,
    )
    logger.info("admin %s updated user %s", current_staff_user.id, user_id)
    return to_admin_user_schema(user)


@router.delete("/{user_id}", response_model=AdminUserSchema)
async def delete_user(
    user_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> AdminUserSchema:
    user = await container.auth_service.delete_user(
        redis=container.redis,
        user_id=user_id,
    )
    logger.info("admin %s deleted user %s", current_staff_user.id, user_id)
    return to_admin_user_schema(user)


@router.post("/{user_id}/block", response_model=AdminUserSchema)
async def block_user(
    user_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> AdminUserSchema:
    user = await container.auth_service.block_user(
        redis=container.redis,
        user_id=user_id,
    )
    logger.info("admin %s blocked user %s", current_staff_user.id, user_id)
    return to_admin_user_schema(user)


@router.post("/{user_id}/unblock", response_model=AdminUserSchema)
async def unblock_user(
    user_id: UUID,
    current_staff_user: StaffUser = Depends(get_current_staff_user),
    container: Container = Depends(get_container),
) -> AdminUserSchema:
    user = await container.auth_service.unblock_user(user_id=user_id)
    logger.info("admin %s unblocked user %s", current_staff_user.id, user_id)
    return to_admin_user_schema(user)
