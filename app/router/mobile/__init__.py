from fastapi import APIRouter
from app.router.mobile.auth import router as mobile_auth_router
from app.router.mobile.enrollement import router as onboarding_router
from app.router.mobile.event import router as event_router


router = APIRouter(prefix="/user",tags=["user"])
router.include_router(mobile_auth_router)
router.include_router(onboarding_router)
router.include_router(event_router)
