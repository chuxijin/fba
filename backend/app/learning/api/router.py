from fastapi import APIRouter

from backend.app.learning.api.v1.admin import router as admin_router
from backend.app.learning.api.v1.user import router as user_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)
v1.include_router(admin_router, prefix='/learning/admin', tags=['学习管理-管理端'])
v1.include_router(user_router, prefix='/learning/user', tags=['学习管理-用户端'])
