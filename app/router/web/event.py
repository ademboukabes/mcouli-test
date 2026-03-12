import uuid
from fastapi import APIRouter, Depends
from typing import List

# Import your dependency and schemas
from app.container import init_repo 
from app.schema.web.event import (
    EventCreate, 
    EventResponse, 
    JoinEventRequest, 
    JoinEventResponse
)

router = APIRouter(prefix="/events", tags=["events"])

@router.get("/", response_model=List[EventResponse])
async def get_events(
    limit: int = 10,
    offset: int = 0,
    repos: tuple = Depends(init_repo),
):
    """Fetch a paginated list of all events."""
    # 1. Unpack the 5 queriers from your unchanged init_repo
    _, _, _, event_q, join_q = repos
    
    # 2. Manually initialize your service with these queriers
    from app.service.web.eventService import EventService
    event_service = EventService(e_querier=event_q, j_querier=join_q)
    
    # 3. Now this call uses your service's 'async for' logic correctly
    return await event_service.list_events(limit=limit, offset=offset)


@router.post("/", response_model=EventResponse)
async def create_event(
    req: EventCreate,
    repos: tuple = Depends(init_repo),
):
    """Create a new event with a unique QR code hash."""
    # Change from 4 variables to 5
    _, _, _, event_q, join_q = repos
    
    # Initialize the service using the queriers from repos
    from app.service.web.eventService import EventService
    event_service = EventService(e_querier=event_q, j_querier=join_q)
    
    return await event_service.create_event(req)


@router.delete("/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    repos: tuple = Depends(init_repo),
):
    """Delete an event by its ID."""
    # 1. Unpack all 5 items from the tuple
    _, _, _, event_q, join_q = repos
    
    # 2. Initialize the Service manually
    from app.service.web.eventService import EventService
    event_service = EventService(e_querier=event_q, j_querier=join_q)
    
    # 3. Perform the deletion
    await event_service.delete_event(event_id)
    return {"message": "Event deleted successfully"}


@router.post("/join", response_model=JoinEventResponse)
async def join_event(
    req: JoinEventRequest,
    repos: tuple = Depends(init_repo),
):
    """Join an event using the user ID and the scanned QR hash."""
    # 1. Unpack all 5 items from the tuple (even the ones you ignore)
    _, _, _, event_q, join_q = repos
    
    # 2. Initialize the Service manually
    from app.service.web.eventService import EventService
    event_service = EventService(e_querier=event_q, j_querier=join_q)
    
    # 3. Call the join_event method
    return await event_service.join_event(req)