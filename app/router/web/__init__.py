from fastapi import APIRouter
from app.router.web.staff_users import router as staff_users_router
from app.router.web.event import router as event_router
from app.router.web.auth import router as auth_routes

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(staff_users_router)
router.include_router(event_router)
router.include_router(auth_routes)
