from fastapi import APIRouter, Depends
from app.container import Container, get_container
from app.deps.cookie_auth import require_admin_staff
from db.generated.models import StaffUser
from app.schema.response.web.stats import (
    AdminStatsResponse, DriveUsageResponse,
    ProcessingLoadResponse, AlertResponse
)

router = APIRouter(prefix="/stats", tags=["Web - Stats"])

@router.get("/dashboard", response_model=AdminStatsResponse)
async def get_dashboard(
    container: Container = Depends(get_container),
    current_admin: StaffUser = Depends(require_admin_staff)
) -> AdminStatsResponse:
    """Staff Admin Only: Get global KPIs for the dashboard"""
    return await container.stats_service.get_dashboard_stats()


@router.get("/processing-load", response_model=ProcessingLoadResponse)
async def get_processing_load(
    container: Container = Depends(get_container),
    current_admin: StaffUser = Depends(require_admin_staff)
) -> ProcessingLoadResponse:
    """Staff Admin Only: Get pipeline processing load percentages"""
    return await container.stats_service.get_processing_load()


@router.get("/storage", response_model=DriveUsageResponse)
async def get_storage(
    container: Container = Depends(get_container),
    current_admin: StaffUser = Depends(require_admin_staff)
) -> DriveUsageResponse:
    """Staff Admin Only: Get MinIO storage consumption"""
    return await container.stats_service.get_storage_usage()


@router.get("/alerts", response_model=AlertResponse)
async def get_alerts(
    container: Container = Depends(get_container),
    current_admin: StaffUser = Depends(require_admin_staff)
) -> AlertResponse:
    """Staff Admin Only: Get recent alerts/notifications for the admin"""
    return await container.stats_service.get_staff_alerts(current_admin.id)
