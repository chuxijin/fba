from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank_v2.schema.review import (
    CreateExternalWrongQuestionParam,
    CreateQuestionReviewParam,
    CreateReviewTagParam,
    GetDueWrongQuestionResult,
    GetQuestionReviewDetail,
    GetReviewTagDetail,
    GetWrongQuestionListItem,
    SubmitQuestionReviewResult,
    WrongEntrySource,
    WrongStateStatus,
)
from backend.app.question_bank_v2.service.wrong_review_service import wrong_review_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get('/tags', summary='获取复盘标签', name='qbank_v2_get_review_tags')
async def get_review_tags(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetReviewTagDetail]]:
    """返回系统标签和当前用户自定义标签"""
    data = await wrong_review_service.get_tags(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/tags', summary='创建复盘标签', name='qbank_v2_create_review_tag')
async def create_review_tag(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateReviewTagParam,
) -> ResponseSchemaModel[GetReviewTagDetail]:
    """创建仅当前用户可见的错因、方法或其他标签"""
    data = await wrong_review_service.create_tag(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('', summary='获取我的错题列表', name='qbank_v2_get_wrong_questions')
async def get_wrong_questions(
    request: Request,
    db: CurrentSession,
    status: Annotated[WrongStateStatus | None, Query(description='错题状态；空表示全部')] = 'active',
    entry_source: Annotated[WrongEntrySource | None, Query(description='首次录入来源')] = None,
    offset: Annotated[int, Query(ge=0, description='偏移量')] = 0,
    limit: Annotated[int, Query(ge=1, le=200, description='返回数量')] = 100,
) -> ResponseSchemaModel[list[GetWrongQuestionListItem]]:
    """系统内答错与外部录入使用同一列表模型"""
    data = await wrong_review_service.get_list(
        db=db,
        user_id=request.user.id,
        status=status,
        entry_source=entry_source,
        offset=offset,
        limit=limit,
    )
    return response_base.success(data=data)


@router.get('/due', summary='获取到期错题', name='qbank_v2_get_due_wrong_questions')
async def get_due_wrong_questions(
    request: Request,
    db: CurrentSession,
    limit: Annotated[int, Query(ge=1, le=200, description='本次返回题数')] = 100,
) -> ResponseSchemaModel[GetDueWrongQuestionResult]:
    """按 FSRS 下次复习时间返回当前用户已到期的活跃错题"""
    data = await wrong_review_service.get_due(db=db, user_id=request.user.id, limit=limit)
    return response_base.success(data=data)


@router.post('/external', summary='录入外部错题', name='qbank_v2_capture_external_wrong_question')
async def capture_external_wrong_question(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateExternalWrongQuestionParam,
) -> ResponseSchemaModel[GetWrongQuestionListItem]:
    """将手工、OCR 或导入题统一创建为用户私有版本化题目"""
    data = await wrong_review_service.capture_external(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post(
    '/{wrong_state_id}/reviews',
    summary='提交错题复盘',
    name='qbank_v2_submit_wrong_question_review',
)
async def submit_wrong_question_review(
    request: Request,
    db: CurrentSessionTransaction,
    wrong_state_id: Annotated[int, Path(gt=0, description='错题状态 ID')],
    obj: CreateQuestionReviewParam,
) -> ResponseSchemaModel[SubmitQuestionReviewResult]:
    """追加复盘事件，并以四级评分原子推进 FSRS 调度"""
    data = await wrong_review_service.submit_review(
        db=db,
        user_id=request.user.id,
        wrong_state_id=wrong_state_id,
        obj=obj,
    )
    return response_base.success(data=data)


@router.get(
    '/reviews/{review_id}',
    summary='获取错题复盘详情',
    name='qbank_v2_get_wrong_question_review',
)
async def get_wrong_question_review(
    request: Request,
    db: CurrentSession,
    review_id: Annotated[int, Path(gt=0, description='复盘事件 ID')],
) -> ResponseSchemaModel[GetQuestionReviewDetail]:
    """读取复盘快照、标签、知识点和当次 FSRS 调度结果"""
    data = await wrong_review_service.get_review(
        db=db,
        user_id=request.user.id,
        review_id=review_id,
    )
    return response_base.success(data=data)
