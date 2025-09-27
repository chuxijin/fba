from fastapi import APIRouter

from backend.app.job.api.v1.job_app import router as job_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(job_router)
