from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.container import Container, get_container
from app.deps.token_auth import MobileUserSchema, get_current_mobile_user

router = APIRouter(prefix="/photos")


@router.get("")
async def list_my_photos(
    event_id: UUID | None = Query(default=None),
    sort: Literal["asc", "desc"] = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
    container: Container = Depends(get_container),
) -> list[dict[str, object]]:
    photos = await container.user_photo_service.list_photos(
        user_id=current_user.user_id,
        event_id=event_id,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return [
        {
            "id": str(p.id),
            "event_id": str(p.event_id),
            "visibility": p.visibility,
            "status": str(p.status),
            "taken_at": p.taken_at.isoformat() if p.taken_at else None,
            "day_number": p.day_number,
            "created_at": p.created_at.isoformat(),
        }
        for p in photos
    ]


@router.get("/event/{event_id}")
async def list_event_photos(
    event_id: UUID,
    sort: Literal["asc", "desc"] = Query(default="desc"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
    container: Container = Depends(get_container),
) -> dict[str, object]:
    photos = await container.user_photo_service.list_event_photos(
        user_id=current_user.user_id,
        event_id=event_id,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    total = await container.user_photo_service.count_event_photos(
        user_id=current_user.user_id,
        event_id=event_id,
    )
    return {
        "total": total,
        "items": [
            {
                "id": str(p.id),
                "event_id": str(p.event_id),
                "visibility": p.visibility,
                "status": str(p.status),
                "taken_at": p.taken_at.isoformat() if p.taken_at else None,
                "day_number": p.day_number,
                "created_at": p.created_at.isoformat(),
            }
            for p in photos
        ],
    }


@router.get("/{photo_id}/image")
async def get_photo_image(
    photo_id: UUID,
    current_user: MobileUserSchema = Depends(get_current_mobile_user),
    container: Container = Depends(get_container),
) -> Response:
    data, filename, content_type = await container.user_photo_service.get_photo_bytes(
        user_id=current_user.user_id,
        photo_id=photo_id,
    )
    return Response(
        content=data,
        media_type=content_type,
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )
