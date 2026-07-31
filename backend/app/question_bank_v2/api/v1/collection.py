from fastapi import APIRouter, Request

from backend.app.question_bank_v2.schema.question import CollectQuestionsParam, CollectQuestionsResult
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(dependencies=[DependsJwtAuth])


@router.post('/collect', summary='统一采集题目 ID', name='qbank_v2_collect_questions')
async def collect_questions(
    request: Request,
    db: CurrentSession,
    obj: CollectQuestionsParam,
) -> ResponseSchemaModel[CollectQuestionsResult]:
    """按题库、错题、收藏、笔记或指定题目来源返回稳定题目 ID"""
    data = await practice_service.collect_questions(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)
