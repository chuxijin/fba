from fastapi import APIRouter

from backend.app.gongkao.api.v1.category import router as category_router
from backend.app.gongkao.api.v1.gangwei import router as gangwei_router
from backend.app.gongkao.api.v1.hanyu import router as hanyu_router
from backend.app.gongkao.api.v1.shizhen import router as shizhen_router
from backend.app.gongkao.api.v1.zhenti import router as zhenti_router

router = APIRouter(prefix='/gk')

router.include_router(category_router, prefix='/category', tags=['分类模块'])
router.include_router(gangwei_router, prefix='/gangwei', tags=['岗位模块'])
router.include_router(hanyu_router, prefix='/hanyu', tags=['汉语词汇模块'])
router.include_router(shizhen_router, prefix='/shizhen', tags=['时政模块'])
router.include_router(zhenti_router, prefix='/zhenti', tags=['真题模块'])
