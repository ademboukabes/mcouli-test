from fastapi import APIRouter

from app.router.staff.drive import router as staff_drive_router
from app.router.staff.notifications import router as staff_notifications_router
from app.router.staff.uploads import router as staff_uploads_router

router = APIRouter(prefix="/staff", tags=["staff"])
router.include_router(staff_drive_router)
router.include_router(staff_notifications_router)
router.include_router(staff_uploads_router)
