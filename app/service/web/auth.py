from typing import Optional
import uuid
from app.core.exceptions import AppException
from app.core.securite import (
    create_access_staff_token,   # Updated
    create_refresh_staff_token,  # Updated
    Get_expiry_time,
    verify_password
)
from db.generated import stuff_user as staff_queries
# Import the new service
from app.service.staff_session import StaffSessionService 

from app.schema.auth.web.authSc import WebAuthResponse

class WebAuthService:
    def __init__(
        self,
        staff_querier: staff_queries.AsyncQuerier,
        staff_session_service: StaffSessionService, # Inject the new service
    ):
        self.staff_querier = staff_querier
        self.staff_session_service = staff_session_service

    async def admin_login(
        self,
        email: str,
        password: str,
        # device_id can be passed from frontend or generated per browser session
        device_id: Optional[uuid.UUID] = None
    ) -> WebAuthResponse:
        # 1. Verify the Staff User exists
        staff = await self.staff_querier.get_staff_user_by_email(email=email)
    
        if not staff or not verify_password(password, staff.password):
            raise AppException.unauthorized("Invalid email or password")

        # 2. Handle Staff Session (Database + Redis combined in service)
        # If no device_id provided, generate a stable one for the web portal
        if not device_id:
            device_id = uuid.uuid5(uuid.NAMESPACE_DNS, "web-admin-panel")

        # This now uses the staff_sessions table (fixing the FK error)
        session = await self.staff_session_service.create_staff_session(
            staff_id=staff.id,
            device_id=device_id,
            role=staff.role
        )

        # 3. Generate Staff-Specific Tokens
        access_token = create_access_staff_token(
            session_id=str(session.id), 
            staff_id=str(staff.id), 
            role=staff.role
        )
        refresh_token = create_refresh_staff_token(
            session_id=str(session.id), 
            staff_id=str(staff.id)
        )
        
        return WebAuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user_id=staff.id,
            role=staff.role,
            expires_in=Get_expiry_time(),
        )