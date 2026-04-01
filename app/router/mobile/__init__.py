from fastapi import APIRouter
from app.router.mobile.auth import router as mobile_auth_router
from app.router.mobile.enrollement import router as onboarding_router
from app.router.mobile.event import router as event_router
from app.router.mobile.notifications import router as mobile_notifications_router
from app.router.mobile.photo_approval import router as photo_approval_router


router = APIRouter(prefix="/user", tags=["user"])
router.add_api_route
router.include_router(mobile_auth_router)
router.include_router(onboarding_router)
router.include_router(event_router)
router.include_router(mobile_notifications_router)
router.include_router(photo_approval_router)
