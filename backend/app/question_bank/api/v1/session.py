#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.question_bank.schema.practice import (
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
from backend.common.security.jwt import DependsJwtAuth
from backend.app.question_bank.service.session_service import session_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


# ============ 练习会话接口 ============


@router.post('', summary='创建练习会话', name='qbank_practice_create_session')
async def create_session(
    db: CurrentSessionTransaction,
    obj: CreatePracticeSessionParam,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """创建练习会话"""
    new_session = await session_service.create_session(db=db, user_id=request.user.id, obj=obj)

    # 重新查询完整详情（含 session_questions 快照）
    session = await session_service.get_session_detail(
        db=db, session_id=new_session.id, user_id=request.user.id
    )
    return response_base.success(data=GetPracticeSessionDetail.model_validate(session))


@router.get('/latest', summary='获取最新的进行中会话', name='qbank_practice_get_latest_session')
async def get_latest_session(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
    session_type: Annotated[str | None, Query(description='会话类型')] = None,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
) -> ResponseModel:
    """获取用户最新的进行中会话（用于恢复未完成的练习）"""
    session = await session_service.get_latest_session(
        db=db, user_id=request.user.id, session_type=session_type,
        bank_id=bank_id, chapter_id=chapter_id,
    )
    if not session:
        return response_base.fail(res=CustomResponse(code=400, msg='没有进行中的会话'))

    return response_base.success(data=GetPracticeSessionDetail.model_validate(session))


@router.get(
    '',
    summary='获取用户练习会话列表',
    name='qbank_practice_get_sessions',
    dependencies=[DependsPagination],
)
async def get_sessions(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
    session_type: Annotated[str | None, Query(description='会话类型')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeSessionListItem]]:
    """获取用户的练习会话列表（分页）"""
    stmt = await session_service.get_session_list_select(
        user_id=request.user.id, session_type=session_type, status=status
    )
    page_data = await paging_data(db, stmt, GetPracticeSessionListItem)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取练习会话详情', name='qbank_practice_get_session')
async def get_session(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """获取练习会话详情（含会话题目快照和答题记录）"""
    session_data = await session_service.get_session_detail(
        db=db, session_id=pk, user_id=request.user.id
    )
    return response_base.success(data=session_data)


@router.post('/{pk}/submit', summary='提交练习会话', name='qbank_practice_submit_session')
async def submit_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: SubmitPracticeSessionParam,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[SubmitPracticeSessionResult]:
    """提交练习会话（统一判题 + 统计 + 错题本）"""
    result = await session_service.submit_session(
        db=db, session_id=pk, user_id=request.user.id, obj=obj,
    )
    return response_base.success(data=result)


@router.post('/{pk}/abandon', summary='放弃练习会话', name='qbank_practice_abandon_session')
async def abandon_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """放弃练习会话（用户中途退出练习时调用）"""
    count = await session_service.abandon_session(db=db, session_id=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除练习会话', name='qbank_practice_delete_session')
async def delete_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """删除练习会话（删除会话及其关联的所有答题记录）"""
    count = await session_service.delete_session(db=db, session_id=pk, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 答题记录接口 ============


@router.post('/{pk}/records', summary='批量提交/更新答题记录', name='qbank_practice_upsert_records')
async def upsert_records(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: BatchUpsertPracticeRecordsParam,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """批量创建/更新答题记录（基于 session_id + question_id 幂等）"""
    # 路径中的 session_id 覆盖 body 中的值，保证一致性
    obj.session_id = pk
    result = await session_service.upsert_records(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=result)


@router.get('/records/{pk}', summary='获取答题记录详情', name='qbank_practice_get_record')
async def get_record(
    db: CurrentSession,
    pk: Annotated[int, Path(description='记录 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[GetPracticeRecordDetail]:
    """获取答题记录详情"""
    record = await session_service.get_record(db=db, record_id=pk, user_id=request.user.id)
    return response_base.success(data=GetPracticeRecordDetail.model_validate(record))


@router.get(
    '/records',
    summary='获取答题记录列表',
    name='qbank_practice_get_records',
    dependencies=[DependsPagination],
)
async def get_records(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
    session_id: Annotated[int | None, Query(description='会话 ID')] = None,
    question_id: Annotated[int | None, Query(description='题目 ID')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeRecordListItem]]:
    """获取答题记录列表（分页）"""
    stmt = await session_service.get_record_list_select(
        user_id=request.user.id, session_id=session_id, question_id=question_id
    )
    page_data = await paging_data(db, stmt, GetPracticeRecordListItem)
    return response_base.success(data=page_data)


@router.get('/{pk}/records', summary='获取会话的所有答题记录', name='qbank_practice_get_session_records')
async def get_session_records(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[list[GetPracticeRecordDetail]]:
    """获取会话的所有答题记录"""
    records = await session_service.get_session_records(db=db, session_id=pk, user_id=request.user.id)
    return response_base.success(data=[GetPracticeRecordDetail.model_validate(r) for r in records])


# ============ 报告 / 解析 ============


@router.get('/{pk}/report', summary='获取会话答题报告', name='qbank_practice_get_session_report')
async def get_session_report(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[SessionReport]:
    """获取会话答题报告（含统计信息、答题卡数据、错题 ID 列表）"""
    report = await session_service.get_session_report(db=db, session_id=pk, user_id=request.user.id)
    return response_base.success(data=report)


@router.get('/{pk}/solution', summary='获取会话答案解析', name='qbank_practice_get_session_solution')
async def get_session_solution(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseModel:
    """获取会话全部题目的答案与解析"""
    solutions = await session_service.get_session_solution(db=db, session_id=pk, user_id=request.user.id)
    return response_base.success(data=solutions)



