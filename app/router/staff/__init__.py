from app.router.staff.drive import router as staff_drive_router
from fastapi import APIRouter


router = APIRouter(prefix="/stuff",tags=["stuff"])
router.include_router(staff_drive_router)