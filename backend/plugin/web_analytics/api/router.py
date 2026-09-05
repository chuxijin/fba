from fastapi import APIRouter

from backend.plugin.web_analytics.api.v1.collector import router as collector_router
from backend.plugin.web_analytics.api.v1.report import router as report_router
from backend.plugin.web_analytics.api.v1.site import router as site_router

v1 = APIRouter(prefix='/api/v1/analytics')
v1.include_router(collector_router, tags=['网站统计采集'])
v1.include_router(site_router, prefix='/sites', tags=['网站统计站点'])
v1.include_router(report_router, tags=['网站统计报表'])
