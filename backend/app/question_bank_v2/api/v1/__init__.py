from fastapi import APIRouter

from backend.app.question_bank_v2.api.v1.analytics import router as analytics_router
from backend.app.question_bank_v2.api.v1.bank import router as bank_router
from backend.app.question_bank_v2.api.v1.catalog import router as catalog_router
from backend.app.question_bank_v2.api.v1.collection import router as collection_router
from backend.app.question_bank_v2.api.v1.composition import router as composition_router
from backend.app.question_bank_v2.api.v1.evaluation import router as evaluation_router
from backend.app.question_bank_v2.api.v1.interaction import router as interaction_router
from backend.app.question_bank_v2.api.v1.knowledge import router as knowledge_router
from backend.app.question_bank_v2.api.v1.locate_training import router as locate_training_router
from backend.app.question_bank_v2.api.v1.material import router as material_router
from backend.app.question_bank_v2.api.v1.practice import router as practice_router
from backend.app.question_bank_v2.api.v1.preference import router as preference_router
from backend.app.question_bank_v2.api.v1.question import router as question_router
from backend.app.question_bank_v2.api.v1.review import router as review_router
from backend.app.question_bank_v2.api.v1.user_content import router as user_content_router

router = APIRouter(prefix='/qbank-v2')
router.include_router(bank_router, prefix='/banks', tags=['题库 V2'])
router.include_router(catalog_router, prefix='/collections', tags=['题库合集 V2'])
router.include_router(composition_router, prefix='/banks', tags=['题库编排 V2'])
router.include_router(collection_router, prefix='/questions', tags=['题目采集 V2'])
router.include_router(interaction_router, prefix='/questions', tags=['交互题 V2'])
router.include_router(question_router, prefix='/questions', tags=['题目 V2'])
router.include_router(material_router, prefix='/materials', tags=['题目材料 V2'])
router.include_router(preference_router, prefix='/preferences', tags=['题库偏好 V2'])
router.include_router(practice_router, prefix='/sessions', tags=['题库练习 V2'])
router.include_router(evaluation_router, prefix='/evaluations', tags=['题库评测 V2'])
router.include_router(review_router, prefix='/wrong-questions', tags=['错题复盘 V2'])
router.include_router(knowledge_router, tags=['题库知识点 V2'])
router.include_router(user_content_router, tags=['题库用户内容 V2'])
router.include_router(analytics_router, tags=['题库统计 V2'])
router.include_router(locate_training_router, prefix='/locate-trainings', tags=['找数训练 V2'])
