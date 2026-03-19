#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Body, Path, Query, Request

from backend.app.question_bank.schema.note import GetQuestionNoteDetail
from backend.app.question_bank.schema.practice import GetQuestionSolution, GetSessionQuestionsResponse
from backend.app.question_bank.schema.question import (
    CreateQuestionParam,
    DeleteQuestionParam,
    GetQuestionDynamicCollectionItem,
    GetQuestionDetail,
    GetQuestionListItem,
    GetQuestionStatisticsDetail,
    QuestionAnalysisItem,
    QuestionOptionStatsItem,
    UpdateQuestionParam,
)
from backend.app.question_bank.schema.question_import import (
    BatchImportParam,
    BatchImportResult,
)
from backend.app.question_bank.security import DependsCurrentUser
from backend.app.question_bank.service.favorite_service import favorite_service
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.note_service import note_service
from backend.app.question_bank.service.question_service import question_service
from backend.app.question_bank.service.session_service import session_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.common.security.rbac import DependsRBAC
from backend.database.redis import redis_client
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


def _parse_int_csv(value: str | None) -> list[int]:
    if not value:
        return []
    result: list[int] = []
    for item in value.split(','):
        token = item.strip()
        if not token or not token.isdigit():
            continue
        parsed = int(token)
        if parsed > 0:
            result.append(parsed)
    return sorted(set(result))


def _parse_text_csv(value: str | None) -> list[str]:
    if not value:
        return []
    values = [item.strip() for item in value.split(',') if item and item.strip()]
    return sorted(set(values))


# ============ 批量查询接口（必须在 /{pk} 之前） ===========


