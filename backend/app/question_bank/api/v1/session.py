#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from time import perf_counter
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Path, Query, Request
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

from backend.app.question_bank.schema.practice import (
    BatchUpsertPracticeRecordsResult,
    BatchUpsertSessionQuestionsParam,
    CreatePracticeSessionParam,
    GetPracticeRecordDetail,
    GetPracticeRecordListItem,
    GetPracticeSessionDetail,
    GetPracticeSessionListItem,
    SessionReport,
    SubmitPracticeSessionParam,
    SubmitPracticeSessionResult,
)
from backend.app.question_bank.service.membership_service import membership_service
from backend.app.question_bank.service.session_service import session_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.exception import errors
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


async def _resolve_session_id(db: CurrentSession, session_key: str, user_id: int) -> int:
    """按 session_key 解析会话 ID 并校验归属"""
    from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
    session = await practice_session_dao.get_by_key(db, session_key)
    if not session:
        raise errors.NotFoundError(msg='会话不存在')
    if session.user_id != user_id:
        raise errors.ForbiddenError(msg='无权访问此会话')
    return session.id


# ============ 练习会话接口 ============


@router.post('', summary='创建练习会话', name='qbank_practice_create_session', dependencies=[DependsJwtAuth])
async def create_session(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreatePracticeSessionParam,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """创建练习会话"""
    # 分段计时埋点（性能诊断用，定位瓶颈后可移除）
    timings: list[tuple[str, float]] = []
    total_start = perf_counter()

    # 复习类会话（错题/收藏/笔记）的题目来自用户付费期已生成的私有数据，跳过题库/筛选/知识点权限校验
    is_review_session = obj.session_type in {'wrong', 'favorite', 'note'}

    t0 = perf_counter()
    membership_detail: list[tuple[str, float]] = []
    if obj.chapter_id is not None:
        m0 = perf_counter()
        obj.bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=obj.chapter_id,
            bank_id=obj.bank_id,
            user_id=None if is_review_session else request.user.id,
        )
        membership_detail.append(('resolve_bank_context_for_chapter', perf_counter() - m0))
    elif obj.bank_id and not is_review_session:
        m0 = perf_counter()
        await membership_service.verify_bank_list_access(
            db=db,
            user_id=request.user.id,
            bank_id=obj.bank_id,
        )
        membership_detail.append(('verify_bank_list_access', perf_counter() - m0))

    if not is_review_session:
        m0 = perf_counter()
        await membership_service.verify_filter_access(
            db=db,
            user_id=request.user.id,
            cat_id=obj.cat_id,
            region=obj.region,
            year_start=obj.year_start,
            year_end=obj.year_end,
        )
        membership_detail.append(('verify_filter_access', perf_counter() - m0))
        m0 = perf_counter()
        await membership_service.verify_knowledge_access(
            db=db,
            user_id=request.user.id,
            knowledge_point=obj.knowledge_point,
        )
        membership_detail.append(('verify_knowledge_access', perf_counter() - m0))
    timings.append(('membership_checks', perf_counter() - t0))

    t0 = perf_counter()
    new_session = await session_service.create_unified_session(db=db, user_id=request.user.id, obj=obj)
    timings.append(('create_unified_session', perf_counter() - t0))

    t0 = perf_counter()
    session = await session_service.get_session_detail(
        db=db, session_id=new_session.id, user_id=request.user.id
    )
    timings.append(('get_session_detail_after_create', perf_counter() - t0))

    t0 = perf_counter()
    response = response_base.success(data=GetPracticeSessionDetail.model_validate(session))
    timings.append(('pydantic_serialize', perf_counter() - t0))

    logger.debug(
        'create_session_timing | user_id={} session_type={} chapter_id={} bank_id={} is_review={} new_session_id={} total={:.1f}ms detail={} membership={}',
        request.user.id,
        obj.session_type,
        obj.chapter_id,
        obj.bank_id,
        is_review_session,
        new_session.id,
        (perf_counter() - total_start) * 1000,
        ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
        ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in membership_detail) or 'none',
    )
    return response


