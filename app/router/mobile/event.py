from typing import List

from fastapi import APIRouter, Depends

from app.container import Container, get_container
from app.deps.auth import MobileUserSchema, get_current_mobile_user
from app.schema.request.web.event import JoinEventRequest
from app.schema.response.web.event import JoinEventResponse, UserEventResponse


router = APIRouter(prefix="/event")
@router.post("/join", response_model=JoinEventResponse)
async def join_event(
    req: JoinEventRequest,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user), 
)-> JoinEventResponse:
    return await container.event_service.join_event_by_code(
        user_id=current_user.user_id,
        code=req.event_code
    )


@router.get("/me", response_model=List[UserEventResponse])
async def get_my_joined_events(
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user), 
)-> List[UserEventResponse]:
    return await container.event_service.get_my_events(current_user.user_id)
