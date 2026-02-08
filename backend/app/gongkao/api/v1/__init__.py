from backend.app.gongkao.api.v1.category import router as category_router
from backend.app.gongkao.api.v1.ciyu import router as ciyu_router
from backend.app.gongkao.api.v1.gangwei import router as gangwei_router
from backend.app.gongkao.api.v1.guanmei import router as guanmei_router
from backend.app.gongkao.api.v1.jingyan import router as jingyan_router

from backend.app.gongkao.api.v1.shiping import router as shiping_router
from backend.app.gongkao.api.v1.shizhen import router as shizhen_router
from backend.app.gongkao.api.v1.zhenti import router as zhenti_router
from fastapi import APIRouter

router = APIRouter(prefix='/gk')

router.include_router(category_router, prefix='/category', tags=['分类模块'])
router.include_router(ciyu_router, prefix='/ciyu', tags=['词语模块'])
router.include_router(gangwei_router, prefix='/gangwei', tags=['岗位模块'])
router.include_router(guanmei_router, prefix='/guanmei', tags=['官媒学言语'])
router.include_router(jingyan_router, prefix='/jingyan', tags=['经验模块'])

router.include_router(shiping_router, prefix='/shiping', tags=['时评模块'])
router.include_router(shizhen_router, prefix='/shizhen', tags=['时政模块'])
router.include_router(zhenti_router, prefix='/zhenti', tags=['真题模块'])