@router.get('/favorites', summary='批量检查收藏状态', name='qbank_batch_check_favorites')
async def batch_check_favorites(
    db: CurrentSession,
    question_ids: Annotated[str, Query(description='题目 ID 列表，逗号分隔')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[dict[int, bool]]:
    """批量检查收藏状态"""
    status_map = await favorite_service.batch_check_favorites_from_string(
        db=db, user_id=current_user.user_id, question_ids_str=question_ids
    )
    return response_base.success(data=status_map)


@router.get('/notes', summary='批量查询笔记', name='qbank_batch_get_notes')
async def batch_get_notes(
    db: CurrentSession,
    question_ids: Annotated[str, Query(description='题目 ID 列表，逗号分隔')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[dict[int, GetQuestionNoteDetail | None]]:
    """批量查询笔记"""
    note_map = await note_service.batch_get_notes_from_string(
        db=db, user_id=current_user.user_id, question_ids_str=question_ids
    )
    return response_base.success(data=note_map)


@router.get('/collections', summary='动态获取题目合集', name='qbank_get_dynamic_collections')
async def get_dynamic_collections(
    db: CurrentSession,
    cat_id: Annotated[int | None, Query(description='分类 ID')] = None,
    region: Annotated[str | None, Query(description='地区关键字')] = None,
    knowledge_ids: Annotated[str | None, Query(description='知识点 ID，逗号分隔')] = None,
    knowledge_names: Annotated[str | None, Query(description='知识点名称，逗号分隔')] = None,
    stem_keyword: Annotated[str | None, Query(description='题干关键字')] = None,
    option_keyword: Annotated[str | None, Query(description='选项关键字')] = None,
    analysis_keyword: Annotated[str | None, Query(description='解析关键字')] = None,
    year_start: Annotated[int | None, Query(description='起始年份（按题目创建年）')] = None,
    year_end: Annotated[int | None, Query(description='结束年份（按题目创建年）')] = None,
) -> ResponseSchemaModel[list[GetQuestionDynamicCollectionItem]]:
    """按筛选条件动态返回试卷合集（通过题目挂载关系聚合）"""
    kp_ids = _parse_int_csv(knowledge_ids)
    kp_names = _parse_text_csv(knowledge_names)
    if year_start is not None and year_end is not None and year_start > year_end:
        year_start, year_end = year_end, year_start

    cache_payload = {
        'cat_id': cat_id,
        'region': (region or '').strip() or None,
        'knowledge_ids': kp_ids,
        'knowledge_names': kp_names,
        'stem_keyword': (stem_keyword or '').strip() or None,
        'option_keyword': (option_keyword or '').strip() or None,
        'analysis_keyword': (analysis_keyword or '').strip() or None,
        'year_start': year_start,
        'year_end': year_end,
    }
    cache_hash = hashlib.sha1(
        json.dumps(cache_payload, ensure_ascii=False, sort_keys=True).encode('utf-8')
    ).hexdigest()
    cache_key = f'qbank:collections:v1:{cache_hash}'

    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return response_base.success(data=json.loads(cached))
    except Exception:
        # 缓存异常不影响主流程
        pass

    data = await question_service.get_dynamic_collections(
        db=db,
        cat_id=cat_id,
        region=region,
        knowledge_ids=kp_ids,
        knowledge_names=kp_names,
        stem_keyword=stem_keyword,
        option_keyword=option_keyword,
        analysis_keyword=analysis_keyword,
        year_start=year_start,
        year_end=year_end,
    )

    try:
        await redis_client.set(cache_key, json.dumps(data, ensure_ascii=False), ex=60)
    except Exception:
        pass

    return response_base.success(data=data)


# ============ 题目相关接口 ============


@router.get('/{pk}', summary='获取题目详情（不含答案）', name='qbank_get_question', dependencies=[DependsCurrentUser])
async def get_question(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[GetQuestionDetail]:
    """
    获取题目详情（不含答案和解析）

    - 客户：需要会员权限验证
    - 管理员：直接查看，无需会员验证
    """
    user_type = current_user.user_type

    if user_type == 'customer':
        await membership_service.verify_question_access(db=db, user_id=current_user.user_id, question_id=pk)

    data = await question_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取题目列表',
    name='qbank_get_question_list',
    dependencies=[DependsCurrentUser, DependsPagination],
)
async def get_question_list(
    request: Request,
    db: CurrentSession,
    current_user: AuthUser = DependsCurrentUser,
    ids: Annotated[str | None, Query(description='题目 ID 列表，逗号分隔')] = None,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
    type: Annotated[str | None, Query(description='题型')] = None,
    difficulty: Annotated[str | None, Query(description='难度')] = None,
    content_status: Annotated[int | None, Query(description='内容状态')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用（挂载级别）')] = None,
    review_status: Annotated[int | None, Query(description='审核状态（挂载级别）')] = None,
    keyword: Annotated[str | None, Query(description='关键字搜索')] = None,
    page: Annotated[int | None, Query(description='页码', ge=1)] = None,
    size: Annotated[int | None, Query(description='每页数量', ge=1, le=100)] = None,
    include_answer: Annotated[bool, Query(description='是否包含答案（用于查看历史记录）')] = False,
) -> ResponseSchemaModel[PageData[GetQuestionListItem] | list[GetQuestionListItem]]:
    """
    获取题目列表

    - 客户：需要会员权限验证，不支持分页
    - 管理员：无需会员验证，支持分页
    - 支持通过 ids 参数批量获取指定题目
    - include_answer=True 时返回答案和解析
    """
    user_type = current_user.user_type

    # 解析 ids 参数
    question_ids = None
    if ids:
        question_ids = [int(id.strip()) for id in ids.split(',') if id.strip()]

    # 客户需要验证会员权限（按 ids 查询时跳过权限验证）
    if user_type == 'customer' and not question_ids:
        if bank_id:
            await membership_service.verify_bank_list_access(db=db, user_id=current_user.user_id, bank_id=bank_id)
        elif chapter_id:
            await membership_service.verify_chapter_access(db=db, user_id=current_user.user_id, chapter_id=chapter_id)

    data = await question_service.get_list(
        db=db,
        ids=question_ids,
        bank_id=bank_id,
        chapter_id=chapter_id,
        type=type,
        difficulty=difficulty,
        content_status=content_status,
        is_active=is_active,
        review_status=review_status,
        keyword=keyword,
        page=page if user_type == 'admin' else None,
        size=size if user_type == 'admin' else None,
        include_analysis=include_answer,
    )

    return response_base.success(data=data)


@router.post(
    '',
    summary='创建题目',
    name='qbank_create_question',
    dependencies=[DependsRBAC],
)
async def create_question(request: Request, db: CurrentSessionTransaction, obj: CreateQuestionParam) -> ResponseModel:
    """管理员接口 - 创建题目"""
    await question_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新题目',
    name='qbank_update_question',
    dependencies=[DependsRBAC],
)
async def update_question(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    obj: UpdateQuestionParam,
) -> ResponseModel:
    """管理员接口 - 更新题目"""
    count = await question_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除题目',
    name='qbank_delete_question',
    dependencies=[DependsRBAC],
)
async def delete_question(db: CurrentSessionTransaction, obj: DeleteQuestionParam) -> ResponseModel:
    """管理员接口 - 删除题目（级联删除解析和统计）"""
    count = await question_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 题目解析相关接口 ============


@router.get(
    '/{pk}/analysis',
    summary='获取题目解析（含答案）',
    name='qbank_get_question_analysis',
    dependencies=[DependsCurrentUser],
)
async def get_question_analysis(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[QuestionAnalysisItem]:
    """
    获取题目解析（含答案）

    - 客户：需要会员权限验证，自动增加查看次数
    - 管理员：直接查看，不增加查看次数
    """
    user_type = current_user.user_type

    if user_type == 'customer':
        await membership_service.verify_question_access(db=db, user_id=current_user.user_id, question_id=pk)
        increment_view = True
    else:
        increment_view = False

    data = await question_service.get_analysis(db=db, question_id=pk, increment_view=increment_view)
    return response_base.success(data=data)


@router.get(
    '/{pk}/solution',
    summary='获取题目答案和解析（练题模式专用）',
    name='qbank_get_question_solution',
    dependencies=[DependsCurrentUser],
)
async def get_question_solution(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
    user_answer: Annotated[str | None, Query(description='用户答案（用于判题）')] = None,
) -> ResponseSchemaModel[GetQuestionSolution]:
    """获取题目答案和解析（练题模式专用）"""
    data = await question_service.get_solution(db=db, question_id=pk, user_answer=user_answer)
    return response_base.success(data=data)


@router.post(
    '/{pk}/analysis/helpful',
    summary='标记解析是否有帮助',
    name='qbank_mark_analysis_helpful',
    dependencies=[DependsCurrentUser],
)
async def mark_analysis_helpful(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='题目 ID')],
    is_helpful: Annotated[bool, Body(embed=True, description='是否有帮助')],
) -> ResponseModel:
    """标记解析是否有帮助"""
    await question_service.mark_analysis_helpful(db=db, question_id=pk, is_helpful=is_helpful)
    return response_base.success()


# ============ 题目统计相关接口 ============


@router.get(
    '/{pk}/statistics',
    summary='获取题目统计',
    name='qbank_get_question_statistics',
    dependencies=[DependsCurrentUser],
)
async def get_question_statistics(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
) -> ResponseSchemaModel[GetQuestionStatisticsDetail]:
    """获取题目统计"""
    data = await question_service.get_statistics(db=db, question_id=pk)
    return response_base.success(data=data)


@router.get(
    '/{pk}/option-stats',
    summary='获取题目选项统计',
    name='qbank_get_question_option_stats',
    dependencies=[DependsCurrentUser],
)
async def get_question_option_stats(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='题目 ID')],
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
) -> ResponseSchemaModel[list[QuestionOptionStatsItem]]:
    """获取题目各挂载点下的选项统计"""
    data = await question_service.get_option_stats(
        db=db,
        question_id=pk,
        bank_id=bank_id,
        chapter_id=chapter_id,
    )
    return response_base.success(data=data)


