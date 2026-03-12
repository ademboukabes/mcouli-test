import uuid
import sqlalchemy.ext.asyncio
from typing import List
from app.core.exceptions import AppException
from app.schema.web.event import EventCreate, EventResponse, JoinEventRequest, JoinEventResponse
from db.generated import events as event_queries
from db.generated import joinEv as join_queries

class EventService:
    # Constructor for injection
    def __init__(self, e_querier: event_queries.AsyncQuerier, j_querier: join_queries.AsyncQuerier):
        self.e_querier = e_querier
        self.j_querier = j_querier
    
    async def create_event(self, req: EventCreate) -> EventResponse:
        event = await self.e_querier.create_event(
            name=req.name,
            qr_code_hash=req.qr_code_hash,
            event_date=req.event_date
        )
        if not event:
            raise AppException.internal_error("Failed to create event")
        return EventResponse.model_validate(event)

    async def delete_event(self, event_id: uuid.UUID) -> bool:
        existing = await self.e_querier.get_event_by_id(id=event_id)
        if not existing:
            raise AppException.not_found("Event not found")
        await self.e_querier.delete_event(id=event_id)
        return True

    async def join_event(self, req: JoinEventRequest) -> JoinEventResponse:
        event = await self.e_querier.get_event_by_hash(qr_code_hash=req.qr_code_hash)
        if not event:
            raise AppException.not_found("Invalid QR code: Event does not exist")

        try:
            join_record = await self.j_querier.join_event(
                event_id=event.id,
                user_id=req.user_id
            )
            return JoinEventResponse.model_validate(join_record)
        except Exception as e:
            if "unique constraint" in str(e).lower():
                raise AppException.forbidden("You have already joined this event")
            raise e
        
    async def list_events(self, limit: int = 10, offset: int = 0) -> List[EventResponse]:
        events_list = []
        async for event in self.e_querier.list_events(limit=limit, offset=offset):
            events_list.append(EventResponse.model_validate(event))
        return events_list