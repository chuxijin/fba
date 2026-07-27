from fastapi import APIRouter

from backend.app.question_bank_v2.api.v1.bank import router as bank_router
from backend.app.question_bank_v2.api.v1.catalog import router as catalog_router
from backend.app.question_bank_v2.api.v1.composition import router as composition_router
from backend.app.question_bank_v2.api.v1.practice import router as practice_router
from backend.app.question_bank_v2.api.v1.preference import router as preference_router
from backend.app.question_bank_v2.api.v1.question import router as question_router

router = APIRouter(prefix='/qbank-v2')
router.include_router(bank_router, prefix='/banks', tags=['题库 V2'])
router.include_router(catalog_router, prefix='/collections', tags=['题库合集 V2'])
router.include_router(composition_router, prefix='/banks', tags=['题库编排 V2'])
router.include_router(question_router, prefix='/questions', tags=['题目 V2'])
router.include_router(preference_router, prefix='/preferences', tags=['题库偏好 V2'])
router.include_router(practice_router, prefix='/sessions', tags=['题库练习 V2'])
