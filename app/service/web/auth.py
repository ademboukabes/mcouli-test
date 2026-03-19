
from app.core.exceptions import AppException
from app.core.securite import (
    create_access_staff_token,   # Updated
    create_refresh_staff_token,  # Updated
    Get_expiry_time,
    verify_password
)
from db.generated import stuff_user as staff_queries

from app.schema.auth.web.authSc import WebAuthResponse
from db.generated.models import StaffUser

class WebAuthService:
    def __init__(
        self,
        staff_querier: staff_queries.AsyncQuerier,
        # Removed staff_session_service here
    ):
        self.staff_querier = staff_querier

    async def admin_login(
        self,
        email: str,
        password: str,
    ) -> WebAuthResponse:
        # 1. Verify user exists
        staff: StaffUser | None = await self.staff_querier.get_staff_user_by_email(email=email)

        if not staff or not verify_password(password, staff.password):
            raise AppException.unauthorized("Invalid email or password")

        # 2. Generate Stateless Tokens
        # We only pass staff_id and role. No more session_id.
        access_token = create_access_staff_token(
            staff_id=str(staff.id),
            role=staff.role
        )

        refresh_token = create_refresh_staff_token(
            staff_id=str(staff.id),
            role=staff.role
        )

        return WebAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=staff.id,
            role=staff.role,
            expires_in=Get_expiry_time(),
        )
