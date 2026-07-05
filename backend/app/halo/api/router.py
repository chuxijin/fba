from fastapi import APIRouter

from backend.app.halo.api.v1.halo import router as halo_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(halo_router, prefix='/halo', tags=['Halo 博客'])
