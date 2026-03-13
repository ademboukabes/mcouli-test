from fastapi import APIRouter
from app.router.web.staff_users import router as staff_users_router
router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(staff_users_router)