#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank.schema.practice import (
    BatchUpsertPracticeRecordsResult,
    BatchUpsertPracticeRecordsParam,
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
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ============ 练习会话接口 ============


@router.post('', summary='创建练习会话', name='qbank_practice_create_session', dependencies=[DependsJwtAuth])
async def create_session(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreatePracticeSessionParam,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """创建练习会话"""
    if obj.chapter_id is not None:
        obj.bank_id = await membership_service.resolve_bank_context_for_chapter(
            db=db,
            chapter_id=obj.chapter_id,
            bank_id=obj.bank_id,
            user_id=request.user.id,
        )
    elif obj.bank_id:
        await membership_service.verify_bank_list_access(
            db=db,
            user_id=request.user.id,
            bank_id=obj.bank_id,
        )

    await membership_service.verify_filter_access(
        db=db,
        user_id=request.user.id,
        cat_id=obj.cat_id,
        region=obj.region,
        year_start=obj.year_start,
        year_end=obj.year_end,
    )
    await membership_service.verify_knowledge_access(
        db=db,
        user_id=request.user.id,
        knowledge_point=obj.knowledge_point,
    )

    new_session = await session_service.create_unified_session(db=db, user_id=request.user.id, obj=obj)
    session = await session_service.get_session_detail(
        db=db, session_id=new_session.id, user_id=request.user.id
    )
    return response_base.success(data=GetPracticeSessionDetail.model_validate(session))


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
    study_domain: Annotated[str | None, Query(description='学习领域编码')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeSessionListItem]]:
    """获取用户的练习会话列表"""
    stmt = await session_service.get_session_list_select(
        db=db,
        user_id=request.user.id,
        session_type=session_type,
        status=status,
        study_domain=study_domain,
    )
    page_data = await paging_data(db, stmt, GetPracticeSessionListItem)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取练习会话详情', name='qbank_practice_get_session', dependencies=[DependsJwtAuth])
async def get_session(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """获取练习会话详情"""
    session_data = await session_service.get_session_detail(
        db=db, session_id=pk, user_id=request.user.id
    )
    return response_base.success(data=session_data)


@router.post('/{pk}/submit', summary='提交练习会话', name='qbank_practice_submit_session', dependencies=[DependsJwtAuth])
async def submit_session(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: SubmitPracticeSessionParam,
) -> ResponseSchemaModel[SubmitPracticeSessionResult]:
    """提交练习会话"""
    result = await session_service.submit_session(
        db=db, session_id=pk, user_id=request.user.id, obj=obj,
    )
    return response_base.success(data=result)


@router.post('/{pk}/abandon', summary='放弃练习会话', name='qbank_practice_abandon_session', dependencies=[DependsJwtAuth])
async def abandon_session(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
) -> ResponseModel:
    """放弃练习会话"""
    count = await session_service.abandon_session(db=db, session_id=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除练习会话', name='qbank_practice_delete_session', dependencies=[DependsJwtAuth])
async def delete_session(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
) -> ResponseModel:
    """删除练习会话"""
    count = await session_service.delete_session(db=db, session_id=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 答题记录接口 ============


@router.post('/{pk}/records', summary='批量提交或更新答题记录', name='qbank_practice_upsert_records', dependencies=[DependsJwtAuth])
async def upsert_records(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: BatchUpsertPracticeRecordsParam,
) -> ResponseSchemaModel[BatchUpsertPracticeRecordsResult]:
    """批量创建或更新答题记录"""
    obj.session_id = pk
    result = await session_service.upsert_records(db=db, user_id=request.user.id, obj=obj)
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


@router.get('/{pk}/records', summary='获取会话全部答题记录', name='qbank_practice_get_session_records', dependencies=[DependsJwtAuth])
async def get_session_records(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
) -> ResponseSchemaModel[list[GetPracticeRecordDetail]]:
    """获取会话全部答题记录"""
    records = await session_service.get_session_records(db=db, session_id=pk, user_id=request.user.id)
    return response_base.success(data=[GetPracticeRecordDetail.model_validate(item) for item in records])


# ============ 报告 / 解析 ============


@router.get('/{pk}/report', summary='获取会话答题报告', name='qbank_practice_get_session_report', dependencies=[DependsJwtAuth])
async def get_session_report(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
) -> ResponseSchemaModel[SessionReport]:
    """获取会话答题报告"""
    report = await session_service.get_session_report(db=db, session_id=pk, user_id=request.user.id)
    return response_base.success(data=report)


@router.get('/{pk}/solution', summary='获取会话答案解析', name='qbank_practice_get_session_solution', dependencies=[DependsJwtAuth])
async def get_session_solution(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
) -> ResponseModel:
    """获取会话全部题目的答案与解析"""
    solutions = await session_service.get_session_solution(db=db, session_id=pk, user_id=request.user.id)
    return response_base.success(data=solutions)
