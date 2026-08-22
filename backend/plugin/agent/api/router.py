from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.agent.api.v1.shenlun_coach import router as shenlun_coach_router
from backend.plugin.agent.api.v1.shenlun_grading import router as shenlun_grading_router

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)
if getattr(settings, 'AGENT_SHENLUN_ENABLED', True):
    v1.include_router(shenlun_grading_router, prefix='/agent/shenlun', tags=['Agent - 申论批改'])
if getattr(settings, 'AGENT_SHENLUN_COACH_ENABLED', False):
    v1.include_router(shenlun_coach_router, prefix='/agent/shenlun/coach', tags=['Agent - 申论教练'])
