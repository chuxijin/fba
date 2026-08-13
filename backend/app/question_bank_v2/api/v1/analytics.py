from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank_v2.schema.analytics import (
    GetBankProgressDetail,
    GetBankWrongSectionCounts,
    GetCollectionProgressSummary,
    GetPracticeRankList,
    GetUserPracticeReport,
    GetKnowledgePointTrends,
    RankType,
)
from backend.app.question_bank_v2.service.analytics_service import analytics_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(dependencies=[DependsJwtAuth])


@router.get(
    '/collections/{collection_id}/progress/summary',
    summary='获取合集内题库学习进度摘要',
    name='qbank_v2_get_collection_progress_summary',
)
async def get_collection_progress_summary(
    request: Request,
    db: CurrentSession,
    *,
    collection_id: Annotated[int, Path(gt=0, description='合集 ID')],
    include_descendants: Annotated[bool, Query(description='是否包含子合集')] = True,
) -> ResponseSchemaModel[GetCollectionProgressSummary]:
    data = await analytics_service.get_collection_progress_summary(
        db=db,
        user_id=request.user.id,
        collection_id=collection_id,
        include_descendants=include_descendants,
    )
    return response_base.success(data=data)


@router.get('/banks/{bank_id}/progress', summary='获取题库篇章学习进度', name='qbank_v2_get_bank_progress')
async def get_bank_progress(
    request: Request,
    db: CurrentSession,
    bank_id: Annotated[int, Path(gt=0, description='题库稳定身份 ID')],
) -> ResponseSchemaModel[GetBankProgressDetail]:
    data = await analytics_service.get_bank_progress(db=db, user_id=request.user.id, bank_id=bank_id)
    return response_base.success(data=data)


@router.get(
    '/banks/{bank_id}/wrong-sections',
    summary='获取题库错题篇章统计',
    name='qbank_v2_get_bank_wrong_sections',
)
async def get_bank_wrong_sections(
    request: Request,
    db: CurrentSession,
    bank_id: Annotated[int, Path(gt=0, description='题库稳定身份 ID')],
) -> ResponseSchemaModel[GetBankWrongSectionCounts]:
    data = await analytics_service.get_bank_wrong_sections(db=db, user_id=request.user.id, bank_id=bank_id)
    return response_base.success(data=data)


@router.get('/analytics/report', summary='获取用户刷题报告', name='qbank_v2_get_user_practice_report')
async def get_user_practice_report(
    request: Request,
    db: CurrentSession,
    days: Annotated[int, Query(ge=7, le=365, description='每日趋势天数')] = 30,
) -> ResponseSchemaModel[GetUserPracticeReport]:
    data = await analytics_service.get_user_report(db=db, user_id=request.user.id, days=days)
    return response_base.success(data=data)


@router.get('/analytics/ranks', summary='获取刷题排行榜', name='qbank_v2_get_practice_ranks')
async def get_practice_ranks(
    request: Request,
    db: CurrentSession,
    rank_type: Annotated[RankType, Query(description='排行榜类型')] = 'practice_count',
    offset: Annotated[int, Query(ge=0, le=980, description='偏移量，仅开放前 1000 名')] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description='返回数量')] = 20,
) -> ResponseSchemaModel[GetPracticeRankList]:
    data = await analytics_service.get_rank_list(
        db=db,
        user_id=request.user.id,
        rank_type=rank_type,
        offset=offset,
        limit=limit,
    )
    return response_base.success(data=data)


@router.get(
    '/analytics/knowledge-trends',
    summary='知识点维度刷题趋势',
    name='qbank_v2_get_knowledge_point_trends',
)
async def get_knowledge_point_trends(
    request: Request,
    db: CurrentSession,
    days: Annotated[int, Query(ge=7, le=365, description='趋势天数')] = 90,
) -> ResponseSchemaModel[GetKnowledgePointTrends]:
    data = await analytics_service.get_knowledge_point_trends(
        db=db,
        user_id=request.user.id,
        days=days,
    )
    return response_base.success(data=data)
