from fastapi import APIRouter
from app.router.web.staff_users import router as staff_users_router
from app.router.web.event import router as event_router
from app.router.web.auth import router as auth_routes
from app.router.web.audit import router as audit_router
from app.router.web.users import router as users_router
from app.router.web.stats import router as stats_router

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(staff_users_router)
router.include_router(event_router)
router.include_router(auth_routes)
router.include_router(audit_router)
router.include_router(users_router)
router.include_router(stats_router)
