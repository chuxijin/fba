from fastapi import APIRouter

from backend.app.gongkao.api.v1.gangwei import router as gangwei_router
from backend.app.gongkao.api.v1.hanyu import router as hanyu_router
from backend.app.gongkao.api.v1.shizhen import router as shizhen_router
from backend.app.gongkao.api.v1.practice_log import router as practice_log_router
from backend.app.gongkao.api.v1.hanyu_notebook import router as hanyu_notebook_router

router = APIRouter(prefix='/gk')

router.include_router(gangwei_router, prefix='/gangwei', tags=['岗位模块'])
router.include_router(hanyu_router, prefix='/hanyu', tags=['汉语词汇模块'])
router.include_router(shizhen_router, prefix='/shizhen', tags=['时政模块'])
router.include_router(practice_log_router, prefix='/practice-logs', tags=['练习记录模块'])
router.include_router(hanyu_notebook_router, prefix='/hanyu/notebook', tags=['汉语学习本模块'])