@router.get('/latest', summary='获取最新进行中的会话', name='qbank_practice_get_latest_session', dependencies=[DependsJwtAuth])
async def get_latest_session(
    request: Request,
    db: CurrentSession,
    session_type: Annotated[str | None, Query(description='会话类型')] = None,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='篇章 ID')] = None,
    cat_id: Annotated[int | None, Query(description='分类 ID')] = None,
    region: Annotated[str | None, Query(description='地区')] = None,
    year_start: Annotated[int | None, Query(description='起始年份')] = None,
    year_end: Annotated[int | None, Query(description='结束年份')] = None,
    knowledge_point: Annotated[list[str] | None, Query(description='知识点条件')] = None,
    practice_mode: Annotated[str | None, Query(description='刷题模式')] = None,
    source_key: Annotated[str | None, Query(description='来源签名')] = None,
) -> ResponseModel:
    """获取用户最新的进行中会话"""
    if chapter_id is not None:
        bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=chapter_id,
            bank_id=bank_id,
            user_id=request.user.id,
        )

    resolved_source_key = source_key
    should_build_source_key = (
        resolved_source_key is None
        and session_type is not None
        and any([
            bank_id is not None,
            chapter_id is not None,
            cat_id is not None,
            region is not None,
            year_start is not None,
            year_end is not None,
            bool(knowledge_point),
            practice_mode is not None,
        ])
    )
    if should_build_source_key:
        resolved_source_key = session_service.build_session_source_key(
            CreatePracticeSessionParam(
                session_type=session_type,
                bank_id=bank_id,
                chapter_id=chapter_id,
                cat_id=cat_id,
                region=region,
                year_start=year_start,
                year_end=year_end,
                knowledge_point=knowledge_point,
                exam_config={'practice_mode': practice_mode} if practice_mode else None,
            )
        )

    session = await session_service.get_latest_session(
        db=db,
        user_id=request.user.id,
        session_type=session_type,
        bank_id=bank_id,
        chapter_id=chapter_id,
        source_key=resolved_source_key,
    )
    if not session:
        return response_base.fail(res=CustomResponse(code=400, msg='没有进行中的会话'))

    return response_base.success(data=GetPracticeSessionDetail.model_validate(session))


