import uuid
from fastapi import APIRouter, Depends, status
from typing import List, Optional

from app.container import get_container, Container

from app.deps.cookie_auth import (
    get_current_staff_user
)
from app.schema.request.web.event import (
    EventCreate,

)
from app.schema.response.web.event import (
    EventResponse,
)

from db.generated import models

router = APIRouter(prefix="/events")


@router.get("/", response_model=List[EventResponse])
async def list_events(
    limit: int = 10,
    offset: int = 0,
    name: Optional[str] = None,
    status: Optional[models.EventStatus] = None,
    container: Container = Depends(get_container),
    current_staff: models.StaffUser = Depends(get_current_staff_user),
)-> List[EventResponse]:
    """Staff Only: List all events with optional filters."""

    if name:
        return await container.event_service.find_events_by_name(name)

    return await container.event_service.list_events(
        limit=limit,
        offset=offset,
        status=status
    )

@router.post("/", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    req: EventCreate,
    container: Container = Depends(get_container),
    current_staff: models.StaffUser = Depends(get_current_staff_user),
)-> EventResponse:
    """Staff Only: Create a new event."""
    return await container.event_service.create_event(req, current_staff.id)


@router.post("/{event_id}/archive", response_model=EventResponse)
async def archive_event(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_staff: models.StaffUser = Depends(get_current_staff_user), # Use Staff Dep
)-> EventResponse:
    """Staff Only: Archive an event."""
    return await container.event_service.update_status(event_id, "archived")


@router.post("/{event_id}/schedule", response_model=EventResponse)
async def schedule_event(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_staff: models.StaffUser = Depends(get_current_staff_user), # Use Staff Dep
)-> EventResponse:
    """Staff Only: Move to scheduled."""
    return await container.event_service.update_status(event_id, "scheduled")


@router.post("/{event_id}/draft", response_model=EventResponse)
async def draft_event(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_staff: models.StaffUser = Depends(get_current_staff_user),
)-> EventResponse:
    """Staff Only: Move an event back to draft status."""
    return await container.event_service.update_status(event_id, "draft")

