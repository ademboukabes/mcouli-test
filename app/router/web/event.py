import uuid
from fastapi import APIRouter, Depends
from typing import List, Optional

from app.container import get_container, Container
from app.deps.auth import MobileUserSchema, get_current_mobile_user
from app.schema.request.web.event import (
    EventCreate,
    JoinEventRequest
)

from app.schema.response.web.event import (
    EventResponse,
    JoinEventResponse,
    UserEventResponse,
    ParticipantResponse,
)

router = APIRouter(prefix="/events", tags=["events"])

# --- Event Management (Admin/Staff) ---

@router.post("/", response_model=EventResponse)
async def create_event(
    req: EventCreate,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Create a new event. Creator is identified by the current user session."""
    return await container.event_service.create_event(req, current_user.user_id)


# --- Status Action Endpoints ---

@router.post("/{event_id}/archive", response_model=EventResponse)
async def archive_event(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Archive an event (sets status to 'archived' and updates archived_at)."""
    # We pass the status string directly to the service
    return await container.event_service.update_status(event_id, "archived")


@router.post("/{event_id}/schedule", response_model=EventResponse)
async def schedule_event(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Move an event from 'draft' to 'scheduled'."""
    return await container.event_service.update_status(event_id, "scheduled")


@router.post("/{event_id}/draft", response_model=EventResponse)
async def reset_to_draft(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Reset an event back to 'draft' status."""
    return await container.event_service.update_status(event_id, "draft")

@router.delete("/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Delete an event by its ID."""
    await container.event_service.delete_event(event_id)
    return {"message": "Event deleted successfully"}


# --- Discovery & Participation ---

@router.get("/", response_model=List[EventResponse])
async def list_events(
    limit: int = 10,
    offset: int = 0,
    name: Optional[str] = None,
    container: Container = Depends(get_container),
):
    """List all events, optionally filtered by name."""
    if name:
        return await container.event_service.find_events_by_name(name)
    return await container.event_service.list_events(limit=limit, offset=offset)


@router.post("/join", response_model=JoinEventResponse)
async def join_event(
    req: JoinEventRequest,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Join an event by scanning a QR code (event_code)."""
    # Note: We use the user_id from the authenticated token for security
    return await container.event_service.join_event_by_code(
        user_id=current_user.user_id, 
        code=req.event_code
    )


@router.get("/me", response_model=List[UserEventResponse])
async def get_my_joined_events(
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Get all events the currently logged-in user has joined."""
    return await container.event_service.get_my_events(current_user.user_id)


@router.get("/{event_id}/participants", response_model=List[ParticipantResponse])
async def get_event_participants(
    event_id: uuid.UUID,
    container: Container = Depends(get_container),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
):
    """Get the list of attendees for a specific event."""
    return await container.event_service.get_event_attendees(event_id)