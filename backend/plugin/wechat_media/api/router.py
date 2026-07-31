from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.wechat_media.api.v1.media import router as media_router

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(media_router, prefix='/wechat/media', tags=['微信公众号素材'])
