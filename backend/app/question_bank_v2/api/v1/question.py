from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank_v2.schema.question import (
    CreateQuestionParam,
    CreateQuestionRevisionParam,
    GetQuestionDetail,
    GetQuestionListItem,
    GetQuestionRevisionDetail,
    QuestionType,
    RevisionStatus,
    UpdateQuestionParam,
    UpdateQuestionRevisionParam,
)
from backend.app.question_bank_v2.service.question_service import question_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth, Depends(RequestPermission('question_bank:bank:update')), DependsRBAC])


@router.get('', summary='获取题目管理列表', name='qbank_v2_get_questions')
async def get_questions(
    db: CurrentSession,
    *,
    question_type: Annotated[QuestionType | None, Query(description='题型')] = None,
    revision_status: Annotated[RevisionStatus | None, Query(description='最近版本状态')] = None,
    keyword: Annotated[str | None, Query(max_length=200, description='题干关键字')] = None,
    offset: Annotated[int, Query(ge=0, description='偏移量')] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description='返回数量')] = 100,
) -> ResponseSchemaModel[list[GetQuestionListItem]]:
    """按每题最近版本查询题目管理列表"""
    data = await question_service.get_list(
        db=db,
        question_type=question_type,
        revision_status=revision_status,
        keyword=keyword,
        offset=offset,
        limit=limit,
    )
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取题目管理详情', name='qbank_v2_get_question')
async def get_question(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
    revision_id: Annotated[int | None, Query(gt=0, description='指定题目版本 ID')] = None,
) -> ResponseSchemaModel[GetQuestionDetail]:
    """获取题目最近版本或指定版本的答案和解析"""
    data = await question_service.get(db=db, pk=pk, revision_id=revision_id)
    return response_base.success(data=data)


@router.post('', summary='创建题目及首个草稿版本', name='qbank_v2_create_question')
async def create_question(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateQuestionParam,
) -> ResponseSchemaModel[GetQuestionDetail]:
    """创建题目稳定身份、草稿内容、答案和解析"""
    data = await question_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新题目稳定身份', name='qbank_v2_update_question')
async def update_question(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
    obj: UpdateQuestionParam,
) -> ResponseSchemaModel[GetQuestionDetail]:
    """仅更新题目编码、可见性和身份状态"""
    data = await question_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    return response_base.success(data=data)


@router.get('/{pk}/revisions', summary='获取题目版本列表', name='qbank_v2_get_question_revisions')
async def get_question_revisions(
    db: CurrentSession,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
) -> ResponseSchemaModel[list[GetQuestionRevisionDetail]]:
    """按版本号倒序获取题目全部版本"""
    data = await question_service.get_revisions(db=db, question_id=pk)
    return response_base.success(data=data)


@router.post('/{pk}/revisions', summary='创建题目草稿版本', name='qbank_v2_create_question_revision')
async def create_question_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
    obj: CreateQuestionRevisionParam,
) -> ResponseSchemaModel[GetQuestionRevisionDetail]:
    """创建下一个递增版本号的题目草稿"""
    data = await question_service.create_revision(db=db, question_id=pk, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}/revisions/{revision_id}',
    summary='更新题目草稿版本',
    name='qbank_v2_update_question_revision',
)
async def update_question_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题目版本 ID')],
    obj: UpdateQuestionRevisionParam,
) -> ResponseSchemaModel[GetQuestionRevisionDetail]:
    """原子更新草稿题干、选项、答案和解析"""
    data = await question_service.update_revision(
        db=db,
        question_id=pk,
        revision_id=revision_id,
        obj=obj,
        updated_by=request.user.id,
    )
    return response_base.success(data=data)


@router.post(
    '/{pk}/revisions/{revision_id}/publish',
    summary='发布题目版本',
    name='qbank_v2_publish_question_revision',
)
async def publish_question_revision(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(gt=0, description='题目 ID')],
    revision_id: Annotated[int, Path(gt=0, description='题目版本 ID')],
) -> ResponseSchemaModel[GetQuestionRevisionDetail]:
    """校验答案后固化内容哈希并切换当前发布版本"""
    data = await question_service.publish_revision(
        db=db,
        question_id=pk,
        revision_id=revision_id,
        published_by=request.user.id,
    )
    return response_base.success(data=data)