# ============ 批量导入相关接口 ============


@router.post('/import', summary='批量导入题目', name='qbank_batch_import_questions', dependencies=[DependsRBAC])
async def batch_import_questions(
    request: Request,
    db: CurrentSessionTransaction,
    obj: BatchImportParam,
) -> ResponseSchemaModel[BatchImportResult]:
    """
    管理员接口 - 批量导入题目（从 CSV）

    - 支持中文题型和难度
    - 自动创建章节（一级/二级目录）
    - 同时创建题目和解析记录
    - 返回详细的导入结果
    """
    data = await question_service.batch_import(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=data)


# ============ 会话题目批量获取接口 ============


@router.get(
    '/sessions/{session_id}',
    summary='获取会话题目静态内容和材料',
    name='qbank_get_session_questions',
    dependencies=[DependsCurrentUser],
)
async def get_session_questions(
    request: Request,
    db: CurrentSession,
    session_id: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[GetSessionQuestionsResponse]:
    """
    获取会话题目静态内容和去重材料

    - 题目静态内容一次性返回（不含材料全文，仅含 material_ids）
    - 材料独立返回并去重
    - 前端不再逐题拉取题干/选项/材料
    """
    data = await session_service.get_session_questions_with_materials(
        db=db, session_id=session_id, user_id=current_user.user_id
    )
    return response_base.success(data=data)


