from typing import Optional
import uuid

from app.core.exceptions import AppException, DBException
from db.generated import stuff_user as staff_queries
from db.generated.models import StaffUser, StaffRole


class StaffUserService:
    staff_user_querier: staff_queries.AsyncQuerier

    def init(self, staff_user_querier: staff_queries.AsyncQuerier) -> None:
        self.staff_user_querier = staff_user_querier

    async def create_staff_user(
        self, *, email: Optional[str], discord_id: str, role: StaffRole
    ) -> StaffUser:
        try:
            if role == StaffRole.ADMIN:
                user = await self.staff_user_querier.create_admin(
                    email=email, discord_id=discord_id
                )
            else:
                user = await self.staff_user_querier.create_multi(
                    email=email, discord_id=discord_id
                )
            if user is None:
                raise AppException.internal_error("Failed to create staff user")
            return user
        except Exception as exc:
            raise DBException.handle(exc)

    async def update_staff_user(
        self, *, id: uuid.UUID, email: Optional[str], discord_id: str, role: StaffRole
    ) -> StaffUser:
        try:
            user = await self.staff_user_querier.update_staff_user(
                id=id, email=email, discord_id=discord_id, role=role.value
            )
            if user is None:
                raise AppException.not_found("Staff user not found")
            return user
        except Exception as exc:
            raise DBException.handle(exc)

    async def delete_staff_user(self, *, id: uuid.UUID) -> StaffUser:
        try:
            user = await self.staff_user_querier.delete_staff_user(id=id)
            if user is None:
                raise AppException.not_found("Staff user not found")
            return user
        except Exception as exc:
            raise DBException.handle(exc)

    async def list_staff_users(self, *, limit: int, offset: int) -> list[StaffUser]:
        result = []
        async for user in self.staff_user_querier.get_all_staff_users(limit=limit, offset=offset):
            result.append(user)
        return result
