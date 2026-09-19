from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.feishu.api.v1.sheet import router as feishu_sheet_router

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(feishu_sheet_router, prefix='/feishu/sheet', tags=['飞书电子表格'])
