
from app.core.logger import logger
from typing import Literal, Optional
import uuid

from app.core.exceptions import AppException, DBException, DBExceptionImpl
from app.core.securite import hash_password
from db.generated import stuff_user as staff_queries
from db.generated.stuff_user import ListStaffUsersParams
from db.generated.models import StaffUser, StaffRole


class StaffUserService:
    staff_user_querier: staff_queries.AsyncQuerier

    def init(self, staff_user_querier: staff_queries.AsyncQuerier) -> None:
        self.staff_user_querier = staff_user_querier

    async def create_staff_user(
        self, *, email: Optional[str], password: str, role: StaffRole
    ) -> StaffUser:
        try:
            hashed_password = hash_password(password)
            user = await self.staff_user_querier.create_multi(
                email=email,
                password=hashed_password,
                role=role,
            )
            if user is None:
                raise AppException.internal_error("Failed to create staff user")
            return user
        except Exception as exc:
            logger.error("Failed to create staff user: %s", exc)
            raise DBExceptionImpl.handle(exc)

    async def update_staff_user(
        self, *, id: uuid.UUID, email: Optional[str], role: StaffRole
    ) -> StaffUser:
        try:
            user = await self.staff_user_querier.update_staff_user(
                id=id, email=email, role=role.value
            )
            if user is None:
                raise AppException.not_found("Staff user not found")
            return user
        except Exception as exc:
            logger.error("Failed to update staff user: %s", exc)
            raise DBException.handle(exc)

    async def delete_staff_user(self, *, id: uuid.UUID) -> StaffUser:
        try:
            user = await self.staff_user_querier.delete_staff_user(id=id)
            if user is None:
                raise AppException.not_found("Staff user not found")
            return user
        except Exception as exc:
            raise DBException.handle(exc)

    async def list_staff_users(
        self,
        *,
        limit: int,
        offset: int,
        search: str | None,
        role: StaffRole | None,
        sort_by: Literal["created_at", "email"],
        sort_direction: Literal["asc", "desc"],
    ) -> list[StaffUser]:
        try:
            if search is not None:
                normalized_search = search.strip() 
            else:
                normalized_search = None
            
            params = ListStaffUsersParams(
                column_1=normalized_search,               
                column_2=role.value if role is not None else None ,      
                column_3=sort_by,
                column_4=sort_direction,
                limit=limit,
                offset=offset,
            )

            result: list[StaffUser] = []
            async for user in self.staff_user_querier.list_staff_users(params):
                result.append(user)
            return result
        except Exception as exc:
            logger.error("Failed to list staff users: %s", exc)
            raise DBException.handle(exc)