@router.get(
    '',
    summary='获取用户练习会话列表',
    name='qbank_practice_get_sessions',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_sessions(
    request: Request,
    db: CurrentSession,
    session_type: Annotated[str | None, Query(description='会话类型')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    cat_id: Annotated[int | None, Query(gt=0, description='题库目录分类 ID')] = None,
    kp_cat_id: Annotated[int | None, Query(gt=0, description='知识点分类 ID')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeSessionListItem]]:
    """获取用户的练习会话列表"""
    stmt = await session_service.get_session_list_select(
        db=db,
        user_id=request.user.id,
        session_type=session_type,
        status=status,
        cat_id=cat_id,
        kp_cat_id=kp_cat_id,
    )
    page_data = await paging_data(db, stmt, GetPracticeSessionListItem)
    return response_base.success(data=page_data)


@router.get('/{session_key}', summary='获取练习会话详情', name='qbank_practice_get_session', dependencies=[DependsJwtAuth])
async def get_session(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """获取练习会话详情"""
    timings: list[tuple[str, float]] = []
    total_start = perf_counter()

    # Cut #1：单 SQL 完成 key→id 解析 + 归属校验 + selectinload 详情
    t0 = perf_counter()
    session_data = await session_service.get_session_detail_by_key(
        db=db, session_key=session_key, user_id=request.user.id
    )
    timings.append(('get_session_detail_by_key', perf_counter() - t0))

    logger.debug(
        'get_session_route_timing | user_id={} session_id={} total={:.1f}ms detail={}',
        request.user.id,
        session_data.get('id'),
        (perf_counter() - total_start) * 1000,
        ', '.join(f'{name}={cost * 1000:.1f}ms' for name, cost in timings),
    )
    return response_base.success(data=session_data)


@router.post('/{session_key}/submit', summary='提交练习会话', name='qbank_practice_submit_session', dependencies=[DependsJwtAuth])
async def submit_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(description='会话 Key')],
    obj: SubmitPracticeSessionParam,
) -> ResponseSchemaModel[SubmitPracticeSessionResult]:
    """提交练习会话"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    result = await session_service.submit_session(
        db=db, session_id=sid, user_id=request.user.id, obj=obj,
    )

    from backend.app.study_plan.service.session_hook import handle_session_completed

    await handle_session_completed(
        db,
        session_key=session_key,
        user_id=request.user.id,
        correct_count=result.correct_count,
        total_count=result.completed_count,
    )

    from backend.app.study_plan.service.ability_profile import sync_question_bank_session_profile

    try:
        async with db.begin_nested():
            await sync_question_bank_session_profile(
                db,
                user_id=request.user.id,
                session_id=sid,
            )
    except SQLAlchemyError as exc:
        logger.warning(
            'sync_question_bank_session_profile_failed | user_id={} session_key={} error={}',
            request.user.id,
            session_key,
            exc,
        )

    return response_base.success(data=result)


@router.post('/{session_key}/abandon', summary='放弃练习会话', name='qbank_practice_abandon_session', dependencies=[DependsJwtAuth])
async def abandon_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseModel:
    """放弃练习会话"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    count = await session_service.abandon_session(db=db, session_id=sid, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{session_key}', summary='删除练习会话', name='qbank_practice_delete_session', dependencies=[DependsJwtAuth])
async def delete_session(
    request: Request,
    db: CurrentSessionTransaction,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseModel:
    """删除练习会话"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    count = await session_service.delete_session(db=db, session_id=sid, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 答题记录接口 ============


@router.post('/{session_key}/records', summary='批量提交或更新答题记录', name='qbank_practice_upsert_records', dependencies=[DependsJwtAuth])
async def upsert_records(
    request: Request,
    db: CurrentSession,
    background_tasks: BackgroundTasks,
    session_key: Annotated[str, Path(description='会话 Key')],
    obj: BatchUpsertSessionQuestionsParam,
) -> ResponseSchemaModel[BatchUpsertPracticeRecordsResult]:
    """批量创建或更新答题记录"""
    async with db.begin():
        sid = await _resolve_session_id(db, session_key, request.user.id)
        obj.session_id = sid
        result = await session_service.upsert_records(db=db, user_id=request.user.id, obj=obj)

    # 同步路径只做"用户当下要看的事"：鉴权 / 落盘 / 会话轻量进度。
    # 错题本维护 / 进度同步 / 统计快照增量改为事务提交后由 Celery 异步处理，
    # 这里通过 BackgroundTasks 在响应发送后投递 Celery，确保任务读到的是已提交数据。
    async_payload = result.pop('_async_payload', None)
    if async_payload is not None:
        from backend.app.task.tasks.qbank.tasks import process_record_side_effects

        background_tasks.add_task(process_record_side_effects.delay, **async_payload)

    return response_base.success(data=result)


@router.get('/records/{pk}', summary='获取答题记录详情', name='qbank_practice_get_record', dependencies=[DependsJwtAuth])
async def get_record(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='记录 ID')],
) -> ResponseSchemaModel[GetPracticeRecordDetail]:
    """获取答题记录详情"""
    record = await session_service.get_record(db=db, record_id=pk, user_id=request.user.id)
    return response_base.success(data=GetPracticeRecordDetail.model_validate(record))


@router.get(
    '/records',
    summary='获取答题记录列表',
    name='qbank_practice_get_records',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_records(
    request: Request,
    db: CurrentSession,
    session_id: Annotated[int | None, Query(description='会话 ID')] = None,
    question_id: Annotated[int | None, Query(description='题目 ID')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeRecordListItem]]:
    """获取答题记录列表"""
    stmt = await session_service.get_record_list_select(
        user_id=request.user.id, session_id=session_id, question_id=question_id
    )
    page_data = await paging_data(db, stmt, GetPracticeRecordListItem)
    return response_base.success(data=page_data)


@router.get('/{session_key}/records', summary='获取会话全部答题记录', name='qbank_practice_get_session_records', dependencies=[DependsJwtAuth])
async def get_session_records(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseSchemaModel[list[GetPracticeRecordDetail]]:
    """获取会话全部答题记录"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    records = await session_service.get_session_records(db=db, session_id=sid, user_id=request.user.id)
    return response_base.success(data=[GetPracticeRecordDetail.model_validate(item) for item in records])


# ============ 报告 / 解析 ============


@router.get('/{session_key}/report', summary='获取会话答题报告', name='qbank_practice_get_session_report', dependencies=[DependsJwtAuth])
async def get_session_report(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseSchemaModel[SessionReport]:
    """获取会话答题报告"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    report = await session_service.get_session_report(db=db, session_id=sid, user_id=request.user.id)
    return response_base.success(data=report)


@router.get('/{session_key}/solution', summary='获取会话答案解析', name='qbank_practice_get_session_solution', dependencies=[DependsJwtAuth])
async def get_session_solution(
    request: Request,
    db: CurrentSession,
    session_key: Annotated[str, Path(description='会话 Key')],
) -> ResponseModel:
    """获取会话全部题目的答案与解析"""
    sid = await _resolve_session_id(db, session_key, request.user.id)
    solutions = await session_service.get_session_solution(db=db, session_id=sid, user_id=request.user.id)
    return response_base.success(data=solutions)
