from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.question import (
    CreateQuestionParam,
    GetQuestionDetail,
    GetQuestionListItem,
    QuestionType,
    UpdateQuestionParam,
)
from backend.app.question_bank_v2.service.question_service import question_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC])


@router.get(
    '',
    summary='获取题目管理列表',
    name='qbank_v2_get_questions',
    dependencies=[DependsPagination],
)
async def get_questions(
    db: CurrentSession,
    *,
    bank_id: Annotated[int | None, Query(gt=0, description='题库 ID')] = None,
    question_type: Annotated[QuestionType | None, Query(description='题型')] = None,
    keyword: Annotated[str | None, Query(max_length=200, description='题干关键字')] = None,
) -> ResponseSchemaModel[PageData[GetQuestionListItem]]:
    """获取题目管理列表（分页）"""
    stmt = question_service.get_list_select(bank_id=bank_id, question_type=question_type, keyword=keyword)
    page_data = await paging_data(db, stmt, GetQuestionListItem)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取题目管理详情', name='qbank_v2_get_question')
async def get_question(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
) -> ResponseSchemaModel[GetQuestionDetail]:
    data = await question_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.post('', summary='创建题目', name='qbank_v2_create_question')
async def create_question(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateQuestionParam,
) -> ResponseSchemaModel[GetQuestionDetail]:
    data = await question_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新题目', name='qbank_v2_update_question')
async def update_question(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
    obj: UpdateQuestionParam,
) -> ResponseSchemaModel[GetQuestionDetail]:
    data = await question_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    return response_base.success(data=data)