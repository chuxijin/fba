#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
练习会话和答题记录接口

设计原则：
- 基于会话的答题流程：创建会话 → 答题 → 提交会话
- 支持多种练习模式：章节练习、随机练习、错题练习等
- 记录用户的答题历史和统计数据
"""
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.question_bank.crud.crud_practice_record import practice_record_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.schema.practice import (
    BatchCreatePracticeRecordsParam,
    CreatePracticeSessionParam,
    GetPracticeRecordDetail,
    GetPracticeRecordListItem,
    GetPracticeSessionDetail,
    GetPracticeSessionListItem,
    SessionReport,
    SessionSolution,
    SubmitPracticeSessionParam,
    UpdatePracticeSessionParam,
    UserAnswerItem,
    UserStatistics,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.app.question_bank.service.practice_service import practice_service
from backend.app.question_bank.service.session_service import session_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_code import CustomResponse
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.utils.timezone import timezone

router = APIRouter()


# ============ 练习会话接口 ============


@router.post('', summary='创建练习会话', name='qbank_practice_create_session')
async def create_session(
    db: CurrentSessionTransaction,
    obj: CreatePracticeSessionParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """创建练习会话"""
    new_session, questions_data = await session_service.create_session(db=db, user_id=current_user.user_id, obj=obj)

    session_detail = GetPracticeSessionDetail.model_validate(new_session)
    session_detail.questions = questions_data

    return response_base.success(data=session_detail)


@router.get('/latest', summary='获取最新的进行中会话', name='qbank_practice_get_latest_session')
async def get_latest_session(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    bank_id: Annotated[int | None, Query(description='题库 ID')] = None,
    chapter_id: Annotated[int | None, Query(description='章节 ID')] = None,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """获取用户最新的进行中会话（用于恢复未完成的练习）"""
    session = await session_service.get_latest_session(
        db=db, user_id=current_user.user_id, bank_id=bank_id, chapter_id=chapter_id
    )
    if not session:
        return response_base.fail(res=CustomResponse(code=400, msg='没有进行中的会话'))

    return response_base.success(data=GetPracticeSessionDetail.model_validate(session))


@router.get('/{pk}', summary='获取练习会话详情', name='qbank_practice_get_session')
async def get_session(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetPracticeSessionDetail]:
    """获取练习会话详情（包含题目列表和答案解析）"""
    session, questions_data, user_answers = await session_service.get_session_detail(
        db=db, session_id=pk, user_id=current_user.user_id
    )

    session_detail = GetPracticeSessionDetail.model_validate(session)
    session_detail.questions = questions_data
    session_detail.user_answers = {
        qid: UserAnswerItem(**ans) for qid, ans in user_answers.items()
    } if user_answers else None

    return response_base.success(data=session_detail)


@router.get(
    '',
    summary='获取用户练习会话列表',
    name='qbank_practice_get_sessions',
    dependencies=[DependsPagination],
)
async def get_sessions(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    session_type: Annotated[str | None, Query(description='会话类型')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeSessionListItem]]:
    """
    获取用户的练习会话列表（分页）

    支持按会话类型和状态筛选
    """
    stmt = await practice_session_dao.get_select(
        user_id=current_user.user_id, session_type=session_type, status=status
    )
    page_data = await paging_data(db, stmt, GetPracticeSessionListItem)
    return response_base.success(data=page_data)


@router.put('/{pk}', summary='更新练习会话统计', name='qbank_practice_update_session')
async def update_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: UpdatePracticeSessionParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """更新练习会话统计数据（做题过程中实时更新）"""
    update_dict = obj.model_dump(exclude_none=True)
    if not update_dict:
        return response_base.fail(res=CustomResponse(code=400, msg='没有需要更新的数据'))

    count = await session_service.update_session_statistics(
        db=db,
        session_id=pk,
        user_id=current_user.user_id,
        completed_count=update_dict.get('completed_count'),
        correct_count=update_dict.get('correct_count'),
        wrong_count=update_dict.get('wrong_count'),
        total_time=update_dict.get('total_time'),
    )

    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/submit', summary='提交练习会话', name='qbank_practice_submit_session')
async def submit_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    obj: SubmitPracticeSessionParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """提交练习会话"""
    # 调用 practice_service 统一判题
    submit_time = timezone.now()
    await practice_service.submit_session_and_judge(
        db=db,
        session_id=pk,
        total_time=obj.total_time,
        submit_time=submit_time,
    )

    return response_base.success(data='success')


@router.post('/{pk}/abandon', summary='放弃练习会话', name='qbank_practice_abandon_session')
async def abandon_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """放弃练习会话（用户中途退出练习时调用）"""
    count = await session_service.abandon_session(db=db, session_id=pk, user_id=current_user.user_id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除练习会话', name='qbank_practice_delete_session')
async def delete_session(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """删除练习会话（删除会话及其关联的所有答题记录）"""
    count = await session_service.delete_session(db=db, session_id=pk, user_id=current_user.user_id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ============ 答题记录接口 ============


@router.post('/records', summary='创建答题记录', name='qbank_practice_create_records')
async def create_records(
    db: CurrentSessionTransaction,
    obj: BatchCreatePracticeRecordsParam,
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseModel:
    """创建答题记录（支持单条或批量，会跳过已存在的记录）"""
    await session_service.create_records(
        db=db, user_id=current_user.user_id, session_id=obj.session_id, records=obj.records
    )

    return response_base.success()


@router.get('/records/{pk}', summary='获取答题记录详情', name='qbank_practice_get_record')
async def get_record(
    db: CurrentSession,
    pk: Annotated[int, Path(description='记录 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[GetPracticeRecordDetail]:
    """获取答题记录详情"""
    record = await session_service.get_record(db=db, record_id=pk, user_id=current_user.user_id)

    return response_base.success(data=GetPracticeRecordDetail.model_validate(record))


@router.get(
    '/records',
    summary='获取答题记录列表',
    name='qbank_practice_get_records',
    dependencies=[DependsPagination],
)
async def get_records(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    session_id: Annotated[int | None, Query(description='会话 ID')] = None,
    question_id: Annotated[int | None, Query(description='题目 ID')] = None,
) -> ResponseSchemaModel[PageData[GetPracticeRecordListItem]]:
    """
    获取答题记录列表（分页）

    支持按会话、题目筛选
    """
    stmt = await practice_record_dao.get_select(
        user_id=current_user.user_id, session_id=session_id, question_id=question_id
    )
    page_data = await paging_data(db, stmt, GetPracticeRecordListItem)
    return response_base.success(data=page_data)


@router.get('/{pk}/records', summary='获取会话的所有答题记录', name='qbank_practice_get_session_records')
async def get_session_records(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[list[GetPracticeRecordDetail]]:
    """获取会话的所有答题记录"""
    records = await session_service.get_session_records(db=db, session_id=pk, user_id=current_user.user_id)

    return response_base.success(data=[GetPracticeRecordDetail.model_validate(r) for r in records])


@router.get('/{pk}/report', summary='获取会话答题报告', name='qbank_practice_get_session_report')
async def get_session_report(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[SessionReport]:
    """获取会话答题报告（用于结算页面，包含统计信息、答题卡数据、错题 ID 列表）"""
    report_data = await session_service.get_session_report(db=db, session_id=pk, user_id=current_user.user_id)

    return response_base.success(data=report_data)


@router.get('/{pk}/solution', summary='获取会话答案解析', name='qbank_practice_get_session_solution')
async def get_session_solution(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会话 ID')],
    current_user: AuthUser = DependsCustomerAuth,
) -> ResponseSchemaModel[SessionSolution]:
    """获取会话答案解析（包含题目内容、正确答案、解析、用户答案、是否正确）"""
    solution_data = await session_service.get_session_solution(db=db, session_id=pk, user_id=current_user.user_id)

    return response_base.success(data=solution_data)


# ============ 用户学习统计接口 ============


@router.get('/user/statistics', summary='获取用户学习统计')
async def get_user_statistics(
    db: CurrentSession,
    current_user: AuthUser = DependsCustomerAuth,
    cat_id: Annotated[int | None, Query(description='分类 ID（可选，筛选指定分类下的题库）')] = None,
) -> ResponseSchemaModel[UserStatistics]:
    """获取用户学习统计（用于练习中心页面显示各题库进度和判断是否有未完成会话）"""
    data = await practice_service.get_user_statistics(db=db, user_id=current_user.user_id, cat_id=cat_id)
    return response_base.success(data=data)
