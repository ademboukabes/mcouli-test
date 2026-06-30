from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING
from app.schema.response.web.stats import (
    AdminStatsResponse, DriveUsageResponse,
    ProcessingLoadResponse, AlertResponse, AlertItem
)

if TYPE_CHECKING:
    from db.generated.stats import AsyncQuerier

class StatsService:
    def __init__(self, querier: "AsyncQuerier"):
        self.q = querier

    async def get_dashboard_stats(self) -> AdminStatsResponse:
        active_events = await self.q.get_active_events_count()
        photos = await self.q.get_total_photos_uploaded()
        metrics = await self.q.get_processing_job_metrics()

        return AdminStatsResponse(
            active_events=active_events or 0,
            photos_uploaded=photos or 0,
            processed_photos=metrics.completed_count if metrics else 0,
            queue_size=metrics.pending_count if metrics else 0,
            timestamp=datetime.now(timezone.utc)
        )

    async def get_processing_load(self) -> ProcessingLoadResponse:
        metrics = await self.q.get_processing_job_metrics()
        if not metrics:
            return ProcessingLoadResponse(completed=0.0, processing=0.0, queued=0.0)

        total = metrics.completed_count + metrics.running_count + metrics.pending_count

        if total == 0:
            return ProcessingLoadResponse(completed=0.0, processing=0.0, queued=0.0)

        return ProcessingLoadResponse(
            completed=round((metrics.completed_count / total) * 100, 1),
            processing=round((metrics.running_count / total) * 100, 1),
            queued=round((metrics.pending_count / total) * 100, 1)
        )

    async def get_storage_usage(self) -> DriveUsageResponse:
        used_bytes = await self.q.get_total_storage_bytes()
        # Mock d'un total de 1TB (1000 Go) pour l'affichage Frontend
        total_bytes = 1000 * 1024 * 1024 * 1024

        return DriveUsageResponse(
            used_bytes=used_bytes or 0,
            total_bytes=total_bytes,
            timestamp=datetime.now(timezone.utc)
        )

    async def get_staff_alerts(self, staff_id: uuid.UUID) -> AlertResponse:
        db_alerts = [a async for a in self.q.get_recent_staff_alerts(staff_user_id=staff_id)]
        unread_count = await self.q.get_unread_staff_alerts_count(staff_user_id=staff_id)

        alerts = []
        for a in db_alerts:
            # Assuming payload is a dict with title and message
            payload = a.payload or {}
            alerts.append(AlertItem(
                id=str(a.id),
                type=a.type,
                title=payload.get("title", "Notification"),
                message=payload.get("message", "No message provided"),
                created_at=a.created_at,
                is_read=a.read_at is not None
            ))

        return AlertResponse(
            alerts=alerts,
            unread_count=unread_count or 0,
            timestamp=datetime.now(timezone.utc)
        )
