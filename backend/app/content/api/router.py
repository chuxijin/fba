from fastapi import APIRouter

from backend.app.content.api.v1.content import router as content_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(content_router, prefix='/content', tags=['内容管理'])
