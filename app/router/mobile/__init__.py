from fastapi import APIRouter
from app.router.mobile.auth import router as mobile_auth_router

router = APIRouter(prefix="/user",tags=["user"])
router.include_router(mobile_auth_router)
