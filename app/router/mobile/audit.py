from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.container import Container, get_container
from app.core.constant import AuditEventType
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user
from app.schema.response.mobile.audit import AuditEventListResponse, AuditEventSchema

router = APIRouter(prefix="/audits", tags=["audits"])


@router.get("", response_model=AuditEventListResponse)
async def list_audits(
    event_type: AuditEventType | None = Query(None),
    user_id: UUID | None = Query(None),
    created_from: datetime | None = Query(None, alias="from"),
    created_to: datetime | None = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    container: Container = Depends(get_container),
    _: MobileUserSchema = Depends(get_current_mobile_user),
) -> AuditEventListResponse:
    events = await container.audit_service.list_audit_events(
        event_type=event_type,
        user_id=user_id,
        created_from=created_from,
        created_to=created_to,
        limit=limit,
        offset=offset,
    )
    return AuditEventListResponse(
        items=[
            AuditEventSchema.from_model(audit_event, actor=actor)
            for audit_event, actor in events
        ]
    )
