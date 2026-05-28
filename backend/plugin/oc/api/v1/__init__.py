from fastapi import APIRouter

from backend.plugin.oc.api.v1.jobs import router as jobs_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(jobs_router)
